#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import datastore_errors

from models import *

import edrop
import os
import wsgiref.handlers
import urllib

def show_topic_url(topic_name):
  return '/show?' + urllib.urlencode({'topic': topic_name})

class Create(webapp.RequestHandler):
  def get(self):
    notfound = self.request.get("notfound")
    topic_name = self.request.get("topic")

    topic = edrop.get_topic(topic_name)
    if topic:
      self.redirect(show_topic_url(topic_name))

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
    self.redirect(show_topic_url(topic_name))

class Show(webapp.RequestHandler):
  def get(self):
    topic_name = self.request.get("topic")
    topic = edrop.get_topic(topic_name)
    if not topic:
      params = {'topic': topic_name, 'notfound': 1}
      self.redirect('/create?' + urllib.urlencode(params))
      return

    order = self.request.get("order")
    if order not in ("-created_at", "-influence"):
      order = "-created_at"

    messages = []
    try:
      raise datastore_errors.NeedIndexError()
      tweets = topic.tweets.order(order).fetch(10)
    except datastore_errors.NeedIndexError:
      tweets = topic.tweets.fetch(10)
      messages.append("""These results are unsorted because indexes are currently
      unavailable.""")

    template_values = {
        'title': topic_name,
        'messages': messages,
        'template': 'show.html',
        'tweets': tweets,
        'topic': topic,
        'url': show_topic_url(topic_name)
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/base.html')
    self.response.out.write(template.render(path, template_values))

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

application = webapp.WSGIApplication([
  ('/', Main),
  ('/show', Show),
  ('/create', Create)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
