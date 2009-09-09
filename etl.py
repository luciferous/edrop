#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.api.labs import taskqueue

from models import *

import edrop
import wsgiref.handlers
import logging
import re

URL_RE = re.compile(u"""http://\S+""", re.UNICODE)
SPLIT_RE = re.compile(u"""[\s.,"'\u2026]+""", re.UNICODE)

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
      phrases = ETL._possible_phrases(tweet.content)
      for phrase in phrases:
        topic_key_name = 'key:' + phrase
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

  def _possible_phrases(text):
    urls = URL_RE.findall(text)
    text = URL_RE.sub('', text)
    text = text.lower()
    words = SPLIT_RE.split(text)
    words = filter(lambda word: word is not None, words)
    lengths = range(1, len(words) + 1)
    ranges = zip(lengths, map(lambda l: range(l), lengths))
    phrases = []
    for length, starts in ranges:
      phrases += map(lambda i: ' '.join(words[i:length]), starts)
    return phrases + urls
  _possible_phrases = staticmethod(_possible_phrases)

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
