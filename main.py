#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import datastore_errors

from models import *

import os
import wsgiref.handlers
import re
import urllib
import logging

class TopicDetail(webapp.RequestHandler):
  def get(self, topic_name):
    topic_name = urllib.unquote(topic_name)
    topic_name = topic_name.decode('utf8')
    order = self.request.get("order") or "-created_at"

    tokens = Topic.tokenize(topic_name)
    path = Topic.create_path(tokens)
    topic = Topic.get(db.Key.from_path(*path))

    tweets = []
    messages = []
    try:
      if topic:
        tweets = topic.tweets.order(order).fetch(10)
    except datastore_errors.NeedIndexError:
      tweets = topic.tweets.fetch(10)
      messages.append("""These results are unsorted because indexes are currently
      unavailable.""")

    template_values = {
        'topic_name': topic_name,
        'title': topic_name,
        'messages': messages,
        'tweets': tweets,
        'topic': topic,
        'request_path': self.request.path
        }

    path = os.path.join(os.path.dirname(__file__), 'templates/show.html')
    self.response.out.write(template.render(path, template_values))

class TopicIndex(webapp.RequestHandler):
  def get(self):
    self.error(404) # Nothing here yet

  def post(self):
    topic_name = self.request.get('name')
    topic_name = topic_name.strip()

    if not topic_name or len(topic_name) > 140:
      self.error(400) # Bad request
      return

    topics = []
    parent = None
    tokens = Topic.tokenize(topic_name)

    topics = Topic.from_tokens(tokens)
    db.save(topics)

    self.redirect('/topics/%s' % urllib.quote(topic_name.encode('utf8')))

class Main(webapp.RequestHandler):
  def get(self):
    tweets = Tweet.all().order("-created_at").fetch(5)
    template_values = {
        'title': 'edrop',
        'tweets': tweets
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    topic_name = self.request.get('name')
    if topic_name:
      self.redirect('/topics/%s' % urllib.quote(topic_name.encode('utf8')))
    else:
      self.error(404)

application = webapp.WSGIApplication([
  ('/', Main),
  ('/topics/', TopicIndex),
  ('/topics/(.+)', TopicDetail)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
