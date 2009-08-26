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

  def source_url(self):
    return "http://twitter.com/%s/statuses/%s" % (self.author, self.source_id)

class Topic(db.Model):
  name = db.StringProperty()

class TweetTopic(db.Model):
  tweet = db.ReferenceProperty(Tweet)

def next_batch():
  query = Batch.gql("ORDER BY created_at ASC")
  return query.get()

def commit_batch_topics(batch, tweettopics):
  if (len(tweettopics) > 0):
    db.put(tweettopics)
  batch.delete()

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
                  source_id=str(item['id']))
    tweets.append(tweet)
  return tweets

def parse_created_at(created_at):
  created_at_notz = created_at[:19] + created_at[25:]
  return datetime.strptime(created_at_notz, "%a %b %d %H:%M:%S %Y")
