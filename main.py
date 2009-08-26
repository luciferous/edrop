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

    query = Topic.gql("WHERE name = :1", "the")
    if (not query.get()):
      t = Topic(name="the")
      t.save()

    tweets = extract_tweets(batch)
    tweettopics = edrop.create_tweet_topics(tweets)

    for tt in tweettopics:
      self.response.out.write("<p><strong>%s</strong>%s</p>" %
          (str(tt.parent), tt.tweet.content))

    batch.delete()
    db.save(tweets)
    db.save(tweettopics)

class Display(webapp.RequestHandler):
  def get(self):
    self.response.out.write(""" <html><head><title>edrop</title></head>
        <body><ul>
          <li><a href="/extract">Extract</a></li>
          <li><a href="/fetch">Fetch</a></li>
          <pre>%s</pre>
        </ul></body></html>""" % str(self))

class Welcome(webapp.RequestHandler):
  def get(self):
    self.response.out.write(""" <html><head><title>edrop</title></head>
        <body><ul>
          <li><a href="/fetch">Fetch</a></li>
          <li><a href="/extract">Extract</a></li>
        </ul></body></html>""")

    #path = os.path.join(os.path.dirname(__file__), 'templates/index.html')
    #self.response.out.write(template.render(path, template_values))

application = webapp.WSGIApplication([
  ('/', Welcome),
  ('/r', Display),
  ('/fetch', Fetch),
  ('/extract', Extract)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
