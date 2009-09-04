#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import datastore_errors

from models import *

import edrop
import os
import wsgiref.handlers
import re

class TopicDetail(webapp.RequestHandler):
  def get(self, topic_name):
    order = self.request.get("order") or "-created_at"
    topic = edrop.get_topic(topic_name)

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
        'template': 'show.html',
        'tweets': tweets,
        'topic': topic,
        'request_path': self.request.path
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/base.html')
    self.response.out.write(template.render(path, template_values))

class TopicIndex(webapp.RequestHandler):
  def get(self):
    self.error(404) # Nothing here yet

  def post(self):
    topic_name = self.request.get('name')
    if topic_name:
      topic = edrop.get_topic(topic_name)
      if not topic:
        topic = edrop.create_topic(topic_name)
      self.redirect('/topics/%s' % topic.name)
    else:
      self.error(400) # Bad request

class Main(webapp.RequestHandler):
  def get(self):
    tweets = Tweet.all().order("-created_at").fetch(5)
    template_values = {
        'title': 'edrop',
        'template': 'index.html',
        'tweets': tweets
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/base.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    topic_name = self.request.get('name')
    if topic_name:
      self.redirect('/topics/%s' % topic_name)
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
