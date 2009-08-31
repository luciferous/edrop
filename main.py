#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from models import *

import edrop
import os
import wsgiref.handlers
import urllib

class Create(webapp.RequestHandler):
  def get(self):
    notfound = self.request.get("notfound")
    topic_name = self.request.get("topic")

    topic = edrop.get_topic(topic_name)
    if topic:
      self.showtopic(topic_name)

    template_values = {
        'title': topic_name,
        'template': 'create.html',
        'topic_name': topic_name,
        'notfound': notfound
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/base.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    topic_name = self.request.get("topic")
    topic = edrop.get_topic(topic_name)
    if not topic:
      topic = edrop.create_topic(topic_name)
    self.showtopic(topic_name)

  def showtopic(self, topic_name):
    self.redirect('/show?' + urllib.urlencode({'topic': topic_name}))

class Show(webapp.RequestHandler):
  def get(self):
    topic_name = self.request.get("topic")
    topic = edrop.get_topic(topic_name)
    if not topic:
      params = {'topic': topic_name, 'notfound': 1}
      self.redirect('/create?' + urllib.urlencode(params))
      return

    template_values = {
        'title': topic_name,
        'template': 'show.html',
        'tweets': topic.tweets.order("-created_at").fetch(10),
        'topic': topic
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/base.html')
    self.response.out.write(template.render(path, template_values))

class Main(webapp.RequestHandler):
  def get(self):
    tweets = Tweet.all().order("-created_at").fetch(5)
    keys = sum([t.topics for t in tweets], [])
    topics = db.get(keys)

    template_values = {
        'title': 'edrop',
        'template': 'index.html',
        'topics': set([t.name for t in topics]),
        'tweets': tweets
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/base.html')
    self.response.out.write(template.render(path, template_values))

application = webapp.WSGIApplication([
  ('/', Main),
  ('/show', Show),
  ('/create', Create)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
