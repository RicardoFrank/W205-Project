from __future__ import print_function
import sys

from twitter.tweetstore import TweetStore
from util.kafkatransceiver import KafkaTransceiver

class KafkaTweetStore(TweetStore):
   """
   Store tweets in a Kafka log
   """

   def __init__(self, serializer = None, endpoint = None, topic = None, tweetsPerLine = None):
      """
      """
      self.kafka = KafkaTransceiver(endpoint)
      self.topic = topic
      self.tweetsPerLine = tweetsPerLine
      TweetStore.__init__(self, serializer)
      print("created KTS, tweetsPerLine %d" % self.tweetsPerLine)

   def message(self, m):
      if self.tweetsPerLine is not None:
         sys.stdout.write(m)
         sys.stdout.flush()

   def close(self):
      """
      Close the store.
      """
      if self.kafka is None:
         return
      self._closing = True
      self._logEol()
      self.serializer.closing()
      self.kafka.close()
      self.kafka = None
      self.nTweets = 0
      self._closing = False

   def _logEol(self):
      if self.kafka is not None:
	  self.message("%d tweets\n" % self.nTweets)

   def _logTweet(self):
      self.message('.')
      if self.tweetsPerLine is not None and self.nTweets % self.tweetsPerLine == 0:
         self._logEol()

   def write(self, s):
      """
      write() makes no sense for Kafka,
      where messages are atomic units and
      so don't require bytes to mark tweets
      """
      pass

   def writeTweet(self,  tweet):
      """
      Write a tweet to the store.
      """
      if self._closing:
         print("writing to closing tweet store:", ''.join(traceback.format_stack()))
      self.nTweets += 1
      self.totTweets += 1
      self.totBytes += len(tweet)
      self.kafka.xmit(self.topic, tweet)
      self._logTweet()
