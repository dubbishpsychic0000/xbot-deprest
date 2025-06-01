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
        self.failed_attempts = 0
        self.max_failed_attempts = 3
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
                    self.last_2hour_cycle = datetime.fromisoformat(state.get('last_2hour_cycle', '2020-01-01T00:00:00'))
                    self.daily_tweet_count = state.get('daily_tweet_count', 0)
                    self.last_tweet_date = state.get('last_tweet_date', datetime.now().strftime('%Y-%m-%d'))
                    self.last_processed_tweets = set(state.get('last_processed_tweets', []))
                    self.failed_attempts = state.get('failed_attempts', 0)
            else:
                self.reset_state()
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            self.reset_state()
    
    def reset_state(self):
        """Reset bot state to defaults"""
        self.last_standalone_tweet = datetime(2020, 1, 1)
        self.last_thread = datetime(2020, 1, 1)
        self.last_2hour_cycle = datetime(2020, 1, 1)
        self.daily_tweet_count = 0
        self.last_tweet_date = datetime.now().strftime('%Y-%m-%d')
        self.last_processed_tweets = set()
        self.failed_attempts = 0
    
    def save_state(self):
        """Save bot state to file"""
        try:
            state = {
                'last_standalone_tweet': self.last_standalone_tweet.isoformat(),
                'last_thread': self.last_thread.isoformat(),
                'last_2hour_cycle': self.last_2hour_cycle.isoformat(),
                'daily_tweet_count': self.daily_tweet_count,
                'last_tweet_date': self.last_tweet_date,
                'last_processed_tweets': list(self.last_processed_tweets)[-1000:],  # Keep only last 1000
                'failed_attempts': self.failed_attempts
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
            logger.debug("State saved successfully")
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
        """Check if we should post a standalone tweet (4 per day, randomly distributed)"""
        self.reset_daily_count_if_needed()
        
        if self.daily_tweet_count >= 4:
            return False
        
        # Random distribution throughout the day (higher chance if we're behind schedule)
        current_hour = datetime.now().hour
        expected_tweets_by_now = min(4, (current_hour + 1) * 4 // 24)
        
        if self.daily_tweet_count < expected_tweets_by_now:
            return True
        
        # Random chance for normal distribution
        return random.random() < 0.1  # 10% chance per check
    
    def should_post_thread(self) -> bool:
        """Check if we should post a thread (every 2 days)"""
        now = datetime.now()
        time_since_last = now - self.last_thread
        return time_since_last.days >= 2
    
    def should_run_2hour_cycle(self) -> bool:
        """Check if we should run the 2-hour cycle"""
        now = datetime.now()
        time_since_last = now - self.last_2hour_cycle
        return time_since_last.total_seconds() >= 7200  # 2 hours in seconds
    
    async def handle_rate_limit(self, operation_type: str, attempt: int = 1):
        """Enhanced rate limiting with exponential backoff"""
        base_delays = {
            'reply': 10,     # Increased base delays
            'quote': 12,
            'tweet': 6,
            'thread': 20,
            'timeline_fetch': 30
        }
        
        base_delay = base_delays.get(operation_type, 10)
        
        # Exponential backoff for multiple attempts
        delay = base_delay * (2 ** (attempt - 1))
        
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.8, 1.3)
        total_delay = min(delay * jitter, 300)  # Cap at 5 minutes
        
        logger.info(f"Rate limiting ({operation_type}, attempt {attempt}): waiting {total_delay:.1f}s")
        await asyncio.sleep(total_delay)
    
    def filter_fresh_tweets(self, tweets: List[Dict], hours_limit: int = 6) -> List[Dict]:
        """Filter tweets to get only recent ones and not already processed"""
        if not tweets:
            return []
        
        fresh_tweets = []
        now = datetime.now()
        
        for tweet in tweets:
            # Skip already processed tweets
            if tweet['id'] in self.last_processed_tweets:
                continue
            
            # Skip our bot's own tweets
            if tweet.get('author', '').lower() == os.getenv('BOT_USERNAME', '').lower():
                continue
            
            # Check if tweet is recent enough (reduced to 6 hours for fresher content)
            try:
                if 'created_at' in tweet:
                    tweet_time = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                    if tweet_time.tzinfo:
                        tweet_time = tweet_time.replace(tzinfo=None)
                    time_diff = now - tweet_time
                    
                    if time_diff.total_seconds() < hours_limit * 3600:
                        fresh_tweets.append(tweet)
                else:
                    # If no timestamp, assume it's fresh
                    fresh_tweets.append(tweet)
            except Exception as e:
                logger.warning(f"Could not parse tweet date: {e}")
                # Include tweet if we can't parse date
                fresh_tweets.append(tweet)
        
        # Sort by creation time (most recent first) if possible
        try:
            fresh_tweets.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        except:
            # If sorting fails, shuffle to randomize
            random.shuffle(fresh_tweets)
        
        logger.info(f"Filtered to {len(fresh_tweets)} fresh tweets from {len(tweets)} total")
        return fresh_tweets
    
    async def get_timeline_tweets_with_retry(self, limit: int = 50, max_retries: int = 3) -> List[Dict]:
        """Get fresh tweets from timeline with retry logic"""
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Fetching {limit} tweets from timeline (attempt {attempt}/{max_retries})...")
                
                # Add delay before fetching to avoid overwhelming the system
                if attempt > 1:
                    await self.handle_rate_limit('timeline_fetch', attempt)
                
                # Fetch tweets using the scraping function
                all_tweets = scrape_timeline_tweets(limit)
                
                if not all_tweets:
                    logger.warning(f"No tweets fetched from timeline (attempt {attempt})")
                    if attempt < max_retries:
                        continue
                    return []
                
                # Filter for fresh tweets
                fresh_tweets = self.filter_fresh_tweets(all_tweets, hours_limit=6)
                
                if fresh_tweets:
                    logger.info(f"Successfully got {len(fresh_tweets)} fresh tweets")
                    self.failed_attempts = 0  # Reset on success
                    return fresh_tweets
                else:
                    logger.warning(f"No fresh tweets found (attempt {attempt})")
                    if attempt < max_retries:
                        continue
                
            except Exception as e:
                logger.error(f"Failed to get timeline tweets (attempt {attempt}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(30 * attempt)  # Progressive delay
                else:
                    self.failed_attempts += 1
        
        logger.error("All timeline fetch attempts failed")
        return []
    
    async def run_reply_bot_timeline(self, limit: int = 2) -> List[str]:
        """Generate and post replies to timeline tweets with improved error handling"""
        results = []
        
        # Get fresh tweets from timeline
        tweets = await self.get_timeline_tweets_with_retry(50)
        if not tweets:
            logger.warning("No fresh tweets found for replies")
            return results
        
        # Select random tweets for replies (prefer newer tweets)
        reply_candidates = tweets[:min(limit * 3, len(tweets))]  # Take top candidates
        random.shuffle(reply_candidates)  # Randomize selection
        
        successful_replies = 0
        
        for tweet in reply_candidates[:limit * 2]:  # Try up to double the limit
            if successful_replies >= limit:
                break
                
            try:
                # Skip tweets that are too short or might be spam
                if len(tweet.get('text', '')) < 10:
                    continue
                
                # Skip tweets with too many mentions (likely spam)
                if tweet.get('text', '').count('@') > 3:
                    continue
                
                logger.info(f"Generating reply for tweet from @{tweet.get('author', 'unknown')}")
                
                # Generate AI reply with retry
                reply_text = None
                for attempt in range(2):
                    reply_text = await generate_ai_content("reply", tweet.get('text', ''))
                    if reply_text:
                        break
                    await asyncio.sleep(5)
                
                if not reply_text:
                    logger.warning("Failed to generate reply text after retries")
                    continue
                
                # Post reply with retry
                reply_id = None
                for attempt in range(2):
                    reply_id = post_content("reply", reply_text, reply_to_id=tweet['id'])
                    if reply_id:
                        break
                    await self.handle_rate_limit('reply', attempt + 1)
                
                if reply_id:
                    results.append(reply_id)
                    self.last_processed_tweets.add(tweet['id'])
                    successful_replies += 1
                    logger.info(f"Posted reply to tweet {tweet['id']} from @{tweet.get('author', 'unknown')}")
                else:
                    logger.warning(f"Failed to post reply to tweet {tweet['id']}")
                
                # Rate limiting between replies
                if successful_replies < limit:
                    await self.handle_rate_limit('reply')
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet.get('id', 'unknown')}: {e}")
                await asyncio.sleep(5)  # Brief pause on error
        
        logger.info(f"Reply bot completed: {successful_replies}/{limit} successful replies")
        return results
    
    async def run_quote_bot_timeline(self, limit: int = 1) -> List[str]:
        """Generate and post quote tweets from timeline with improved error handling"""
        results = []
        
        # Get fresh tweets from timeline
        tweets = await self.get_timeline_tweets_with_retry(50)
        if not tweets:
            logger.warning("No fresh tweets found for quoting")
            return results
        
        # Select interesting tweets for quotes (prefer tweets with more engagement potential)
        quote_candidates = [t for t in tweets if len(t.get('text', '')) > 20]  # Longer tweets
        random.shuffle(quote_candidates)
        
        successful_quotes = 0
        
        for tweet in quote_candidates[:limit * 2]:  # Try up to double the limit
            if successful_quotes >= limit:
                break
                
            try:
                # Skip very short tweets
                if len(tweet.get('text', '')) < 15:
                    continue
                
                logger.info(f"Generating quote tweet for tweet from @{tweet.get('author', 'unknown')}")
                
                # Generate AI quote tweet with retry
                quote_text = None
                for attempt in range(2):
                    quote_text = await generate_ai_content("quote", tweet.get('text', ''))
                    if quote_text:
                        break
                    await asyncio.sleep(5)
                
                if not quote_text:
                    logger.warning("Failed to generate quote text after retries")
                    continue
                
                # Post quote tweet with retry
                quote_id = None
                for attempt in range(2):
                    quote_id = post_content("quote", quote_text, quoted_tweet_id=tweet['id'])
                    if quote_id:
                        break
                    await self.handle_rate_limit('quote', attempt + 1)
                
                if quote_id:
                    results.append(quote_id)
                    self.last_processed_tweets.add(tweet['id'])
                    successful_quotes += 1
                    logger.info(f"Posted quote tweet for tweet {tweet['id']} from @{tweet.get('author', 'unknown')}")
                else:
                    logger.warning(f"Failed to post quote tweet for {tweet['id']}")
                
                # Rate limiting between quotes
                if successful_quotes < limit:
                    await self.handle_rate_limit('quote')
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet.get('id', 'unknown')}: {e}")
                await asyncio.sleep(5)  # Brief pause on error
        
        logger.info(f"Quote bot completed: {successful_quotes}/{limit} successful quotes")
        return results
    
    async def run_thread_bot(self, topic: str, num_tweets: int = 3) -> Optional[List[str]]:
        """Generate and post a Twitter thread with improved error handling"""
        try:
            logger.info(f"Generating thread about: {topic}")
            
            # Generate thread content with retry
            thread_tweets = None
            for attempt in range(2):
                thread_tweets = await generate_ai_content("thread", topic, num_tweets=num_tweets)
                if thread_tweets and isinstance(thread_tweets, list) and len(thread_tweets) > 0:
                    break
                await asyncio.sleep(10)
            
            if not thread_tweets or not isinstance(thread_tweets, list):
                logger.error("Failed to generate thread content")
                return None
            
            # Post thread with retry
            thread_ids = None
            for attempt in range(2):
                thread_ids = post_content("thread", thread_tweets)
                if thread_ids:
                    break
                await self.handle_rate_limit('thread', attempt + 1)
            
            if thread_ids:
                self.last_thread = datetime.now()
                logger.info(f"Posted thread with {len(thread_ids)} tweets")
                return thread_ids
            else:
                logger.error("Failed to post thread")
            
        except Exception as e:
            logger.error(f"Failed to create thread: {e}")
        
        return None
    
    async def run_standalone_bot(self, topic: str) -> Optional[str]:
        """Generate and post a standalone tweet with improved error handling"""
        try:
            logger.info(f"Generating standalone tweet about: {topic}")
            
            # Generate tweet content with retry
            tweet_text = None
            for attempt in range(2):
                tweet_text = await generate_ai_content("standalone", topic)
                if tweet_text:
                    break
                await asyncio.sleep(5)
            
            if not tweet_text:
                logger.error("Failed to generate tweet content")
                return None
            
            # Post tweet with retry
            tweet_id = None
            for attempt in range(2):
                tweet_id = post_content("tweet", tweet_text)
                if tweet_id:
                    break
                await self.handle_rate_limit('tweet', attempt + 1)
            
            if tweet_id:
                self.daily_tweet_count += 1
                self.last_standalone_tweet = datetime.now()
                logger.info(f"Posted standalone tweet: {tweet_id} (Daily count: {self.daily_tweet_count}/4)")
                return tweet_id
            else:
                logger.error("Failed to post standalone tweet")
            
        except Exception as e:
            logger.error(f"Failed to create standalone tweet: {e}")
        
        return None
    
    async def run_2hour_cycle(self):
        """Run the main 2-hour cycle: 2 replies + 1 quote from timeline"""
        logger.info("Starting 2-hour bot cycle (timeline-based)...")
        
        try:
            total_replies = 0
            total_quotes = 0
            
            # 1. Generate 2 replies from timeline
            logger.info("Processing replies from timeline tweets...")
            results = await self.run_reply_bot_timeline(limit=2)
            total_replies = len(results)
            
            # Small delay between operations
            await asyncio.sleep(30)
            
            # 2. Generate 1 quote tweet from timeline
            logger.info("Processing quote tweets from timeline...")
            results = await self.run_quote_bot_timeline(limit=1)
            total_quotes = len(results)
            
            # Update cycle timestamp
            self.last_2hour_cycle = datetime.now()
            
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
            logger.debug(f"Standalone tweet not due yet ({self.daily_tweet_count}/4 today)")
    
    async def run_thread_cycle(self):
        """Post thread every 2 days"""
        if self.should_post_thread():
            logger.info("Posting thread (every 2 days)")
            topics = [
                "The future of artificial intelligence",
                "Machine learning breakthroughs in 2024",
                "AI ethics and responsible development",
                "Deep learning innovations and applications",
                "How AI is transforming industries",
                "Understanding neural networks and transformers",
                "AI's impact on creativity and art",
                "The evolution of large language models",
                "AI safety and alignment challenges",
                "Machine learning in healthcare and science"
            ]
            topic = random.choice(topics)
            result = await self.run_thread_bot(topic, num_tweets=random.randint(3, 5))
            if result:
                logger.info(f"Posted thread with {len(result)} tweets")
        else:
            days_since_last = (datetime.now() - self.last_thread).days
            logger.debug(f"Thread not due yet ({days_since_last}/2 days since last)")
    
    async def start_continuous_mode(self):
        """Start the bot in continuous mode with proper scheduling and error recovery"""
        logger.info("Starting Twitter bot in continuous mode...")
        logger.info("Schedule:")
        logger.info("- 2 replies + 1 quote every 2 hours (from timeline)")
        logger.info("- 4 standalone tweets per day (randomly distributed)")
        logger.info("- 1 thread every 2 days")
        
        self.running = True
        
        # Check if we should run initial cycles
        if self.should_run_2hour_cycle():
            logger.info("Running initial 2-hour cycle...")
            await self.run_2hour_cycle()
        
        check_interval = 600  # 10 minutes
        
        while self.running:
            try:
                # Check for 2-hour cycle
                if self.should_run_2hour_cycle():
                    logger.info("Time for 2-hour cycle")
                    await self.run_2hour_cycle()
                
                # Check for standalone tweets (with random distribution)
                await self.run_standalone_cycle()
                
                # Check for threads
                await self.run_thread_cycle()
                
                # Save state after each check
                self.save_state()
                
                # Reduce check frequency if too many failures
                if self.failed_attempts > self.max_failed_attempts:
                    check_interval = min(3600, check_interval * 2)  # Backoff up to 1 hour
                    logger.warning(f"Too many failures, increasing check interval to {check_interval}s")
                else:
                    check_interval = 600  # Reset to 10 minutes
                
                # Sleep until next check
                logger.info(f"Sleeping for {check_interval//60} minutes before next check...")
                await asyncio.sleep(check_interval)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal, stopping bot...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in continuous mode: {e}")
                self.failed_attempts += 1
                
                # Progressive backoff on errors
                error_delay = min(1800, 300 * self.failed_attempts)  # Up to 30 minutes
                logger.info(f"Waiting {error_delay}s before retrying due to error...")
                await asyncio.sleep(error_delay)
    
    def stop(self):
        """Stop the continuous mode"""
        self.running = False
        self.save_state()
        logger.info("Bot stopping...")

async def main():
    """Main CLI interface with improved argument handling"""
    parser = argparse.ArgumentParser(description="AI-Powered Twitter Bot")
    parser.add_argument("mode", 
                       choices=["reply", "quote", "thread", "standalone", "continuous"], 
                       help="Bot operation mode")
    parser.add_argument("--topic", help="Topic for thread/standalone mode (optional)")
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
            logger.info(f"Running reply mode on timeline tweets (limit: {args.limit})")
            results = await bot.run_reply_bot_timeline(args.limit)
            logger.info(f"Posted {len(results)} replies")
        
        elif args.mode == "quote":
            logger.info(f"Running quote mode on timeline tweets (limit: {args.limit})")
            results = await bot.run_quote_bot_timeline(args.limit)
            logger.info(f"Posted {len(results)} quote tweets")
        
        elif args.mode == "thread":
            topic = args.topic or "AI and machine learning innovations"
            logger.info(f"Posting thread about: {topic}")
            results = await bot.run_thread_bot(topic, args.tweets)
            if results:
                logger.info(f"Posted thread with {len(results)} tweets")
            else:
                logger.error("Failed to post thread")
        
        elif args.mode == "standalone":
            topic = args.topic or "AI and machine learning"
            logger.info(f"Posting standalone tweet about: {topic}")
            result = await bot.run_standalone_bot(topic)
            if result:
                logger.info(f"Posted standalone tweet: {result}")
            else:
                logger.error("Failed to post standalone tweet")
    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        bot.stop()
    except Exception as e:
        logger.error(f"Bot execution failed: {e}")
        bot.stop()
        raise

if __name__ == "__main__":
    asyncio.run(main())
