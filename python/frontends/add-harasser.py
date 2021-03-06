from __future__ import print_function
import sys, os, signal
import datetime, time
import re
import tweepy, json
import traceback
import argparse, pprint

sys.path += [ os.getcwd() ]
from util.reentrantmethod import ReentrantMethod
from twitter.filetweetstore import FileTweetStore
from twitter.kafkatweetstore import KafkaTweetStore
from twitter.classifiertweetstore import ClassifierTweetStore
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
      description='Suck filtered tweets from twitter and write them into a store'
      , formatter_class=argparse.ArgumentDefaultsHelpFormatter)
   p.add_argument('harassment', nargs='+', help='screen name of @harasser or a tweet id or a tweet URI or directory(ies) of tweet files')
   p.add_argument('--ntweets', dest='nTweets', type=int, default=1000
                               , help='number of recent tweets written by harasser to publish')
   p.add_argument('--max-tweets', dest='maxTweets', type=int, default=100
                                , help='max tweets written per file or line')
   kargs = p.add_argument_group('kafka', 'write tweets into Kafka store')
   portDef = 9092
   kargs.add_argument('--broker', dest='bk_endpt', nargs='?', const='localhost:9092', metavar='ENDPOINT'
                                , help='broker endpoint for kafka store')
   topicDef = 'harassing-tweets'
   kargs.add_argument('--topic', dest='topic'
                               , help='Kafka topic to which tweets are written (default: {0})'.format(topicDef))
   fargs = p.add_argument_group('file', 'write tweets into a file system store')
   patDef = 'harassment/%Y-%m-%d/%05n'
   fargs.add_argument('--pat', dest='pat'
                             , help='path name pattern to store tweets (default: {0})'.format(patDef.replace('%', '%%')))
   fargs.add_argument('--max-file-size', dest='maxSize', type=int
                                       , help='max bytes (more or less) written per tweet file')

   methodDef = 'isHarassingTweet'
   cargs = p.add_argument_group('classifier', 'send tweets to a classifier (for benchmarking)')
   cargs.add_argument('--classifier', dest='classifier', metavar='ENDPOINT', nargs='?', const='http://localhost:6666')
   cargs.add_argument('--method', dest='meth', metavar='CLASSIFIER METHOD'
                      , help='classifier method to call (default: %s)' % methodDef)
   args = p.parse_args()
   pp = pprint.PrettyPrinter(indent=4)
   pp.pprint(args)

   # Handle mutually exclusive arguments;
   # ideally, argparse could handle this...
   # but it's argument groups that are
   # mutually exclusive, not individual
   # arguments, so...nope.
   kafka = args.bk_endpt or args.topic
   file = args.pat or args.maxSize
   classifier = args.classifier
   if kafka and file or file and classifier or classifier and kafka:
      print("can't mix different tweet store options\n",
            p.format_usage(), file=sys.stderr)
      exit(1)
   # We're forced to handle defaults
   # ourselves, since we must detect
   # mutually exclusive groups ourselves
   if args.pat is None:
      args.pat = patDef
   if args.topic is None:
      args.topic = topicDef
   if args.meth is None:
      args.meth = methodDef

   if len(args.harassment) == 1 \
      and not os.path.isdir(args.harassment[0]):
         args.harassment = args.harassment[0]

   # Bring in twitter creds; this file is *not*
   # in source code control; you've got to provide
   # it yourself
   execfile("./creds.py");

   auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
   auth.set_access_token(access_token, access_token_secret)

   ## Handle signals
   #signal.signal(signal.SIGINT, interrupt)
   #signal.signal(signal.SIGTERM, interrupt)

   api = tweepy.API(auth_handler=auth,wait_on_rate_limit=True,wait_on_rate_limit_notify=True)
   print("tweepy API created")
   if kafka:
      if ':' not in args.bk_endpt: args.bk_endpt += ':%s' % portDef
      st = KafkaTweetStore(endpoint = args.bk_endpt, topic = args.topic, tweetsPerLine = args.maxTweets)
   elif classifier:
      st = ClassifierTweetStore(endpoint = args.classifier, classify = args.meth == 'isHarassingTweet')
   elif file:
      st = FileTweetStore(maxTweets = args.maxTweets, pathPattern=args.pat)
   else:
      print("omg, can't parse options")
      exit(1)
   print("tweet store created: " + type(st).__name__)
   s = TweetSerializer(store = st)
   st.serializer = s
   w = TweetWriter(s.write)

   # Determine what to add as harassment
   harasser = None
   harassing_tweet = None
   if isinstance(args.harassment, list):
      pass
   elif args.harassment.startswith('@'):
      # A screen name
      harasser = args.harassment[1:]
   elif re.match('^http(s?)://twitter\.com/[^/]+/status/\d+$', args.harassment):
      # A URI to a tweet
      harassing_tweet = re.sub('.*/', '', args.harassment)
   elif re.match('^\d+$', args.harassment):
      # A tweet ID
      harassing_tweet = args.harassment
   else:
      # Default to a screen name
      harasser = args.harassment

   if kafka:
      store = "topic '%s'" % args.topic
   elif file:
      store = "file store '%s'" % args.pat
   elif classifier:
      store = 'classifier @ %s via .%s()' % (args.classifier, args.meth)

   if harassing_tweet is not None:
      print("adding tweet id %s to %s" % (harassing_tweet, store))
      def onetweet(id):
         yield api.get_status(id)
      iter = lambda: onetweet(harassing_tweet)
   elif harasser is not None:
      print("adding tweets from @%s to %s" % (harasser, store))
      iter = tweepy.Cursor(api.user_timeline,screen_name=harasser, count=args.nTweets).items
   else:
      print("iterating over files in %s, adding them to %s" % (args.harassment, store))
      def readfiles(dirs):
         """
         Pump a directory of tweet files out as individual tweets.

         It's useful for benchmarking, but it's otherwise awful.
         Sorry. --Chris
         """
         for d in dirs:
            for path in os.listdir(d):
               f = open('%s/%s' % (d, path), 'r')
               s = f.read()
               js = re.split("\n},?\n", s)
               for j in js:
                  if j[0] == '[':
                     j = j[1:]
                  j += "}"
                  if j[0] != ']':
                     class x(object):
                        def __init__(self, js):
                           self._json = json.loads(str(js))
                     if w.stopped:
                        return
                     yield x(j)
            return

      iter = lambda: (readfiles(args.harassment))

   start = time.time()
   try:
      for tweet in iter():
         w.on_data(tweet._json)
   except KeyboardInterrupt:
      pass
   except:
      w.on_exception(sys.exc_info()[0])

   s.end()
   dt = time.time() - start
   print("%d bytes in %d tweets in %0.2f seconds: %0.2f tweets/sec, %0.2f bytes/sec, %s/sec"
         % (st.totBytes, st.totTweets, dt, st.totTweets/dt, st.totBytes/dt, humanize(st.totBytes/dt)))


# vim: expandtab shiftwidth=3 softtabstop=3 tabstop=3
