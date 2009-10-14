#!/usr/bin/env python

"""Model classes and utility functions."""

from google.appengine.ext import db
from django.utils.simplejson import decoder
from google.appengine.api import datastore_errors

from datetime import datetime

import re
import operator
import math
import logging

DAY_SCALE = 4
LOCAL_EPOCH = datetime(2009, 7, 12)

URL_RE = re.compile(u"""http://\S+""", re.UNICODE)
SPLIT_RE = re.compile(u"""[\s.,"\u2026\u3001\u3002?]+""", re.UNICODE)

class Batch(db.Model):
  """Represents the JSON string from the Twitter public timeline.

  Properties
    data: JSON from the public timeline.
    created_at: Timestamp for this batch.
  """
  data = db.TextProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)

class Tweet(db.Model):
  """Represents a Tweet.

  Properties
    content: Text content of the tweet.
    created_at: When Twitter created the Tweet.
    pic_url: Link to the author's profile picture.
    source_id: Tweet ID in Twitter.
    topics: Topics associated with this Tweet.
    influence: A calculated score based on the number of followers and when
      the Tweet was added.
  """
  content = db.StringProperty(multiline=True)
  created_at = db.DateTimeProperty()
  pic_url = db.LinkProperty()
  author = db.StringProperty()
  source_id = db.StringProperty()
  topics = db.ListProperty(db.Key)
  influence = db.StringProperty()

  def source_url(self):
    """Returns the URL of the Tweet.

    Returns
      A link to the Tweet based on the ID and author.
    """
    return "http://twitter.com/%s/statuses/%s" % (self.author, self.source_id)

  def from_batch(batch):
    """Return a list of Tweets from a Batch.

    Parameters
      batch: A Batch object.
    Returns
      A list of Tweets converted from items in the Batch.
    """
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
  """A Topic which users can introduce to e-drop, and which Tweets can be
  associated with.

  Properties
    name: Name of the topic.
    created_at: When the topic was created.
    creator: The User who created the topic. Can be None.
    score: A ranking property, yet unused.
  """
  name = db.StringProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)
  creator = db.UserProperty()
  score = db.IntegerProperty(default=0)

  @property
  def tweets(self):
    """Returns Tweets associated with this topic.

    Returns
      A list of Tweets.
    """
    return Tweet.all().filter("topics =", self.key())

  def create_path(tokens):
    """Static method which creates a tuple representing the path from a root
    topic to a leaf. For example, the multiword topic "hello world", when
    converted to a path, becomes a tree with a root "hello" and child "world".
    This path is represented in the tuple ("Topic", "hello", "Topic", "world").

    Parameters
      tokens: List of words in the topic. Can be just one word.
    Returns
      A tuple representing the path.
    """
    parentcount = len(tokens) - 1
    prefixes = parentcount * ('parent:',) + ('key:',)
    keynames = map(operator.add, prefixes, tokens)
    return sum(zip(len(tokens) * ('Topic',), keynames), ())
  create_path = staticmethod(create_path)

  def from_tokens(tokens, **kwargs):
    """Builds a Topic from a list of words. A topic which has many words is
    stored as a tree of single words tokenized from the topic.

    Parameters
      tokens: The topic as a list of words.
    Returns
      The Topic object with parent set from the list of words.
    """
    if isinstance(tokens, str):
      tokens = [tokens]

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
    """Tokenizes the phrase.

    Parameters
      phrase: One or more words.
    Returns
      List of words.
    """
    phrase = phrase.lower()
    urls = URL_RE.findall(phrase)
    phrase = URL_RE.sub('', phrase)

    words = SPLIT_RE.split(phrase)
    words = filter(lambda word: word, words)
    return words + urls
  tokenize = staticmethod(tokenize)

class Settings(db.Model):
  value = db.StringProperty(required=True)

def parse_created_at(created_at):
  """Takes a date string and parses it to a DateTime object.

  Parameters
    created_at: String representation of a date.
  Returns
    DateTime object.
  """
  created_at_notz = created_at[:19] + created_at[25:]
  return datetime.strptime(created_at_notz, "%a %b %d %H:%M:%S %Y")
