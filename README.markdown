e-drop
======

e-drop is a simple Twitter feed aggregator.

Overview of e-drop
-----------------

e-drop attempts to match every tweet in the public timeline to topics it has
stored in its database. If no topic matches, then e-drop ignores the tweet,
therby only storing tweets it considers "related". Stored tweets can be
retrieved by the topic to which they are related, so we could retrieve a list
of tweets related to the topic "encino man" for example.

### What are topics and tweets?

A topic is a word or a sequence of words. "Hamburger", "old testament", "lord
of the rings" are all valid topics. A tweet is whatever anyone posts onto
Twitter.

### How are topics and tweets related?

A tweet is related to a topic if the tweet contains the topic. For example, the
tweet "My favorite movie of all time is Encino Man" is related to the topics
"movie", "favorite movie", and "encino man", but not to the topics "music", or
"pit bull".

When e-drop scans the public timeline it matches all the tweets it finds against
its database of topics, and stores the tweets that match, remembering which
tweets and topics match.

How e-drop matches tweets and topics
-----------------------------------

The complexity of matching tweets with topics comes after building a list of
possible topics. Let's take "My favorite movie of all time is Encino Man" as an
example. To match this tweet against topics in the database, we can split it
into tokens: "my", "favorite", "movie", ..., "man".

We can query the datastore:

    Topic.gql("WHERE name = :1", "my")
    Topic.gql("WHERE name = :1", "favorite")
    Topic.gql("WHERE name = :1", "movie")
    # ...
    Topic.gql("WHERE name = :1", "man")

The datastore even allows a list of keys, which would run in one query:

    keys = ["my", "favorite", "movie", ..., "man"] Topic.get(keys)

(In the actual application, we prefix each key name with "key:", and each
ancestor key name with "parent:".)

This takes care of topics of single words, but what about topics comprising
more than one word? If there was topic in the datastore "encino man", none of
the above queries would match. To find multiword topics like "encino man" we
have to break up the tweet into possible multiword tokens, and then query the
datastore for each token.

One strategy to do this is to retrieve the slice of the first word to the
second; then to the third; then fourth; and so on to the end, then slice again
starting with the second word.

    tokens = ["my favorite", "my favorite movie", ..., "favorite movie",
        "favorite movie of", "favorite movie of all", ...]
    # Query the datastore
    Topic.get(tokens)

This works, but for every n words in the tweet, the size of tokens is (n ^ 2 +
n) / 2. If you are interested in this series look up [Triangular
Numbers](http://en.wikipedia.org/wiki/Triangular_number). For an average
15-word tweet, there would be 120 multiword topics.

e-drop was doing this for a while, the consequence was that it used 6 out of
the 6.5 hours of CPU quota each day, and this was without visitors. It now uses
about 1.8 hours of CPU a day.

What changed was instead of querying the database for all possible tokens,
e-drop only queries tokens where the first word of the topic is an ancestor in
the datastore. This makes a (n ^ 2 + n) / 2 set of tokens only necessary in the
worst-case scenario, where all the words are ancestors topics, which is
possible but not likely.

### Multiword topics are trees

A topic is an ancestor if it is not the last word in a multiword topic. To find
out if topics that begin with "encino" exist in the datastore, we only need a
query with a single key name: "parent:encino". 

    Topic.get_by_key_name("parent:encino")

Knowing if the beginning of a multiword token exists means we can trim the set
of multiword tokens described earlier, or better: we can only build sequences
for tokens we know first words exist.

    ancestors = ["my", "favorite", "movie", ..., "man"]
    ancestor_exists = Topic.get(ancestors)

    # Topic.get() returns a list of Topics or None, i.e.,
    # [None, "favorite", None, ..., None]

    for index in range(len(ancestors)):
        first_word= ancestor_exists[index]
        if first_word is not None:
            build_sequence(first_word)
            # ...

We can represent this relationship in an entity path. Entities in the datastore
can have one ancestor, ancestors have many children.

### Multiword topics are reached by paths

An path is a group of entities that are connected in a parent/child
relationship. An entity path can be represented by pairs of type and key name.
The "encino man" topic exists in the datastore as two topics: the parent
"encino" and the child "man". To retrieve "encino man" as a multiword topic, we
create a key from the path.

    key = Key.from_path("Topic", "encino", "Topic", "man")
    Topic.get(key)

    >>> <Topic: encino man>

We can create many keys and query them in one go:

    keys = [Key.from_path..., Key.from_path...]
    Topic.get(keys)

    >>> [<Topic...>, <Topic...>]

We could also represent this tree structure using a Reference property, but
then multiword topics with the same last words would lose uniqueness (e.g.
"encino man" and "i love you man") since they both would have the key name
"key:man". Using the parent property two topics with the same key are unique as
long as they have different parents.
