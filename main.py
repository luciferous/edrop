#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch

from models import *
import edrop

import os
import wsgiref.handlers

class Fetch(webapp.RequestHandler):
  def get(self):
    url = "http://twitter.com/statuses/public_timeline.json"
    response = urlfetch.fetch(url)

    if (response.status_code == 200):
      if response.content.startswith("["):
        batch = Batch(data=response.content)
        batch.save()
        self.redirect("/extract")

class Extract(webapp.RequestHandler):
  def get(self):
    batch = next_batch()
    if not batch:
      return
    tweets = extract_tweets(batch)
    edrop.tag_with_topics(tweets)
    batch.delete()
    db.save(tweets)

class Create(webapp.RequestHandler):
  def get(self):
    topic_name = self.request.get("topic")
    topic = Topic.gql("WHERE name = :1", topic_name).get()
    if not topic:
      topic = edrop.create_topic(topic_name)

class Display(webapp.RequestHandler):
  def get(self):
    topic_name = self.request.get("topic")
    query = Topic.gql("WHERE name = :1", topic_name)
    topic = query.get()
    if not topic:
      self.response.out.write("None")
    else:
      tweets = topic.tweets.fetch(10)
      template_values = { 'topic': topic, 'tweets': tweets }
      path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
      self.response.out.write(template.render(path, template_values))


class Welcome(webapp.RequestHandler):
  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
    self.response.out.write(template.render(path, template_values))

application = webapp.WSGIApplication([
  ('/', Welcome),
  ('/display', Display),
  ('/fetch', Fetch),
  ('/extract', Extract),
  ('/create', Create)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
