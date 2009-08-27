#!/usr/bin/env python

from google.appengine.api import memcache

from models import *

import re
import time

def tag_with_topics(tweets):
  tweettopics = []
  alpha_re = re.compile("\w+")

  for tweet in tweets:
    names = [word.lower() for word in alpha_re.findall(tweet.content)]
    for topic_name in set(names):
      topic = get_topic(topic_name)
      if topic:
        tweet.topics.append(topic.key())

def get_topic(name):
  topic = memcache.get(name, namespace="topic")
  if topic is not None:
    return topic[1]

  topic = Topic.gql("WHERE name = :1", name).get()
  memcache.set(name, (name, topic), namespace="topic")

  return topic

def create_topic(name):
  topic = memcache.get(name, namespace="topic")
  if topic and topic[1]:
    return

  topic = Topic.get_or_insert("key:" + name, name=name)
  memcache.set(name, (name, topic), namespace="topic")

  return topic
