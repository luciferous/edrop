#!/usr/bin/env python

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import datastore_errors
from django.utils import simplejson

from models import *

import os
import wsgiref.handlers
import re
import urllib
import logging

NAME_RE = re.compile("@(\w+)")

class TopicTruncate(webapp.RequestHandler):

  def get(self, topic_name, format='html'):
    """Retrieve an HTML page of tweets."""
    topic_name = urllib.unquote(topic_name)
    topic_name = topic_name.decode('utf8')

    tokens = Topic.tokenize(topic_name)
    path = Topic.create_path(tokens)
    topic = Topic.get(db.Key.from_path(*path))

    if not topic:
      self.error(404)
      return

    tweets = topic.tweets.order("created_at").fetch(50)
    db.delete(tweets)

class TopicDetail(webapp.RequestHandler):
  """Handles list of tweets in a topic."""

  def get(self, topic_name, format='html'):
    """Retrieve an HTML page of tweets."""
    topic_name = urllib.unquote(topic_name)
    topic_name = topic_name.decode('utf8')
    order = self.request.get("order") or "-created_at"

    tokens = Topic.tokenize(topic_name)
    path = Topic.create_path(tokens)
    topic = Topic.get(db.Key.from_path(*path))

    if not topic:
      self.error(404)
      return

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
        'request_path': self.request.path,
        'new_topic': (datetime.now() - topic.created_at).seconds < 360,
        }

    def render_html(template_values):
      for tweet in template_values['tweets']:
        tweet.content = NAME_RE.sub(
            lambda m: '<a href="http://twitter.com/%s">@%s</a>' % (m.groups() * 2),
            tweet.content
            )
      path = os.path.join(os.path.dirname(__file__), 'templates/show.html')
      return template.render(path, template_values)

    def render_json(template_values):
      if template_values['topic'] is None:
        self.error(404)
        return
      self.response.headers['Content-Type'] = 'application/json'
      items = []
      for tweet in template_values['tweets']:
        item = {}
        items.append(item)
        for property in tweet.properties():
          if property in ['topics', 'influence']:
            continue
          if 'created_at' == property:
            item[property] = tweet.created_at.isoformat() + 'Z'
          else:
            item[property] = unicode(getattr(tweet, property))
        item['source_url'] = tweet.source_url()
      return simplejson.dumps(items)

    def render_xml(template_values):
      if template_values['topic'] is None:
        self.error(404)
        return
      self.response.headers['Content-Type'] = 'application/rss+xml'
      path = os.path.join(os.path.dirname(__file__), 'templates/show.rss')
      return template.render(path, template_values)

    formats = {
        'html': render_html,
        'json': render_json,
        'rss': render_xml,
        }

    if format not in formats:
      self.error(404)
      return

    self.response.out.write(formats[format](template_values))

class TopicIndex(webapp.RequestHandler):
  """Handles request to create topics."""

  def get(self):
    """TODO: show an index of topics."""
    self.error(404) # Nothing here yet

  def post(self):
    """Add a new topic."""
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
  """Handles the front page and search functionality."""

  def get(self):
    """Retrieve HTML for a search form and most recent tweets."""
    tweets = Tweet.all().order("-created_at").fetch(5)
    template_values = {
        'title': 'edrop',
        'tweets': tweets,
        'is_front': True,
        }
    path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
    self.response.out.write(template.render(path, template_values))

  def post(self):
    """Returns results based on the search term."""
    # TODO
    #topic_name = self.request.get('name')
    #topic_name = topic_name.strip()
    self.error(404)

class SettingsHandler(webapp.RequestHandler):
  """Handles requests to set settings."""

  def get(self, name):
    """Displays a form for setting."""
    setting = Settings.get_by_key_name('key:' + name)
    current_value = ""
    if setting:
      current_value = setting.value
    self.response.out.write("""<html><body>
        <form action="%s" method="POST">
          %s: <input name="value" type="text" size="20" value="%s">
          <input type="submit" value="Update">
        </form>
      </body>
    </html>""" % (self.request.path, name, current_value))

  def post(self, name):
    """Records a value for the setting."""
    setting = Settings(
        key_name='key:' + name,
        value=self.request.get('value')
        ).put()
    if setting:
      logging.info("Setting %s changed.")
      self.redirect(self.request.path)

application = webapp.WSGIApplication([
  ('/', Main),
  ('/topics/', TopicIndex),
  ('/topics/(.+)/truncate', TopicTruncate),
  ('/topics/(.+)\.(\w+)', TopicDetail),
  ('/topics/(.+)', TopicDetail),
  ('/settings/(\w+)', SettingsHandler),
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
