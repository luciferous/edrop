import unittest
from models import Topic, Tweet
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

if __name__ == '__main__':
  unittest.main()
