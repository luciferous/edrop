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

from models import *

import edrop
import wsgiref.handlers
import logging
import re
import time

URL_RE = re.compile(u"""http://\S+""", re.UNICODE)
SPLIT_RE = re.compile(u"""[\s.,"\u2026?]+""", re.UNICODE)

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

    ontopic = set()
    topic_tweets = []
    phrases = dict()
    tweets = edrop.extract_tweets(batch)

    word_tweet = dict()
    tweet_words = dict()
    for tweet in tweets:
      text = tweet.content.lower()

      urls = URL_RE.findall(text)
      text = URL_RE.sub('', text)

      words = SPLIT_RE.split(text)
      words = filter(lambda word: word, words)

      tweet_words[tweet] = words + urls

      for word in set(words):
        if word not in word_tweet:
          word_tweet[word] = []
        word_tweet[word].append(tweet)

    keynames = word_tweet.keys()
    parents = dict(zip(
      keynames,
      Topic.get_by_key_name(map(lambda key: 'parent:' + key, keynames))
      ))

    solitary = dict(zip(
      keynames,
      Topic.get_by_key_name(map(lambda key: 'key:' + key, keynames))
      ))

    tweets_by_topic = {}
    keys = []

    for word in keynames:
      if solitary[word]:
        tweets_by_topic[word] = word_tweet[word]
        args = ('Topic', 'key:' + word)
        keys.append(db.Key.from_path(*args))

      if parents[word]:
        for tweet in word_tweet[word]:
          words = tweet_words[tweet]
          slice = words[words.index(word):]
          for index in range(len(slice)):
            pieces = slice[:index + 1]
            ancestors = []
            if len(pieces) > 1:
              ancestors = pieces[:-1]
            args = zip(
                ('Topic',) * len(pieces),
                map(lambda anc: 'parent:' + anc, ancestors) + \
                    ['key:' + pieces[-1]]
                )
            args = sum(args, ())
            topic_name = ' '.join(pieces)
            if topic_name not in tweets_by_topic:
              tweets_by_topic[topic_name] = []
            tweets_by_topic[topic_name].append(tweet)
            keys.append(db.Key.from_path(*args))

    for topic in db.get(keys):
      if not topic:
        continue
      tweets = tweets_by_topic[topic.name]
      for tweet in tweets:
        tweet.topics.append(topic.key())
      ontopic.update(tweets)

    batch.delete()
    db.put(ontopic)

class ExpireCache(webapp.RequestHandler):
  def get(self):
    key = self.request.get("key")
    result = edrop.expire_cache(key)

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

    tokens = SPLIT_RE.split(topic.name)
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

application = webapp.WSGIApplication([
  ('/tasks/queuefetch', QueueFetch),
  ('/tasks/fetch', Fetch),
  ('/tasks/etl', ETL),
  ('/tasks/expirecache', ExpireCache),
  ('/tasks/converttopics', ConvertTopics),
  ('/tasks/linktweets', LinkTweets)
], debug=True)

def main():
  wsgiref.handlers.CGIHandler().run(application)

if __name__ == '__main__':
  main()
