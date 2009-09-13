#!/usr/bin/env python

from google.appengine.api import memcache
from google.appengine.api import users

from models import *

def expire_cache(key=None):
  if not key:
    result = memcache.flush_all()
  else:
    result = memcache.delete(key, namespace="topic")
  return result
