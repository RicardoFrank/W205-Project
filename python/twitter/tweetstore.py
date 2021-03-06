from __future__ import print_function
import sys, os, signal
import datetime, time
import re
import tweepy, json
import traceback
from util.reentrantmethod import ReentrantMethod

class TweetStore(object):
   """
   Store tweets in files according to a policy.
   """

   def __init__(self, serializer = None):
      """
      """
      self.serializer = serializer
      self.nTweets = 0
      self.totTweets = 0
      self.totBytes = 0
      self._closing = False
      ReentrantMethod(self, self.close)

   def close(self):
      """
      Close the store.

      A subsequent write to the store will re-open it.
      """

   def write(self, s):
      """
      Write bytes to a tweet store.

      Typically, these bytes have to do with
      serialization.  Write tweets using the
      writeTweet() method.
      """

   def writeTweet(self,  tweet):
      """
      Write a tweet to the store.
      """
