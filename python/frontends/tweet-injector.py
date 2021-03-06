from __future__ import print_function
import sys, os, signal
import datetime, time
import re
import tweepy, json
import traceback
import argparse, pprint

sys.path += [ os.getcwd() ]
from twitter.filetweetstore import FileTweetStore
from twitter.kafkatweetstore import KafkaTweetStore
from twitter.nulltweetstore import NullTweetStore
from util.reentrantmethod import ReentrantMethod
from twitter.tweetwriter import TweetWriter
from twitter.tweetserializer import TweetSerializer

def interrupt(signum, frame):
   stream.disconnect()
   w.stop()

def humanize(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


if __name__ == '__main__':

   p = argparse.ArgumentParser(
      description='Suck tweets, possibly filtered, from twitter and write them into a store'
      , formatter_class=argparse.ArgumentDefaultsHelpFormatter)
   p.add_argument('keywords', metavar='KW', nargs='*', help='filter keywords')
   p.add_argument('--max-tweets', dest='maxTweets', type=int, default=100
                                , help='max tweets written per file or line')
   kargs = p.add_argument_group('kafka', 'write tweets into Kafka store')
   portDef = '9092'
   kargs.add_argument('--broker', dest='bk_endpt', nargs='?', metavar='ENDPOINT'
                                , const='localhost:9092'
                                , help='broker endpoint for kafka store')
   topicDef = 'tweets'
   kargs.add_argument('--topic', dest='topic'
                               , help='Kafka topic to which tweets are written (default: {0})'.format(topicDef))
   fargs = p.add_argument_group('file', 'write tweets into a file system store')
   patDef = 'tweets/%Y-%m-%d/%05n'
   fargs.add_argument('--pat', dest='pat'
                             , help='path name pattern to store tweets (default: {0})'.format(patDef.replace('%', '%%')))
   fargs.add_argument('--max-file-size', dest='maxSize', type=int
                                       , help='max bytes (more or less) written per tweet file')
   nargs = p.add_argument_group('null', "'write' tweets into null store")
   nargs.add_argument('--discard', action='store_true', help='discard tweets')

   pp = pprint.PrettyPrinter(indent=4)
   args = p.parse_args()
   pp.pprint(args)

   # Handle mutually exclusive arguments;
   # ideally, argparse could handle this...
   # but its argument groups are
   # mutually exclusive, not individual
   # arguments, so...nope.
   # is to use a file system store, y
   kafka = args.bk_endpt or args.topic
   file = args.pat or args.maxSize
   null = args.discard
   if kafka and file or file and null or null and kafka:
      print("can't mix tweet store options\n",
            p.format_usage(), file=sys.stderr)
      exit(1)
   # We're forced to handle defaults
   # ourselves, since we must detect
   # mutually exclusive groups ourselves
   if args.pat is None:
      args.pat = patDef
   if args.topic is None:
      args.topic = topicDef

   # Bring in twitter creds; this file is *not*
   # in source code control; you've got to provide
   # it yourself
   execfile("./creds.py");

   auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
   auth.set_access_token(access_token, access_token_secret)

   # Handle signals
   signal.signal(signal.SIGINT, interrupt)
   signal.signal(signal.SIGTERM, interrupt)

   api = tweepy.API(auth_handler=auth,wait_on_rate_limit=True,wait_on_rate_limit_notify=True)
   print("tweepy API created")
   if kafka:
      if ':' not in args.bk_endpt: args.bk_endpt += ':%s' % portDef
      print('connecting to kafka broker @ ' + args.bk_endpt)
      st = KafkaTweetStore(endpoint = args.bk_endpt, topic = args.topic, tweetsPerLine = args.maxTweets)
   elif null:
      st = NullTweetStore(tweetsPerLine = args.maxTweets)
   else:
      st = FileTweetStore(maxTweets = args.maxTweets, pathPattern=args.pat)
   print("tweet store created")
   s = TweetSerializer(store = st, to_json = lambda tweet: json.loads(tweet))
   st.serializer = s
   w = TweetWriter(s.write)
   stream = tweepy.Stream(auth, w)
   print("twitter stream created")

   # filter stream according to argv, in a separate thread
   start = time.time()
   if len(args.keywords) > 0:
      stream.filter(track=sys.argv, async=True)
      print("filtering tweets on [" + " ".join(args.keywords) + "]")
   else:
      stream.sample(async=True)
      print("sampling tweets")

   # Pass the time, waiting for an interrupt
   while not w.stopped:
      signal.pause()
      print("signalled")
   stream.disconnect()
   stream._thread.join()
   s.end()
   dt = time.time() - start
   print("%d bytes in %d tweets in %0.2f seconds: %0.2f tweets/sec, %0.2f bytes/sec, %s/sec"
         % (st.totBytes, st.totTweets, dt, st.totTweets/dt, st.totBytes/dt, humanize(st.totBytes/dt)))

# vim: expandtab shiftwidth=3 softtabstop=3 tabstop=3
