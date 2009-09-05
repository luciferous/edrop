#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.api.labs import taskqueue

from models import *

import edrop
import wsgiref.handlers

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
    id = self.request.get('batch_id')
    if not id:
      return
    batch = Batch.get_by_id(long(id))
    if not batch:
      return
    tweets = edrop.extract_tweets(batch)
    ontopic = []
    for tweet in tweets:
      topics = edrop.find_topics(tweet)
      if len(topics) > 0:
        tweet.topics += [topic.key() for topic in topics]
        ontopic.append(tweet)

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
