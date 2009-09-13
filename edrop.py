#!/usr/bin/env python

from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api import datastore_errors

from models import *

import re
import time
import math
import datetime
import logging

DAY_SCALE = 4
LOCAL_EPOCH = datetime.datetime(2009, 7, 12)
URL_RE = re.compile(u"""http://\S+""", re.UNICODE)
SPLIT_RE = re.compile(u"""[\s.,"\u2026?]+""", re.UNICODE)

def extract_tweets(batch):
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

def expire_cache(key=None):
  if not key:
    result = memcache.flush_all()
  else:
    result = memcache.delete(key, namespace="topic")
  return result
