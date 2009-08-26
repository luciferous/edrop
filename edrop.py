#!/usr/bin/env python

from google.appengine.api import memcache

from models import *

import re
import time

def create_tweet_topics(tweets):
  tweettopics = []
  alpha_re = re.compile("\w+")

  for tweet in tweets:
    paired = []
    tokens = alpha_re.findall(tweet.content)
    for token in tokens:
      token = token.lower()
      topic = get_topic(token)
      if topic and topic not in paired:
        key = "%s|%d" % (token, time.mktime(tweet.created_at.timetuple()))
        tweettopics.append(TweetTopic(key_name=key,parent=topic, tweet=tweet))
        paired.append(topic)

  return tweettopics

def get_topic(name):
  tokentopic = memcache.get(name, namespace="topic")
  if tokentopic is not None:
    return tokentopic[1]

  querytopic = Topic.gql("WHERE name = :1", name, keys_only=True)
  topic = querytopic.get()
  memcache.set(name, (name, topic), namespace="topic")

  return topic

def create_topic(name):
  tokentopic = memcache.get(name, namespace="topic")
  if tokentopic is not None and tokentopic[1] is not None:
    return

  topic = Topic.get_or_insert("key:" + name, name=name)
  memcache.set(name, (name, topic), namespace="topic")

  return topic
