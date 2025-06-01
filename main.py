import asyncio
import argparse
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import logger, validate_config, TARGET_ACCOUNTS
from twscrape_client import fetch_tweets, scrape_timeline_tweets
from media_handler import process_tweet_media
from ai_generator import generate_ai_content
from poster import post_content
import json
import os

class TwitterBot:
    def __init__(self):
        self.validate_setup()
        self.last_processed_tweets = set()  # Track processed tweets to avoid duplicates
        self.running = False
        self.state_file = "bot_state.json"
        self.load_state()
        
    def validate_setup(self):
        """Validate configuration and setup"""
        try:
            validate_config()
            logger.info("Bot initialized successfully")
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            raise
    
    def load_state(self):
        """Load bot state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_standalone_tweet = datetime.fromisoformat(state.get('last_standalone_tweet', '2020-01-01T00:00:00'))
                    self.last_thread = datetime.fromisoformat(state.get('last_thread', '2020-01-01T00:00:00'))
                    self.daily_tweet_count = state.get('daily_tweet_count', 0)
                    self.last_tweet_date = state.get('last_tweet_date', datetime.now().strftime('%Y-%m-%d'))
                    self.last_processed_tweets = set(state.get('last_processed_tweets', []))
            else:
                self.last_standalone_tweet = datetime(2020, 1, 1)
                self.last_thread = datetime(2020, 1, 1)
                self.daily_tweet_count = 0
                self.last_tweet_date = datetime.now().strftime('%Y-%m-%d')
                self.last_processed_tweets = set()
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            self.last_standalone_tweet = datetime(2020, 1, 1)
            self.last_thread = datetime(2020, 1, 1)
            self.daily_tweet_count = 0
            self.last_tweet_date = datetime.now().strftime('%Y-%m-%d')
            self.last_processed_tweets = set()
    
    def save_state(self):
        """Save bot state to file"""
        try:
            state = {
                'last_standalone_tweet': self.last_standalone_tweet.isoformat(),
                'last_thread': self.last_thread.isoformat(),
                'daily_tweet_count': self.daily_tweet_count,
                'last_tweet_date': self.last_tweet_date,
                'last_processed_tweets': list(self.last_processed_tweets)
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def reset_daily_count_if_needed(self):
        """Reset daily tweet count if it's a new day"""
        today = datetime.now().strftime('%Y-%m-%d')
        if self.last_tweet_date != today:
            self.daily_tweet_count = 0
            self.last_tweet_date = today
            logger.info("Reset daily tweet count for new day")
    
    def should_post_standalone_tweet(self) -> bool:
        """Check if we should post a standalone tweet (4 per day)"""
        self.reset_daily_count_if_needed()
        return self.daily_tweet_count < 4
    
    def should_post_thread(self) -> bool:
        """Check if we should post a thread (every 2 days)"""
        now = datetime.now()
        time_since_last = now - self.last_thread
        return time_since_last.days >= 2
    
    async def handle_rate_limit(self, operation_type: str):
        """Handle rate limiting with exponential backoff"""
        base_delay = {
            'reply': 8,      # Increased from 5
            'quote': 10,     # Increased from 7
            'tweet': 5,      # Increased from 3
            'thread': 15     # Increased from 10
        }
        
        delay = base_delay.get(operation_type, 8)
        jitter = random.uniform(0.8, 1.5)  # Add randomness
        total_delay = delay * jitter
        
        logger.info(f"Rate limiting: waiting {total_delay:.1f}s for {operation_type}")
        await asyncio.sleep(total_delay)
    
    def filter_fresh_tweets(self, tweets: List[Dict], hours_limit: int = 24) -> List[Dict]:
        """Filter tweets to get only recent ones and not already processed"""
        if not tweets:
            return []
        
        fresh_tweets = []
        now = datetime.now()
        
        for tweet in tweets:
            # Skip already processed tweets
            if tweet['id'] in self.last_processed_tweets:
                continue
            
            # Check if tweet is recent enough
            try:
                tweet_time = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                tweet_time = tweet_time.replace(tzinfo=None)
                time_diff = now - tweet_time
                
                if time_diff.total_seconds() < hours_limit * 3600:
                    fresh_tweets.append(tweet)
            except Exception as e:
                logger.warning(f"Could not parse tweet date: {e}")
                # Include tweet if we can't parse date
                fresh_tweets.append(tweet)
        
        # Sort by creation time (most recent first)
        try:
            fresh_tweets.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        except:
            pass
        
        return fresh_tweets
    
    async def get_timeline_tweets(self, limit: int = 50) -> List[Dict]:
        """Get fresh tweets from timeline"""
        try:
            logger.info(f"Fetching {limit} tweets from timeline...")
            # Use the scrape_timeline_tweets function directly
            all_tweets = scrape_timeline_tweets(limit)
            
            if not all_tweets:
                logger.warning("No tweets fetched from timeline")
                return []
            
            # Filter for fresh tweets (last 24 hours, not processed)
            fresh_tweets = self.filter_fresh_tweets(all_tweets, hours_limit=24)
            
            logger.info(f"Found {len(fresh_tweets)} fresh tweets out of {len(all_tweets)} total")
            return fresh_tweets
            
        except Exception as e:
            logger.error(f"Failed to get timeline tweets: {e}")
            return []
    
    async def run_reply_bot_timeline(self, limit: int = 2) -> List[str]:
        """Generate and post replies to timeline tweets"""
        results = []
        
        # Get fresh tweets from timeline
        tweets = await self.get_timeline_tweets(30)  # Get more to have better selection
        if not tweets:
            logger.warning("No fresh tweets found in timeline")
            return results
        
        # Select random tweets for replies
        reply_candidates = random.sample(tweets, min(limit * 2, len(tweets)))
        successful_replies = 0
        
        for tweet in reply_candidates:
            if successful_replies >= limit:
                break
                
            try:
                # Generate AI reply
                logger.info(f"Generating reply for tweet from @{tweet['author']}")
                reply_text = await generate_ai_content("reply", tweet['text'])
                if not reply_text:
                    logger.warning("Failed to generate reply text")
                    continue
                
                # Post reply
                reply_id = post_content("reply", reply_text, reply_to_id=tweet['id'])
                if reply_id:
                    results.append(reply_id)
                    self.last_processed_tweets.add(tweet['id'])
                    successful_replies += 1
                    logger.info(f"Posted reply to tweet {tweet['id']} from @{tweet['author']}")
                else:
                    logger.warning(f"Failed to post reply to tweet {tweet['id']}")
                
                # Rate limiting between replies
                await self.handle_rate_limit('reply')
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet['id']}: {e}")
                await asyncio.sleep(3)  # Brief pause on error
        
        logger.info(f"Reply bot completed: {successful_replies}/{limit} successful replies")
        return results
    
    async def run_quote_bot_timeline(self, limit: int = 1) -> List[str]:
        """Generate and post quote tweets from timeline"""
        results = []
        
        # Get fresh tweets from timeline
        tweets = await self.get_timeline_tweets(30)
        if not tweets:
            logger.warning("No fresh tweets found for quoting")
            return results
        
        # Select random tweets for quotes
        quote_candidates = random.sample(tweets, min(limit * 2, len(tweets)))
        successful_quotes = 0
        
        for tweet in quote_candidates:
            if successful_quotes >= limit:
                break
                
            try:
                # Generate AI quote tweet
                logger.info(f"Generating quote tweet for tweet from @{tweet['author']}")
                quote_text = await generate_ai_content("quote", tweet['text'])
                if not quote_text:
                    logger.warning("Failed to generate quote text")
                    continue
                
                # Post quote tweet
                quote_id = post_content("quote", quote_text, quoted_tweet_id=tweet['id'])
                if quote_id:
                    results.append(quote_id)
                    self.last_processed_tweets.add(tweet['id'])
                    successful_quotes += 1
                    logger.info(f"Posted quote tweet for tweet {tweet['id']} from @{tweet['author']}")
                else:
                    logger.warning(f"Failed to post quote tweet for {tweet['id']}")
                
                # Rate limiting between quotes
                await self.handle_rate_limit('quote')
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet['id']}: {e}")
                await asyncio.sleep(3)  # Brief pause on error
        
        logger.info(f"Quote bot completed: {successful_quotes}/{limit} successful quotes")
        return results
    
    async def run_thread_bot(self, topic: str, num_tweets: int = 3) -> Optional[List[str]]:
        """Generate and post a Twitter thread"""
        try:
            # Generate thread content
            thread_tweets = await generate_ai_content("thread", topic, num_tweets=num_tweets)
            if not thread_tweets or not isinstance(thread_tweets, list):
                logger.error("Failed to generate thread content")
                return None
            
            # Post thread
            thread_ids = post_content("thread", thread_tweets)
            if thread_ids:
                self.last_thread = datetime.now()
                logger.info(f"Posted thread with {len(thread_ids)} tweets")
                return thread_ids
            
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
        
        return None
    
    async def run_standalone_bot(self, topic: str) -> Optional[str]:
        """Generate and post a standalone tweet"""
        try:
            # Generate tweet content
            tweet_text = await generate_ai_content("standalone", topic)
            if not tweet_text:
                logger.error("Failed to generate tweet content")
                return None
            
            # Post tweet
            tweet_id = post_content("tweet", tweet_text)
            if tweet_id:
                self.daily_tweet_count += 1
                self.last_standalone_tweet = datetime.now()
                logger.info(f"Posted standalone tweet: {tweet_id} (Daily count: {self.daily_tweet_count}/4)")
                return tweet_id
            
        except Exception as e:
            logger.error(f"Failed to create standalone tweet: {e}")
        
        return None
    
    async def run_2hour_cycle(self):
        """Run the main 2-hour cycle: 2 replies + 1 quote from timeline"""
        logger.info("Starting 2-hour bot cycle (timeline-based)...")
        
        try:
            # Get fresh timeline tweets once for this cycle
            timeline_tweets = await self.get_timeline_tweets(50)
            
            if not timeline_tweets:
                logger.warning("No timeline tweets available for this cycle")
                return
            
            total_replies = 0
            total_quotes = 0
            
            # 1. Generate 2 replies from timeline
            logger.info("Processing replies from timeline tweets...")
            results = await self.run_reply_bot_timeline(limit=2)
            total_replies = len(results)
            
            # 2. Generate 1 quote tweet from timeline
            logger.info("Processing quote tweets from timeline...")
            results = await self.run_quote_bot_timeline(limit=1)
            total_quotes = len(results)
            
            # Clean up old processed tweets (keep only last 1000)
            if len(self.last_processed_tweets) > 1000:
                old_tweets = list(self.last_processed_tweets)[:500]
                for tweet_id in old_tweets:
                    self.last_processed_tweets.discard(tweet_id)
                logger.info("Cleaned up old processed tweets")
            
            logger.info(f"2-hour cycle completed - Replies: {total_replies}/2, Quotes: {total_quotes}/1")
            
        except Exception as e:
            logger.error(f"Error in 2-hour cycle: {e}")
    
    async def run_standalone_cycle(self):
        """Post standalone tweets (4 per day, randomly distributed)"""
        if self.should_post_standalone_tweet():
            logger.info(f"Posting standalone tweet ({self.daily_tweet_count + 1}/4)")
            result = await self.run_standalone_bot("AI and machine learning")
            if result:
                logger.info(f"Posted standalone tweet ({self.daily_tweet_count}/4 today)")
        else:
            logger.info(f"Daily standalone tweet limit reached ({self.daily_tweet_count}/4)")
    
    async def run_thread_cycle(self):
        """Post thread every 2 days"""
        if self.should_post_thread():
            logger.info("Posting thread (every 2 days)")
            topics = [
                "The future of artificial intelligence",
                "Machine learning breakthroughs",
                "AI ethics and society",
                "Deep learning innovations",
                "AI in everyday life",
                "Neural networks explained",
                "AI's impact on creativity",
                "The rise of large language models"
            ]
            topic = random.choice(topics)
            result = await self.run_thread_bot(topic, num_tweets=random.randint(3, 5))
            if result:
                logger.info(f"Posted thread with {len(result)} tweets")
        else:
            days_since_last = (datetime.now() - self.last_thread).days
            logger.info(f"Thread not due yet ({days_since_last}/2 days since last)")
    
    async def start_continuous_mode(self):
        """Start the bot in continuous mode with proper scheduling"""
        logger.info("Starting Twitter bot in continuous mode...")
        logger.info("Schedule:")
        logger.info("- 2 replies + 1 quote every 2 hours (from timeline)")
        logger.info("- 4 standalone tweets per day (randomly distributed)")
        logger.info("- 1 thread every 2 days")
        
        self.running = True
        
        # Run initial cycle
        await self.run_2hour_cycle()
        
        last_2hour_run = time.time()
        last_standalone_check = time.time()
        last_thread_check = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for 2-hour cycle (2 replies + 1 quote from timeline)
                if current_time - last_2hour_run >= 7200:  # 2 hours = 7200 seconds
                    await self.run_2hour_cycle()
                    last_2hour_run = current_time
                
                # Check for standalone tweets (randomly throughout the day)
                if current_time - last_standalone_check >= 3600:  # Check every hour
                    # Random chance to post (to distribute 4 tweets across the day)
                    if random.random() < 0.25:  # 25% chance each hour for better distribution
                        await self.run_standalone_cycle()
                    last_standalone_check = current_time
                
                # Check for threads (every 6 hours)
                if current_time - last_thread_check >= 21600:  # 6 hours
                    await self.run_thread_cycle()
                    last_thread_check = current_time
                
                # Save state
                self.save_state()
                
                # Sleep for 10 minutes before next check
                logger.info("Sleeping for 10 minutes before next check...")
                await asyncio.sleep(600)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping bot...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in continuous mode: {e}")
                # Continue running even if there's an error
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    def stop(self):
        """Stop the continuous mode"""
        self.running = False
        self.save_state()
        logger.info("Bot stopping...")

async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="AI-Powered Twitter Bot")
    parser.add_argument("mode", 
                       choices=["reply", "quote", "thread", "standalone", "continuous"], 
                       help="Bot operation mode")
    parser.add_argument("--topic", help="Topic for thread/standalone mode")
    parser.add_argument("--limit", type=int, default=2, help="Number of tweets to process")
    parser.add_argument("--tweets", type=int, default=3, help="Number of tweets in thread")
    
    args = parser.parse_args()
    
    bot = TwitterBot()
    
    try:
        if args.mode == "continuous":
            # Run in continuous mode with automatic scheduling
            logger.info("Starting continuous mode - automatic scheduling enabled")
            await bot.start_continuous_mode()
        
        elif args.mode == "reply":
            logger.info("Running reply mode on timeline tweets")
            results = await bot.run_reply_bot_timeline(args.limit)
            logger.info(f"Posted {len(results)} replies")
        
        elif args.mode == "quote":
            logger.info("Running quote mode on timeline tweets")
            results = await bot.run_quote_bot_timeline(args.limit)
            logger.info(f"Posted {len(results)} quote tweets")
        
        elif args.mode == "thread":
            if not args.topic:
                args.topic = "AI and machine learning"
            results = await bot.run_thread_bot(args.topic, args.tweets)
            if results:
                logger.info(f"Posted thread with {len(results)} tweets")
        
        elif args.mode == "standalone":
            if not args.topic:
                args.topic = "AI and machine learning"
            result = await bot.run_standalone_bot(args.topic)
            if result:
                logger.info(f"Posted standalone tweet: {result}")
    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        bot.stop()
    except Exception as e:
        logger.error(f"Bot execution failed: {e}")
        bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
