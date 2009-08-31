#!/usr/bin/env python

from google.appengine.api import memcache

from models import *

import re
import time

def extract_tweets(batch):
  dec = decoder.JSONDecoder()
  feed = dec.decode(batch.data)
  tweets = []
  for item in feed:
    tweet = Tweet(key_name="tweet|%d" % (item['id']),
                  content=item['text'],
                  created_at=parse_created_at(item['created_at']),
                  pic_url=item['user']['profile_image_url'],
                  author=item['user']['screen_name'],
                  source_id=str(item['id']),
                  topics=[])
    tweets.append(tweet)
  return tweets

def find_topics(tweet):
  topics = []
  words = re.findall("\w+", tweet.content)
  for topic_name in set([w.lower() for w in words]):
    topic = get_topic(topic_name)
    if topic:
      topics.append(topic)
  return topics

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

  topic = Topic.gql("WHERE name = :1", name.lower()).get()
  memcache.set(name, (name, topic), namespace="topic")

  return topic

def create_topic(name):
  topic = memcache.get(name, namespace="topic")
  if topic and topic[1]:
    return

  topic = Topic.get_or_insert("key:" + name, name=name)
  memcache.set(name, (name, topic), namespace="topic")

  return topic
