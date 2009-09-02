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

class Create(webapp.RequestHandler):
  def get(self):
    notfound = self.request.get("notfound")
    topic_name = self.request.get("topic")

    topic = edrop.get_topic(topic_name)
    if topic:
      self.redirect(self.request.path + '/' + topic_name)

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
    self.redirect(self.request.path + '/' + topic_name)

class TopicController(webapp.RequestHandler):
  def get(self):
    pathitems = re.findall(u'/(\w+)*', self.request.path_info)
    if len(pathitems) == 1 or not pathitems[1]:
      topic_name = self.request.get('name')
      # Redirect /topics?name=foo => /topics/foo
      if topic_name:
        self.redirect(self.request.path + '/' + topic_name)
    else:
      self.show(pathitems[1])

  def post(self):
    topic_name = self.request.get("name")
    topic = edrop.get_topic(topic_name)
    if not topic:
      topic = edrop.create_topic(topic_name)
    self.redirect(self.request.path + '/' + topic_name)

  def show(self, topic_name):
    topic = edrop.get_topic(topic_name)
    if not topic:
      self.createtopic(topic_name)
      return
    order = self.request.get("order")
    if order not in ("-created_at", "-influence"):
      order = "-created_at"

    messages = []
    try:
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
        'request_path': self.request.path
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/base.html')
    self.response.out.write(template.render(path, template_values))

  def createtopic(self, topic_name):
    template_values = {
        'title': topic_name,
        'template': 'create.html',
        'topic_name': topic_name,
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
  ('/topics/?.*', TopicController),
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
