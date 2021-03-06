#!/usr/bin/env python

"""Handlers for background and administrative tasks."""

from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.api.labs import taskqueue
from google.appengine.api import memcache
from google.appengine.ext import db
from django.utils import simplejson

from models import *

import pickle
import wsgiref.handlers
import logging
import re
import time

MAX_TWEETS = 40

class QueueFetch(webapp.RequestHandler):
  """Puts a task on the fetch queue."""

  def get(self):
    """Called by cron to queue a download of the public timeline."""
    url = "http://twitter.com/statuses/public_timeline.json"
    task = taskqueue.Task(
        url='/tasks/fetch',
        params={'url': url}
        )
    task.add('fetch')

class Fetch(webapp.RequestHandler):
  """Handles requests to download the public timeline."""

  def post(self):
    """Downloads the public timeline, creates a Batch from it, stores the Batch
    to the database, and creates a task to process the Batch created.
    """
    url = self.request.get('url')
    try:
      response = urlfetch.fetch(url)
      if response.status_code == 200:
        items = simplejson.loads(response.content)
        key = Batch(pickled_items=pickle.dumps(items)).put()
        if key:
          taskqueue.Task(
              url='/tasks/etl',
              params={'batch_id': key.id()}
              ).add('etl')
      else:
        logging.info("Fetch failed, got response %d" % response.status_code)
    except urlfetch_errors.DownloadError, e:
      logging.info("Twitter responded too slowly. %s" % e.message)

class ETL(webapp.RequestHandler):
  """Handles request to process Batches."""

  def post(self):
    """Converts Batches to Tweets, and associates Tweets with Topics.

    The strategy used for associating Tweets and Topics is to build a list of
    possible topics for each Tweet. It's useful to think of this process in two
    parts: the first concerns itself with topics that are a single word,
    and the second, with topics comprising multiple words.
    """
    try:
      id = self.request.get('batch_id')
      batch = Batch.get_by_id(long(id))
    except ValueError:
      # Flush tasks with bad batch ids
      self.response.set_status(200)
      return

    if not batch:
      logging.warning("Batch not found %s." % id)
      return

    alltweets = Tweet.from_batch(batch)
    tweets_by_topic = Topic.link_topics(alltweets)
    ontopic = set()
    topic_activity = {}
    for topic, tweets in tweets_by_topic.items():
      key = str(topic.key())
      topic_activity[key] = len(tweets)
      ontopic.update(tweets)
      taskqueue.Task(
          url='/tasks/truncate', params={'key': key}
          ).add('truncate')

    taskqueue.add(
        url='/tasks/activity',
        params={
          'values': simplejson.dumps(topic_activity),
          'batchsize': len(alltweets)
          }
        )

    batch.delete()
    db.put(ontopic)

class Truncate(webapp.RequestHandler):

  def post(self):
    key = db.Key(self.request.get('key'))
    topic = Topic.get(key)

    if not topic:
      self.error(404)
      return

    if topic.tweets.count(MAX_TWEETS) >= MAX_TWEETS:
      db.delete(topic.tweets.order("created_at").fetch(MAX_TWEETS / 2))
      logging.info("Deleted %d tweets from %s." % (MAX_TWEETS / 2, topic.name))

class Activity(webapp.RequestHandler):

  def post(self):
    topic_activity = simplejson.loads(self.request.get('values'))
    batchsize = int(self.request.get('batchsize'))

    def increment_activity(topic_key, activity):
      topic = Topic.get(topic_key)
      topic.record_activity(activity, batchsize)
      db.put(topic)

    for encoded, activity in topic_activity.items():
      try:
        db.run_in_transaction(increment_activity, db.Key(encoded), activity)
      except Exception, e:
        logging.info(e.message)

application = webapp.WSGIApplication([
  ('/tasks/queuefetch', QueueFetch),
  ('/tasks/fetch', Fetch),
  ('/tasks/etl', ETL),
  ('/tasks/activity', Activity),
  ('/tasks/truncate', Truncate),
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
