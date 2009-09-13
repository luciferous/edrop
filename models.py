#!/usr/bin/env python

from google.appengine.ext import db
from django.utils.simplejson import decoder

from datetime import datetime

import re
import operator

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

  def from_tokens(tokens, **kwargs):
    parentcount = len(tokens) - 1
    prefixes = parentcount * ('parent:',) + ('key:',)
    keynames = map(operator.add, prefixes, tokens)
    parent = None

    topics = []
    for keyname, name in zip(keynames, tokens):
      topic = Topic.get_by_key_name(keyname)
      if not topic:
        topic = Topic(key_name=keyname, name=name, parent=parent)
        for prop, value in kwargs.items():
          setattr(topic, prop, value)
      parent = topic
      topics.append(topic)

    return topics
  from_tokens = staticmethod(from_tokens)


def parse_created_at(created_at):
  created_at_notz = created_at[:19] + created_at[25:]
  return datetime.strptime(created_at_notz, "%a %b %d %H:%M:%S %Y")
