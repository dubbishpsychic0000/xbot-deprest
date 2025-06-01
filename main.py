#!/usr/bin/env python3
import asyncio
import schedule
import time
import random
import sys
from datetime import datetime, timedelta
from typing import List, Dict
import argparse

from config import logger, validate_config
from ai_generator import generate_ai_content
from poster import post_content
from twscrape_client import fetch_tweets

class TwitterBot:
    def __init__(self):
        self.last_thread_time = None
        self.tweet_count_today = 0
        self.last_reset_date = datetime.now().date()
        
    def reset_daily_counters(self):
        """Reset daily counters if it's a new day"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.tweet_count_today = 0
            self.last_reset_date = current_date
            logger.info("Daily counters reset")

    async def post_standalone_tweet(self, topic: str = None):
        """Post a standalone tweet"""
        try:
            self.reset_daily_counters()
            
            if self.tweet_count_today >= 4:
                logger.info("Daily tweet limit reached (4/4)")
                return
            
            if not topic:
                topics = [
                    "AI and machine learning",
                    "Technology trends",
                    "Future of AI",
                    "Machine learning insights",
                    "AI ethics and responsibility",
                    "Emerging technologies",
                    "Data science",
                    "Artificial intelligence applications"
                ]
                topic = random.choice(topics)
            
            logger.info(f"Generating standalone tweet about: {topic}")
            content = await generate_ai_content("standalone", topic)
            
            if content:
                tweet_id = post_content("tweet", content)
                if tweet_id:
                    self.tweet_count_today += 1
                    logger.info(f"Posted standalone tweet ({self.tweet_count_today}/4): {tweet_id}")
                    return tweet_id
                else:
                    logger.error("Failed to post standalone tweet")
            else:
                logger.error("Failed to generate standalone tweet content")
                
        except Exception as e:
            logger.error(f"Error in post_standalone_tweet: {e}")

    async def post_thread(self, topic: str = None):
        """Post a thread (once every 2 days)"""
        try:
            current_time = datetime.now()
            
            # Check if we should post a thread (every 2 days)
            if self.last_thread_time:
                time_diff = current_time - self.last_thread_time
                if time_diff < timedelta(days=2):
                    logger.info(f"Thread posted {time_diff} ago, waiting for 2-day interval")
                    return
            
            if not topic:
                thread_topics = [
                    "The evolution of AI in the past decade",
                    "Understanding neural networks and deep learning",
                    "AI ethics and responsible development",
                    "The future of human-AI collaboration",
                    "Machine learning in everyday applications",
                    "Breakthrough AI research and implications",
                    "The impact of AI on various industries",
                    "Building trustworthy AI systems"
                ]
                topic = random.choice(thread_topics)
            
            logger.info(f"Generating thread about: {topic}")
            thread_tweets = await generate_ai_content("thread", topic, num_tweets=3)
            
            if thread_tweets and isinstance(thread_tweets, list) and len(thread_tweets) > 0:
                posted_ids = post_content("thread", thread_tweets)
                if posted_ids and len(posted_ids) > 0:
                    self.last_thread_time = current_time
                    logger.info(f"Posted thread with {len(posted_ids)} tweets: {posted_ids}")
                    return posted_ids
                else:
                    logger.error("Failed to post thread")
            else:
                logger.error("Failed to generate thread content")
                
        except Exception as e:
            logger.error(f"Error in post_thread: {e}")

    async def engage_with_tweets(self):
        """Fetch tweets and create replies/quotes (2 replies + 1 quote per hour)"""
        try:
            logger.info("Fetching timeline tweets for engagement")
            
            # Fetch recent tweets from timeline
            tweets = await fetch_tweets("timeline", "", limit=10)
            
            if not tweets:
                logger.warning("No tweets fetched for engagement")
                return
            
            # Filter tweets that are suitable for engagement
            suitable_tweets = []
            for tweet in tweets:
                if (tweet.get('text', '').strip() and 
                    len(tweet.get('text', '')) > 20 and  # Minimum content length
                    not tweet.get('text', '').startswith('RT @')):  # Not retweets
                    suitable_tweets.append(tweet)
            
            if len(suitable_tweets) < 3:
                logger.warning(f"Only {len(suitable_tweets)} suitable tweets found, need at least 3")
                # Use all available tweets if we don't have enough
                suitable_tweets = tweets[:3] if len(tweets) >= 3 else tweets
            
            if not suitable_tweets:
                logger.warning("No suitable tweets found for engagement")
                return
            
            # Randomly select tweets for engagement
            selected_tweets = random.sample(suitable_tweets, min(3, len(suitable_tweets)))
            
            successful_engagements = 0
            replies_posted = 0
            quotes_posted = 0
            
            for i, tweet in enumerate(selected_tweets):
                try:
                    if replies_posted < 2:
                        # Post reply
                        logger.info(f"Generating reply to tweet: {tweet['id']}")
                        reply_content = await generate_ai_content(
                            "reply", 
                            tweet['text'], 
                            context=f"Tweet by @{tweet.get('author', 'unknown')}"
                        )
                        
                        if reply_content:
                            reply_id = post_content(
                                "reply", 
                                reply_content, 
                                reply_to_id=tweet['id']
                            )
                            if reply_id:
                                replies_posted += 1
                                successful_engagements += 1
                                logger.info(f"Posted reply ({replies_posted}/2): {reply_id}")
                            else:
                                logger.error(f"Failed to post reply to tweet {tweet['id']}")
                        else:
                            logger.error(f"Failed to generate reply for tweet {tweet['id']}")
                    
                    elif quotes_posted < 1:
                        # Post quote tweet
                        logger.info(f"Generating quote tweet for: {tweet['id']}")
                        quote_content = await generate_ai_content(
                            "quote", 
                            tweet['text'], 
                            context=f"Tweet by @{tweet.get('author', 'unknown')}"
                        )
                        
                        if quote_content:
                            quote_id = post_content(
                                "quote", 
                                quote_content, 
                                quoted_tweet_id=tweet['id']
                            )
                            if quote_id:
                                quotes_posted += 1
                                successful_engagements += 1
                                logger.info(f"Posted quote tweet ({quotes_posted}/1): {quote_id}")
                            else:
                                logger.error(f"Failed to post quote tweet for {tweet['id']}")
                        else:
                            logger.error(f"Failed to generate quote content for tweet {tweet['id']}")
                    
                    # Add delay between engagements
                    if i < len(selected_tweets) - 1:
                        await asyncio.sleep(random.uniform(30, 60))
                        
                except Exception as e:
                    logger.error(f"Error engaging with tweet {tweet.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"Engagement completed: {replies_posted} replies, {quotes_posted} quotes")
            
        except Exception as e:
            logger.error(f"Error in engage_with_tweets: {e}")

    async def run_scheduled_job(self, job_type: str, **kwargs):
        """Run a specific scheduled job"""
        try:
            logger.info(f"Running scheduled job: {job_type}")
            
            if job_type == "standalone_tweet":
                await self.post_standalone_tweet(kwargs.get('topic'))
            elif job_type == "thread":
                await self.post_thread(kwargs.get('topic'))
            elif job_type == "engage":
                await self.engage_with_tweets()
            else:
                logger.error(f"Unknown job type: {job_type}")
                
        except Exception as e:
            logger.error(f"Error running scheduled job {job_type}: {e}")

def run_async_job(coro):
    """Helper function to run async jobs in sync scheduler"""
    asyncio.run(coro)

def setup_scheduler(bot: TwitterBot):
    """Setup the scheduler with all jobs"""
    logger.info("Setting up scheduler...")
    
    # Standalone tweets: 4 times a day at random times
    # Schedule them at different times to spread throughout the day
    schedule.every().day.at("09:00").do(
        run_async_job, bot.run_scheduled_job("standalone_tweet")
    )
    schedule.every().day.at("13:30").do(
        run_async_job, bot.run_scheduled_job("standalone_tweet")
    )
    schedule.every().day.at("17:45").do(
        run_async_job, bot.run_scheduled_job("standalone_tweet")
    )
    schedule.every().day.at("21:15").do(
        run_async_job, bot.run_scheduled_job("standalone_tweet")
    )
    
    # Thread: once every 2 days (will be checked internally)
    schedule.every().day.at("10:30").do(
        run_async_job, bot.run_scheduled_job("thread")
    )
    
    # Engagement: every hour (2 replies + 1 quote)
    schedule.every().hour.at(":15").do(
        run_async_job, bot.run_scheduled_job("engage")
    )
    
    logger.info("Scheduler setup completed")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Twitter Bot')
    parser.add_argument('mode', nargs='?', default='continuous', 
                       choices=['continuous', 'standalone', 'thread', 'engage', 'test'],
                       help='Bot operation mode')
    parser.add_argument('--topic', help='Topic for content generation')
    parser.add_argument('--duration', type=int, default=23, 
                       help='Duration in hours for continuous mode')
    
    args = parser.parse_args()
    
    try:
        # Validate configuration
        validate_config()
        logger.info("Twitter bot starting...")
        
        bot = TwitterBot()
        
        if args.mode == 'continuous':
            logger.info(f"Starting continuous mode for {args.duration} hours")
            setup_scheduler(bot)
            
            start_time = time.time()
            end_time = start_time + (args.duration * 3600)  # Convert hours to seconds
            
            while time.time() < end_time:
                try:
                    schedule.run_pending()
                    time.sleep(60)  # Check every minute
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, shutting down...")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    time.sleep(300)  # Wait 5 minutes before retrying
            
            logger.info("Continuous mode completed")
            
        elif args.mode == 'standalone':
            logger.info("Running standalone tweet mode")
            asyncio.run(bot.post_standalone_tweet(args.topic))
            
        elif args.mode == 'thread':
            logger.info("Running thread mode")
            asyncio.run(bot.post_thread(args.topic))
            
        elif args.mode == 'engage':
            logger.info("Running engagement mode")
            asyncio.run(bot.engage_with_tweets())
            
        elif args.mode == 'test':
            logger.info("Running test mode")
            # Test all functions
            asyncio.run(bot.post_standalone_tweet("Test topic"))
            asyncio.run(bot.engage_with_tweets())
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
