#!/usr/bin/env python

from google.appengine.ext import db
from django.utils.simplejson import decoder
from google.appengine.api import datastore_errors

from datetime import datetime

import re
import operator
import math

DAY_SCALE = 4
LOCAL_EPOCH = datetime(2009, 7, 12)

URL_RE = re.compile(u"""http://\S+""", re.UNICODE)
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

  def from_batch(batch):
    dec = decoder.JSONDecoder()
    feed = dec.decode(batch.data)
    tweets = []
    for item in feed:
      if item['user']['followers_count'] == 0 or \
         item['user']['friends_count'] == 0:
        continue
      try:
        tweet = Tweet(
            key_name="tweet:%d" % (item['id']),
            content=item['text'],
            created_at=parse_created_at(item['created_at']),
            pic_url=item['user']['profile_image_url'],
            author=item['user']['screen_name'],
            source_id=str(item['id']),
            topics=[]
            )
        days = (tweet.created_at - LOCAL_EPOCH).days
        influence_factor = max(1, item['user']['followers_count'])
        tweet.influence = "%020d|%s" % (
            long(days * DAY_SCALE + math.log(influence_factor)),
            tweet.source_id
            )
        tweets.append(tweet)
      except datastore_errors.BadValueError, e:
        logging.error("Error saving tweet %d from %s: %s." %
            (item['id'], item['user']['screen_name'], e.message)
            )

    return tweets
  from_batch = staticmethod(from_batch)

class Topic(db.Model):
  name = db.StringProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)
  creator = db.UserProperty()
  score = db.IntegerProperty(default=0)

  @property
  def tweets(self):
    return Tweet.all().filter("topics =", self.key())

  def create_path(topic_name):
    words = Topic.tokenize(topic_name)
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

    topics[-1].name = ' '.join(tokens)
    return topics
  from_tokens = staticmethod(from_tokens)

  def tokenize(phrase):
    phrase = phrase.lower()
    urls = URL_RE.findall(phrase)
    phrase = URL_RE.sub('', phrase)

    words = SPLIT_RE.split(phrase)
    words = filter(lambda word: word, words)
    return words + urls
  tokenize = staticmethod(tokenize)

def parse_created_at(created_at):
  created_at_notz = created_at[:19] + created_at[25:]
  return datetime.strptime(created_at_notz, "%a %b %d %H:%M:%S %Y")
