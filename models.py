#!/usr/bin/env python

from google.appengine.ext import db
from django.utils.simplejson import decoder

from datetime import datetime

class Batch(db.Model):
  data = db.TextProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)

class Tweet(db.Model):
  content = db.StringProperty(multiline=True)
  created_at = db.DateTimeProperty()
  pic_url = db.LinkProperty()
  author = db.StringProperty()
  source_id = db.StringProperty()
  topics = db.ListProperty(db.Key)

  def source_url(self):
    return "http://twitter.com/%s/statuses/%s" % (self.author, self.source_id)

class Topic(db.Model):
  name = db.StringProperty()

  @property
  def tweets(self):
    return Tweet.all().filter("topics =", self.key())

def next_batch():
  query = Batch.gql("ORDER BY created_at ASC")
  return query.get()

def parse_created_at(created_at):
  created_at_notz = created_at[:19] + created_at[25:]
  return datetime.strptime(created_at_notz, "%a %b %d %H:%M:%S %Y")
