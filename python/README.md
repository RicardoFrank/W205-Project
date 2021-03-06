Here's how to start and tinker with #douchetag.

*NB*: when you've completed this run-through,
the account tied to the twitter creds you
enter will have a newly blocked twitter
users.  You'll likely want to use either
a throw-away account, or you'll want
to immediately clean up that account's
block list.

# Pre-conditions

0. The project repo must be cloned.
1. `zookeeper` and `kafka` must be running.
2. The `SPARK_HOME` and `KAFKA_HOME` envariables must be set appropriately.
3. python 2.7 must be installed.
4. Twitter app credentials must be known.

# To run

You'll need to have 5 windows open:

4. will run various command line utilities and interactive frontends
2. will run the spark streaming job
1. will run the classifier
3. will run the tweet injector
5. will run the blocker

In each of them, do

    $ cd .../W205-Project/python
    $ export KAFKA_HOME=wherever-kafka-lives
    $ export SPARK_HOME=wherever-spark-lives

with the appropriate substitutions made.

When starting the apps, all endpoints will default to *localhost:the-right-port*

## Setup

In the first window, you'll first do some installation and setup:

    $ sudo sh install           # installs various python modules via pip
    $ bin/setup                 # creates kafka topics
    $ cp creds.template creds.py
    $ vi creds.py               # put in the twitter API credentials
                                # NB: when you run the blocker,
                                # this user's block list will grow

We'll return to this window later.

## Start the Spark streaming job in a window

If Zookeeper and Kafka are running locally...

    $ bin/run-spark

...or this if they are on remote systems

    $ bin/run-spark --broker <kafka broker endpoint>

The rest of this doc assumes all systems/daemons are running locally.
All commands take some form of `--help` or `-h` to see arguments
to point them at remote endpoints.

## Start the tweet classifier

    $ bin/run-classifier

## Start the tweet injector

    $ bin/run-injector

Once the injector is running, you'll see interesting output in all the other windows.

## Finally, start the blocker

    $ bin/run-blocker

## To add an harasser's tweets to the model

From the first window

    $ bin/add-harasser @BerkeleyData

This will add all of the datascience@berkeley tweets to the corpus of harassing tweets.
Once this corpus is loaded, tweets similar to it will be marked as harassing
and added to the `creds.py` user's block list.

# To test the model interactively

Stop the classifer via ctl-C, then restart it:

    $ bin/run-classifier --forget-harassment

The classifier retains history across process invocations.
For this test, we want it to forget what it has
learned about harassing tweets.

Now, inject a single user's tweets into the tweet stream:

    $ bin/inject-tweets @closemindedjerk

This does the job of the tweet-injector, but for only a single
users tweets.

Check the output in the 2nd window. 
You'll see that none of closemindedjerk's tweets were
judged to be harassing.

Now, add @closemindedjerk's tweets as harassment.
In the first window, do:

    $ bin/add-harassment @closemindedjerk

Then, re-inject @closeminded jerk's tweets to see that they are now considered harassment:

    $ bin/inject-tweets @closemindedjerk

Finally, go check the `creds.py` user's twitter account.
@closemindedjerk should now be blocked.
