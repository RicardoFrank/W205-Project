import random

from classifier.base import TweetClassifier

class RandomTweetClassifier(TweetClassifier):
    def __init__(self, sc = None, p = 0.5):
	TweetClassifier.__init__(self)
	self.p_harassing = p

    def isHarassingTweet(self, txt):
    	return random.random() < self.p_harassing

    def addHarassingTweet(self, txt):
	pass
