#!/usr/bin/env python

"""Handlers for background and administrative tasks."""

from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.api.labs import taskqueue
from google.appengine.api import memcache

from models import *

import wsgiref.handlers
import logging
import re
import time

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
      if response.status_code == 200 and response.content.startswith("["):
        key = Batch(data=response.content).put()
        if key:
          taskqueue.Task(
              url='/tasks/etl',
              params={'batch_id': key.id()}
              ).add('etl')
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

    tweets_by_word = {}
    words_in_tweet = {}
    tweets = Tweet.from_batch(batch)

    for tweet in tweets:
      words_in_tweet[tweet] = Topic.tokenize(tweet.content)
      for word in set(words_in_tweet[tweet]):
        if word not in tweets_by_word:
          tweets_by_word[word] = []
        tweets_by_word[word].append(tweet)

    words = tweets_by_word.keys()
    parenttopics = Topic.get_by_key_name(['parent:' + word for word in words])
    begins_a_phrase = dict(zip(words, parenttopics))
    keys = []
    for word in words:
      keys.append(db.Key.from_path(*Topic.create_path([word])))

      if not begins_a_phrase[word]:
        continue

      memo = {}
      tweets = tweets_by_word[word]
      for tweet in tweets:
        tokens = words_in_tweet[tweet]
        while word in tokens:
          start = tokens.index(word)
          slice = tokens[start:]
          for index in range(len(slice)):
            if index == 0:
              continue
            pieces = slice[:index + 1]
            path = Topic.create_path(pieces)
            keys.append(db.Key.from_path(*path))

            topic_name = ' '.join(pieces)

            if topic_name not in memo:
              memo[topic_name] = []
            memo[topic_name].append(tweet)
          tokens = tokens[start + 1:]

        tweets_by_word.update(memo)

    ontopic = set()
    for topic in [topic for topic in Topic.get(keys) if topic]:
      tweets = tweets_by_word[topic.name]
      for tweet in tweets:
        tweet.topics.append(topic.key())
      ontopic.update(tweets)

    batch.delete()
    db.put(ontopic)

application = webapp.WSGIApplication([
  ('/tasks/queuefetch', QueueFetch),
  ('/tasks/fetch', Fetch),
  ('/tasks/etl', ETL),
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
