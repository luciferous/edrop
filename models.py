#!/usr/bin/env python

from google.appengine.ext import db
from django.utils.simplejson import decoder

from datetime import datetime

import re

WORD_RE = re.compile("\w+", re.UNICODE)
SPLIT_RE = re.compile(u"""[\s.,"\u2026?]+""", re.UNICODE)

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
  influence = db.StringProperty()

  def source_url(self):
    return "http://twitter.com/%s/statuses/%s" % (self.author, self.source_id)

class Topic(db.Model):
  name = db.StringProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)
  creator = db.UserProperty()
  score = db.IntegerProperty(default=0)

  @property
  def tweets(self):
    return Tweet.all().filter("topics =", self.key())

  def create_path(topic_name):
    words = SPLIT_RE.split(topic_name.lower())
    ancestors, child = words[:-1], words[-1:][0]
    parent = None
    if ancestors:
      kinds = ['Topic'] * len(ancestors)
      ancestor_keys = map(lambda name: 'parent:' + name, ancestors)
      args = zip(kinds, ancestor_keys)
      args = sum(args, ()) # Flatten
      parent = db.Key.from_path(*args)
    return 'key:' + child, child, parent
  create_path = staticmethod(create_path)

def next_batch():
  query = Batch.gql("ORDER BY created_at ASC")
  return query.get()

def parse_created_at(created_at):
  created_at_notz = created_at[:19] + created_at[25:]
  return datetime.strptime(created_at_notz, "%a %b %d %H:%M:%S %Y")
