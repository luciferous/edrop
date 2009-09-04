#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.api import urlfetch

from models import *

import edrop
import wsgiref.handlers

class Fetch(webapp.RequestHandler):
  def get(self):
    url = "http://twitter.com/statuses/public_timeline.json"
    response = urlfetch.fetch(url)
    if response.status_code == 200 and response.content.startswith("["):
      Batch(data=response.content).save()

class ETL(webapp.RequestHandler):
  def get(self):
    batch = next_batch()
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
  ('/run/fetch', Fetch),
  ('/run/etl', ETL),
  ('/run/expirecache', ExpireCache)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
