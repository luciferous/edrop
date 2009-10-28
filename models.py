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
    activity: Can be decoded to determine how active a topic is.
  """
  name = db.StringProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)
  creator = db.UserProperty()
  score = db.IntegerProperty(default=0)
  activity = db.StringProperty(default=chr(0) * 60, multiline=True)

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

  def link_topics(tweets):
    if isinstance(tweets, Tweet):
      tweets = [tweets]

    tweets_by_word = {}
    words_in_tweet = {}

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
        tokens = words_in_tweet[tweet]
        while word in tokens:
          start = tokens.index(word)
          slice = tokens[start:]
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
          tokens = tokens[start + 1:]

        tweets_by_word.update(memo)

    tweets_per_topic = {}
    topics = [topic for topic in Topic.get(keys) if topic]
    for topic in topics:
      tweets_per_topic[topic] = tweets_by_word[topic.name]
      for tweet in tweets_per_topic[topic]:
        tweet.topics.append(topic.key())

    return tweets_per_topic
  link_topics = staticmethod(link_topics)

  def get_activity(self, _now=datetime.now()):
    """Returns the activity of a topic.

    Returns
      The activity value.
      """
    length = len(self.activity) - 1
    offset = uni_to_int(self.activity[0])
    day = (_now - LOCAL_EPOCH).days
    index = length - (day - offset)

    if 0 <= index < len(self.activity):
      return uni_to_int(self.activity[index])

  def set_activity(self, activity, _now=datetime.now()):
    """Set the activity of a topic, optionally specifying a date.

    Activity is a measure of how frequently a topic is mentioned per day.
    After capturing a series of frequencies, it is easy to tell if a topic is
    interesting by measuring the activity change over consecutive samples.

    The series of activity samples is stored as a unicode string of unicode
    characters. In each character is encoded a number in range(65536). This
    structure is ordered so that the oldest sample is the last character (i.e.,
    frequencies[-1]), and the most recent sample is second character(i.e.,
    frequencies[1]). The first character is used to determine how many days the
    oldest sample is from the local epoch. Without it, it's impossible to know
    determine the index position of the activity for any day after epoch +
    timedelta(60).

    Because the sample length is fixed, when the newest data overwrites the
    oldest data. Think of a fixed-length linked list instead of a circular
    buffer, or imagine a window sliding left over a series of samples.

    Parameters
      activity: The activity value.
      _now: Date to store the activity for.
    Returns
      None
    """
    offset = uni_to_int(self.activity[0])
    day = (_now - LOCAL_EPOCH).days

    index = day - offset
    payload_char_length = len(self.activity) - 1
    if index < 0: # This case is only possible in testing.
      raise ValueError("Can only store values after offset, not before.")
    elif 0 <= index < payload_char_length:
      index = payload_char_length - index
      self.activity = self.activity[:index] + \
          int_to_uni(activity) + self.activity[index + 1:]
    else:
      newoffset = index - payload_char_length + 1
      shift = min(newoffset, payload_char_length)
      self.activity = int_to_uni(newoffset + offset) + \
          chr(0) * shift + self.activity[1:-shift]
      self.activity = self.activity[:1] + \
          int_to_uni(activity) + self.activity[2:]

def int_to_uni(number):
  """Converts an integer into a unicode character.

  The integer is encoded into a UTF-8 byte sequence, which is then decoded into
  a single unicode character. UTF-8 is an 8-bit encoding, where each byte in a
  the sequence consists of two parts: Marker bits (the most significant bits)
  and payload bits.

    Range                      Encoding
    U-00000000 ... U-0000007F  0xxxxxxx
    U-00000080 ... U-000007FF  110xxxxx 10xxxxxx
    U-00000800 ... U-0000FFFF  1110xxxx 10xxxxxx 10xxxxxx
    ...                        ...

  The least significant bit of the Unicode character is the rightmost x bit.

  Read more about UTF-8 at
  http://docs.python.org/library/codecs.html#encodings-and-unicode.

  The reason for using UTF-8 is because the version of the Python runtime on
  App Engine is 2.5.2 which has problems with some unicode characters.

  Encoding works:

    >>> u"\ud800".encode('utf-16')
    '\xff\xfe\x00\xd8'

  But decoding fails:

    >>> '\xff\xfe\x00\xd8'.decode('utf-16')
    Traceback...
    UnicodeDecodeError: 'utf16' codec can't decode bytes...

    Parameters
      number: An integer.
    Returns
      A unicode character.
  """
  # Guarantee ushort range.
  if not (0 <= number <= 65535):
    raise OverflowError("number must be in range 0 <= number <= 65535")
  # Numbers up to 127 can be encoded in seven bits.
  if number < 128:
    # No decoding necessary, i.e chr(127) == u"\u007f" returns True.
    return chr(number)
  # Process the six least significant bits and turn on the Marker bits.
  bytes = chr(number & 63 | 128)
  number = number >> 6
  # While the number is too large to be encoded in the Marker byte...
  while number >= 64 >> len(bytes):
    # ... Process six bits and prepend to the bytestring.
    bytes = chr(number & 63 | 128) + bytes
    number = number >> 6
  # Python uses an infinite number of bits to store numbers, and negative
  # numbers have an infinite number of leading ones instead of leading zeroes.
  bytes = chr(number | (-128 >> len(bytes) & 255)) + bytes
  return bytes.decode('utf8')


def uni_to_int(char):
  """Converts an unicode character into an integer.

    Parameters
      char: A unicode character.
    Returns
      A number.
  """
  bytes = [ord(byte) for byte in char.encode('utf8')]
  # For numbers < 128, tail = []
  head, tail = bytes[0], bytes[1:]
  # Extract the payload bits from each byte, shift the result by the necessary
  # amount, and return the sum of the resulting numbers.
  return sum(
      map(
        lambda char, shift: char << shift,
        # When shifted right by the tail length, 127 becomes the complement of
        # the mask for the Marker bits.
        [head & 127 >> len(tail)] + [byte & 63 for byte in tail],
        [24, 18, 12, 6, 0][-len(bytes):]
        )
      )

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
