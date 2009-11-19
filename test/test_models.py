import unittest
import logging
import pickle

from models import Topic, Tweet, Batch
from models import int_to_uni, uni_to_int
from google.appengine.ext import db
from google.appengine.api import apiproxy_stub_map
from datetime import datetime, timedelta

class TestModels(unittest.TestCase):

  def test_tokenizer(self):
    # Empty string
    self.assertEqual(Topic.tokenize(""), [])
    # One word
    self.assertEqual(Topic.tokenize("foo"), ["foo"])
    # Two words
    self.assertEqual(Topic.tokenize("foo bar"), ["foo", "bar"])
    # Punctuation
    self.assertEqual(Topic.tokenize("hello, world"), ["hello", "world"])
    self.assertEqual(Topic.tokenize("hello, world!"), ["hello", "world!"])
    # URLs
    self.assertEqual(
        Topic.tokenize("an URL: http://e-drop.appspot.com"),
        ["an", "url:", "http://e-drop.appspot.com"]
        )

  def test_topic_maker(self):
    tokens = Topic.tokenize("deus ex machina")
    topics = Topic.from_tokens(tokens)

    self.assertEqual(topics[0].name, "deus")
    self.assertEqual(topics[1].name, "ex")
    # Only the leaf has the full phrase as its name
    self.assertEqual(topics[2].name, "deus ex machina")

    self.assertTrue(topics[0].parent() is None)
    self.assertEqual(topics[1].parent(), topics[0])
    self.assertEqual(topics[2].parent(), topics[1])

    self.failIf(topics[0].is_saved() or topics[0].is_saved())

    db.put(Topic.from_tokens(Topic.tokenize("of montreal")))
    db.put(Topic.from_tokens(Topic.tokenize("time of day")))

    ofmontreal, tod = Topic.gql(
        "WHERE name IN :1",
        ["of montreal", "time of day"]
        )

    self.assertEqual(ofmontreal.parent().name, "of")
    self.assertEqual(tod.parent().name, "of")
    self.assertNotEqual(str(tod.parent_key()), str(ofmontreal.parent_key()))

  def test_link_topics(self):
    tweet = Tweet(content="His name is Robert Paulson")
    topics = Topic.link_topics(tweet)

    topic_names = [topic.name for topic in topics.keys()]
    self.assertTrue("name" in topic_names)
    self.assertTrue("robert paulson" in topic_names)

  def test_multiple_first_word(self):
    tweet = Tweet(content="Like father, like son")
    topics = Topic.link_topics(tweet)
    topic_names = [topic.name for topic in topics.keys()]

    self.assertTrue("like son" in topic_names)

  def test_unicode_storage(self):
    for n in range(65535):
      self.assertEquals(uni_to_int(int_to_uni(n)), n)

  def test_activity(self):
    topic_nodes = Topic.from_tokens("activity_test_topic")
    db.put(topic_nodes)
    topic = topic_nodes[-1]

    epoch = datetime(2009, 7, 12)
    topic.set_activity(1, _now=epoch)
    self.assertEqual(topic.get_activity(_now=epoch), 1)

    topic.set_activity(2, _now=epoch + timedelta(4))
    self.assertEqual(topic.get_activity(_now=epoch + timedelta(4)), 2)

    topic.set_activity(3, _now=epoch + timedelta(800))
    self.assertEqual(topic.get_activity(_now=epoch + timedelta(800)), 3)

    def before_epoch(topic):
      topic.set_activity(6500, _now=epoch - timedelta(1))
    self.assertRaises(ValueError, before_epoch, topic)

    db.delete(topic_nodes)

  def test_activity_order(self):
    # Create topics
    ramen_nodes = Topic.from_tokens("ramen")
    varelse_nodes = Topic.from_tokens("varelse")
    db.put(ramen_nodes + varelse_nodes)
    # Just take the leaf nodes
    ramen, varelse = ramen_nodes[-1], varelse_nodes[-1]

    # Set an artificial epoch
    epoch = datetime(2009, 7, 12)

    # New topics should have no history
    self.assertEqual(ramen.get_activity(_now=epoch), 0)
    self.assertEqual(varelse.get_activity(_now=epoch), 0)

    # Day 0, Batch 0
    ramen.set_activity(5, _now=epoch)
    ramen.put()
    self.assertEqual(ramen.name, Topic.all().order("-activity").get().name)

    # Day 0, Batch 7
    varelse.set_activity(2, _now=epoch + timedelta(0, 60 * 7))
    varelse.put()
    self.assertEqual(ramen.name, Topic.all().order("-activity").get().name)

    # Day 1, Batch 0
    varelse.set_activity(2, _now=epoch + timedelta(1))
    varelse.put()
    self.assertEqual(varelse.name, Topic.all().order("-activity").get().name)

  def test_batch(self):
    items = []
    items.append({
        "text": "His name is Robert Paulson",
        "created_at": "Mon Aug 10 21:24:24 +0000 2009",
        "id": 1234,
        "user": {
          "profile_image_url": "http://example.com/",
          "screen_name": "Jack",
          "followers_count": 100,
          "friends_count": 100,
          }
        })

    key = Batch(pickled_items=pickle.dumps(items)).put()
    tweets = Tweet.from_batch(Batch.get(key))

    self.assertEqual(1, len(tweets))
    self.assertEqual("His name is Robert Paulson", tweets[0].content)

    db.delete(key)

  def setUp(self):
    # Multiword topics are a linked nodes, i.e., robert => paulson
    nodes = Topic.from_tokens(Topic.tokenize("Robert Paulson"))
    db.put(nodes)
    nodes = Topic.from_tokens(Topic.tokenize("like son"))
    db.put(nodes)

    # Single word topic
    single = Topic.from_tokens("name")
    db.put(single)

  def tearDown(self):
    nodes = Topic.from_tokens(Topic.tokenize("Robert Paulson"))
    # Can delete all nodes because we know what's been created. In a real case
    # we should check each node for children before deleting.
    db.delete(nodes)

    db.delete(Topic.from_tokens(Topic.tokenize("like son")))

    db.delete(Topic.from_tokens("name"))

if __name__ == '__main__':
  unittest.main()
