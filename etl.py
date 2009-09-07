#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.api.labs import taskqueue

from models import *

import edrop
import wsgiref.handlers
import logging
import re

class QueueFetch(webapp.RequestHandler):
  def get(self):
    url = "http://twitter.com/statuses/public_timeline.json"
    task = taskqueue.Task(
        url='/run/fetch',
        params={'url': url}
        )
    task.add('fetch')

class Fetch(webapp.RequestHandler):
  def post(self):
    url = self.request.get('url')
    response = urlfetch.fetch(url)
    if response.status_code == 200 and response.content.startswith("["):
      key = Batch(data=response.content).put()
      if key:
        taskqueue.Task(
            url='/run/etl',
            params={'batch_id': key.id()}
            ).add('etl')

class ETL(webapp.RequestHandler):
  def post(self):
    try:
      id = self.request.get('batch_id')
      batch = Batch.get_by_id(long(id))
    except ValueError:
      # Flush tasks with bad batch ids
      self.response.set_status(200)
      return

    if not batch:
      logging.warning("Batch not found %s." % id)
      self.error(400)
      return

    ontopic = set()
    topic_tweets = dict()

    for tweet in edrop.extract_tweets(batch):
      words = re.findall('\w+', tweet.content, re.UNICODE)
      for word in map(lambda word: word.lower(), words):
        topic_key_name = 'key:' + word
        if not topic_tweets.has_key(topic_key_name):
          topic_tweets[topic_key_name] = set()
        topic_tweets[topic_key_name].add(tweet)

    topics = Topic.get_by_key_name(topic_tweets.keys())
    topics = filter(lambda topic: topic is not None, topics)
    for topic in topics:
      for tweet in topic_tweets['key:' + topic.name]:
        tweet.topics.append(topic.key())
        ontopic.add(tweet)

    batch.delete()
    db.save(ontopic)

class ExpireCache(webapp.RequestHandler):
  def get(self):
    key = self.request.get("key")
    result = edrop.expire_cache(key)

application = webapp.WSGIApplication([
  ('/run/queuefetch', QueueFetch),
  ('/run/fetch', Fetch),
  ('/run/etl', ETL),
  ('/run/expirecache', ExpireCache)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
