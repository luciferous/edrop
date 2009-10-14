import unittest
import logging
from models import Topic, Tweet
from google.appengine.ext import db
from google.appengine.api import apiproxy_stub_map

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
