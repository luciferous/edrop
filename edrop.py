#!/usr/bin/env python

from google.appengine.api import memcache
from google.appengine.api import users

from models import *

import re
import time
import math
import datetime
import logging

DAY_SCALE = 4
LOCAL_EPOCH = datetime.datetime(2009, 7, 12)

def extract_tweets(batch):
  dec = decoder.JSONDecoder()
  feed = dec.decode(batch.data)
  tweets = []
  for item in feed:
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
    except BadValueError, e:
      logging.error("Error saving tweet %d from %s: %s." %
          (item['id'], item['user']['screen_name'], e.message)
          )

  return tweets

def find_topics(tweet):
  topics = []
  words = re.findall("\w+", tweet.content, re.UNICODE)
  for topic_name in set([w.lower() for w in words]):
    topic = get_topic(topic_name)
    if topic:
      topics.append(topic)
  return topics

def get_topic(name):
  name = name.lower().strip()
  tuple = memcache.get(name, namespace="topic")
  if tuple:
    return tuple[1]

  topic = Topic.gql("WHERE name = :1", name).get()
  memcache.set(name, (name, topic), namespace="topic")

  return topic

def create_topic(name):
  name = name.lower().strip()
  tuple = memcache.get(name, namespace="topic")
  if tuple and tuple[1]:
    return tuple[1]

  topic = Topic.get_or_insert(
      "key:" + name,
      name=name,
      user=users.get_current_user()
      )
  memcache.set(name, (name, topic), namespace="topic")

  return topic

def expire_cache(key=None):
  if not key:
    result = memcache.flush_all()
  else:
    result = memcache.delete(key, namespace="topic")
  return result
