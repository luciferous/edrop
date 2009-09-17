#!/usr/bin/env python

"""
We want to strip branches from the tree that don't match the parent. But to
do that we need to get_by_key_name which will return a list of topics, or
None. We can strip away the branches of topics that returned None.

For instance:
If we have a tweet "all your base are belong to us", the possible phrases
stripped from that would be:

"all"
"all your"
"all your base"
...
"belong to us"
"belong to"
"belong"
"to us"
"us"

If we search the datastore for "all" and it returns None. Then we can strip
every phrase beginning with "all". If we do this for every topic with a
child, we can significantly cut down the size of the tree at the cost of
more datastore calls.

This requires each multi-word topic to be stored in a linked list.
Currently topics are stored: "key:all your base are belong to us". Since we
can only call db.get() with multiple Keys and not multiple Queries, we must
modify how we store topics.

"all your base are belong to us" must be stored as separate topics:

"all"
"your"
"base"
"are"
"belong"
"to"
"us"

"all" must reference "your", "your" must reference "base" and so on.

Because there may be other multi-word topics beginning with "all", the
cardinality of the relationship between topics is one-to-many.
We can represent this relationship using the ancestor component in
datastore, as entities can only have one ancestor. We can also represent
this relationship using a Reference property, but we will run into some
trouble as I will describe.

If we set "all" as the ancestor of "your" then we can query "your":

key = Key.from_path('Topic', 'all', 'Topic', 'your')
Topic.get(key)

>>> <Topic: your>

We can create many keys and query them in one shot:

keys = [Key.from_path..., Key.from_path...]
Topic.get(keys)

>>> [<Topic...>, <Topic...>]

If we have another phrase containing "base" in the datastore, then we have
two topics with the same key name. If we are using the ancestor property,
then we preserve the uniqueness of the key, but if we are using a Reference
property, we will have to change the key name to differentiate between the
two topics.

If we create topics for every word in the topic, we may have
non-interesting topics like "all", "are", "your". One way to get around
this is to store a property that tells edrop if a topic is just used as a
parent for another topic. But, that would mean having to go through all the
results of get() programmatically filtering out topics. Another way to do
this is to change the key prefix. Currently all keynames are prefixed with
'key:'. We can change this to 'parent:'. That means we could have topics
with the same name but different keys in the datastore. Whether this is a
bad thing is not clear right now.

"""

from google.appengine.ext import webapp
from google.appengine.api import urlfetch
from google.appengine.api import urlfetch_errors
from google.appengine.api.labs import taskqueue
from google.appengine.api import memcache

from models import *

import wsgiref.handlers
import logging
import re
import time

class QueueFetch(webapp.RequestHandler):
  def get(self):
    url = "http://twitter.com/statuses/public_timeline.json"
    task = taskqueue.Task(
        url='/tasks/fetch',
        params={'url': url}
        )
    task.add('fetch')

class Fetch(webapp.RequestHandler):
  def post(self):
    url = self.request.get('url')
    try:
      response = urlfetch.fetch(url)
      if response.status_code == 200 and response.content.startswith("["):
        key = Batch(data=response.content).put()
        if key:
          taskqueue.Task(
              url='/tasks/etl',
              params={'batch_id': key.id()}
              ).add('etl')
    except urlfetch_errors.DownloadError, e:
      logging.info("Twitter responded too slowly. %s" % e.message)

class ETL(webapp.RequestHandler):
  def post(self):
    try:
      id = self.request.get('batch_id')
      batch = Batch.get_by_id(long(id))
    except ValueError:
      # Flush tasks with bad batch ids
      self.response.set_status(200)
      return

    if not batch:
      logging.warning("Batch not found %s." % id)
      self.error(400)
      return

    tweets_by_word = {}
    words_in_tweet = {}
    tweets = Tweet.from_batch(batch)

    for tweet in tweets:
      words_in_tweet[tweet] = Topic.tokenize(tweet.content)
      for word in set(words_in_tweet[tweet]):
        if word not in tweets_by_word:
          tweets_by_word[word] = []
        tweets_by_word[word].append(tweet)

    words = tweets_by_word.keys()
    parenttopics = Topic.get_by_key_name(['parent:' + word for word in words])
    begins_a_phrase = dict(zip(words, parenttopics))
    keys = []
    for word in words:
      keys.append(db.Key.from_path(*Topic.create_path([word])))

      if not begins_a_phrase[word]:
        continue

      memo = {}
      tweets = tweets_by_word[word]
      for tweet in tweets:
        start = words_in_tweet[tweet].index(word)
        slice = words_in_tweet[tweet][start:]
        for index in range(len(slice)):
          if index == 0:
            continue
          pieces = slice[:index + 1]
          path = Topic.create_path(pieces)
          keys.append(db.Key.from_path(*path))

          topic_name = ' '.join(pieces)

          if topic_name not in memo:
            memo[topic_name] = []
          memo[topic_name].append(tweet)

        tweets_by_word.update(memo)

    ontopic = set()
    for topic in [topic for topic in Topic.get(keys) if topic]:
      tweets = tweets_by_word[topic.name]
      for tweet in tweets:
        tweet.topics.append(topic.key())
      ontopic.update(tweets)

    batch.delete()
    db.put(ontopic)

class ExpireCache(webapp.RequestHandler):
  def get(self):
    key = self.request.get("key")
    if not key:
      result = memcache.flush_all()
    else:
      result = memcache.delete(key, namespace="topic")

class ConvertTopics(webapp.RequestHandler):
  def get(self):
    key = self.request.get('key')
    if key:
      topic = Topic.gql(
          "WHERE __key__ > :1 ORDER by __key__",
          db.Key(key)
          ).get()
    else:
      topic = Topic.gql("ORDER by __key__").get()

    if not topic:
      return

    tokens = Topic.tokenize(topic.name)
    if len(tokens) > 1:
      topics = Topic.from_tokens(tokens, created_at=topic.created_at)
      keys = db.put(topics)
      logging.info(
          "Converted %s: %s.",
          topic.name,
          ', '.join([key.name() for key in keys])
          )
      old, new = topic, topics[-1]
      taskqueue.add(
          url='/tasks/linktweets',
          params={'old': str(old.key()), 'new': str(new.key())},
          method='GET'
          )
    taskqueue.add(
        url='/tasks/converttopics',
        params={'key': str(topic.key())},
        method='GET'
        )

class LinkTweets(webapp.RequestHandler):
  def get(self):
    old, new = self.request.get('old'), self.request.get('new')
    oldkey, newkey = db.Key(old), db.Key(new)
    if not (oldkey and newkey):
      logging.error("Error processing topics: %s." % \
                    str([oldkey.name(), newkey.name()]))
      return

    tweets = Tweet.all().filter("topics =", oldkey)
    modified = []
    for tweet in tweets:
      tweet.topics.remove(oldkey)
      tweet.topics.append(newkey)
      logging.info("Tweet %s: %s => %s." % \
                    (str(tweet.key().id_or_name()),
                    oldkey.name(),
                    newkey.name())
                  )
      modified.append(tweet)
    keys = db.put(modified)
    db.delete(oldkey)

class FullName(webapp.RequestHandler):
  def get(self):
    key = self.request.get('key')
    if key:
      topic = Topic.gql(
          "WHERE __key__ > :1 ORDER by __key__",
          db.Key(key)
          ).get()
    else:
      topic = Topic.gql("ORDER by __key__").get()

    if not topic:
      return
    parentnames = []

    if topic.parent():
      current = topic
      parentnames.append(current.name)
      while current.parent():
        parentnames.append(current.parent().name)
        current = current.parent()
      parentnames.reverse()
      topic.name = ' '.join(parentnames)
      topic.save()

    taskqueue.add(
        url='/tasks/fullname',
        params={'key': str(topic.key())},
        method='GET'
        )

application = webapp.WSGIApplication([
  ('/tasks/queuefetch', QueueFetch),
  ('/tasks/fetch', Fetch),
  ('/tasks/etl', ETL),
  ('/tasks/expirecache', ExpireCache),
  ('/tasks/converttopics', ConvertTopics),
  ('/tasks/linktweets', LinkTweets),
  ('/tasks/fullname', FullName)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
