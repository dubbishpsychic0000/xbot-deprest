import asyncio
import argparse
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import logger, validate_config, TARGET_ACCOUNTS
from twscrape_client import fetch_tweets
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
            else:
                self.last_standalone_tweet = datetime(2020, 1, 1)
                self.last_thread = datetime(2020, 1, 1)
                self.daily_tweet_count = 0
                self.last_tweet_date = datetime.now().strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            self.last_standalone_tweet = datetime(2020, 1, 1)
            self.last_thread = datetime(2020, 1, 1)
            self.daily_tweet_count = 0
            self.last_tweet_date = datetime.now().strftime('%Y-%m-%d')
    
    def save_state(self):
        """Save bot state to file"""
        try:
            state = {
                'last_standalone_tweet': self.last_standalone_tweet.isoformat(),
                'last_thread': self.last_thread.isoformat(),
                'daily_tweet_count': self.daily_tweet_count,
                'last_tweet_date': self.last_tweet_date
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
            'reply': 5,
            'quote': 7,
            'tweet': 3,
            'thread': 10
        }
        
        delay = base_delay.get(operation_type, 5)
        jitter = random.uniform(0.5, 1.5)  # Add randomness
        total_delay = delay * jitter
        
        logger.info(f"Rate limiting: waiting {total_delay:.1f}s for {operation_type}")
        await asyncio.sleep(total_delay)
    
    async def get_fresh_tweets(self, source_type: str, source: str, limit: int = 20) -> List[Dict]:
        """Get fresh tweets, prioritizing recent ones"""
        try:
            # Fetch more tweets to have better selection
            all_tweets = await fetch_tweets(source_type, source, limit)
            
            if not all_tweets:
                return []
            
            # Sort by creation time (most recent first)
            all_tweets.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            # Filter out already processed tweets
            fresh_tweets = [t for t in all_tweets if t['id'] not in self.last_processed_tweets]
            
            # Only return tweets from last 24 hours for replies/quotes
            if source_type in ['user', 'search']:
                now = datetime.now()
                recent_tweets = []
                for tweet in fresh_tweets:
                    try:
                        tweet_time = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                        # Remove timezone info for comparison
                        tweet_time = tweet_time.replace(tzinfo=None)
                        time_diff = now - tweet_time
                        if time_diff.total_seconds() < 24 * 3600:  # Last 24 hours
                            recent_tweets.append(tweet)
                    except:
                        # If we can't parse the date, include it anyway
                        recent_tweets.append(tweet)
                
                return recent_tweets[:limit//2]  # Return half the requested limit
            
            return fresh_tweets[:limit//2]
            
        except Exception as e:
            logger.error(f"Failed to get fresh tweets: {e}")
            return []
    
    async def run_reply_bot(self, username: str, limit: int = 3) -> List[str]:
        """Generate and post replies to recent tweets from a user"""
        results = []
        
        # Get fresh tweets from user
        tweets = await self.get_fresh_tweets("user", username, limit * 2)
        if not tweets:
            logger.warning(f"No fresh tweets found for @{username}")
            return results
        
        # Limit to requested number
        tweets = tweets[:limit]
        
        for tweet in tweets:
            try:
                # Generate AI reply
                reply_text = await generate_ai_content("reply", tweet['text'])
                if not reply_text:
                    continue
                
                # Post reply
                reply_id = post_content("reply", reply_text, reply_to_id=tweet['id'])
                if reply_id:
                    results.append(reply_id)
                    self.last_processed_tweets.add(tweet['id'])
                    logger.info(f"Posted reply to fresh tweet {tweet['id']} from @{username}")
                
                # Rate limiting
                await self.handle_rate_limit('reply')
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet['id']}: {e}")
                await asyncio.sleep(2)  # Brief pause on error
        
        return results
    
    async def run_quote_bot(self, search_query: str, limit: int = 2) -> List[str]:
        """Generate and post quote tweets for search results"""
        results = []
        
        # Get fresh tweets from search
        tweets = await self.get_fresh_tweets("search", search_query, limit * 2)
        if not tweets:
            logger.warning(f"No fresh tweets found for query: {search_query}")
            return results
        
        # Limit to requested number
        tweets = tweets[:limit]
        
        for tweet in tweets:
            try:
                # Generate AI quote tweet
                quote_text = await generate_ai_content("quote", tweet['text'])
                if not quote_text:
                    continue
                
                # Post quote tweet
                quote_id = post_content("quote", quote_text, quoted_tweet_id=tweet['id'])
                if quote_id:
                    results.append(quote_id)
                    self.last_processed_tweets.add(tweet['id'])
                    logger.info(f"Posted quote tweet for fresh tweet {tweet['id']}")
                
                # Rate limiting
                await self.handle_rate_limit('quote')
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet['id']}: {e}")
                await asyncio.sleep(2)  # Brief pause on error
        
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
        """Run the main 2-hour cycle: 2 replies + 1 quote"""
        logger.info("Starting 2-hour bot cycle...")
        
        # AI/ML related search queries for quote tweets
        search_queries = [
            "artificial intelligence",
            "machine learning", 
            "deep learning",
            "neural networks",
            "AI breakthrough",
            "ChatGPT",
            "OpenAI",
            "transformer models",
            "AI ethics",
            "AGI"
        ]
        
        try:
            total_replies = 0
            total_quotes = 0
            
            # 1. Generate 2 replies from target accounts or search
            if TARGET_ACCOUNTS:
                # Reply to target accounts
                selected_accounts = random.sample(TARGET_ACCOUNTS, min(2, len(TARGET_ACCOUNTS)))
                for username in selected_accounts:
                    username = username.strip()
                    if username:
                        logger.info(f"Processing replies for @{username}")
                        results = await self.run_reply_bot(username, limit=1)
                        total_replies += len(results)
                        
                        # Small delay between accounts
                        await self.handle_rate_limit('reply')
            else:
                # If no target accounts, reply to search results
                for i in range(2):
                    query = random.choice(search_queries)
                    logger.info(f"Searching for replies: {query}")
                    tweets = await self.get_fresh_tweets("search", query, 5)
                    if tweets:
                        tweet = random.choice(tweets)
                        reply_text = await generate_ai_content("reply", tweet['text'])
                        if reply_text:
                            reply_id = post_content("reply", reply_text, reply_to_id=tweet['id'])
                            if reply_id:
                                total_replies += 1
                                self.last_processed_tweets.add(tweet['id'])
                    
                    await self.handle_rate_limit('reply')
            
            # 2. Generate 1 quote tweet from search
            selected_query = random.choice(search_queries)
            logger.info(f"Searching and quoting tweets for: {selected_query}")
            results = await self.run_quote_bot(selected_query, limit=1)
            total_quotes = len(results)
            
            # Clean up old processed tweets (keep only last 500)
            if len(self.last_processed_tweets) > 500:
                old_tweets = list(self.last_processed_tweets)[:200]
                for tweet_id in old_tweets:
                    self.last_processed_tweets.discard(tweet_id)
            
            logger.info(f"2-hour cycle completed - Replies: {total_replies}, Quotes: {total_quotes}")
            
        except Exception as e:
            logger.error(f"Error in 2-hour cycle: {e}")
    
    async def run_standalone_cycle(self):
        """Post standalone tweets (4 per day, randomly distributed)"""
        if self.should_post_standalone_tweet():
            logger.info("Posting standalone tweet")
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
                "AI in everyday life"
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
        self.running = True
        
        # Run initial cycle
        await self.run_2hour_cycle()
        
        last_2hour_run = time.time()
        last_standalone_check = time.time()
        last_thread_check = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for 2-hour cycle (2 replies + 1 quote)
                if current_time - last_2hour_run >= 7200:  # 2 hours = 7200 seconds
                    await self.run_2hour_cycle()
                    last_2hour_run = current_time
                
                # Check for standalone tweets (randomly throughout the day)
                if current_time - last_standalone_check >= 3600:  # Check every hour
                    # Random chance to post (to distribute 4 tweets across the day)
                    if random.random() < 0.3:  # 30% chance each hour
                        await self.run_standalone_cycle()
                    last_standalone_check = current_time
                
                # Check for threads (every 6 hours)
                if current_time - last_thread_check >= 21600:  # 6 hours
                    await self.run_thread_cycle()
                    last_thread_check = current_time
                
                # Save state
                self.save_state()
                
                # Sleep for 10 minutes before next check
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
    parser.add_argument("--target", help="Target username for reply mode")
    parser.add_argument("--query", help="Search query for quote mode")
    parser.add_argument("--topic", help="Topic for thread/standalone mode")
    parser.add_argument("--limit", type=int, default=2, help="Number of tweets to process")
    parser.add_argument("--tweets", type=int, default=3, help="Number of tweets in thread")
    
    args = parser.parse_args()
    
    bot = TwitterBot()
    
    try:
        if args.mode == "continuous":
            # Run in continuous mode with automatic scheduling
            logger.info("Starting continuous mode - automatic scheduling enabled")
            logger.info("Schedule: 2 replies + 1 quote every 2 hours, 4 standalone tweets/day, 1 thread every 2 days")
            await bot.start_continuous_mode()
        
        elif args.mode == "reply":
            if not args.target:
                logger.error("--target required for reply mode")
                return
            results = await bot.run_reply_bot(args.target, args.limit)
            logger.info(f"Posted {len(results)} replies")
        
        elif args.mode == "quote":
            if not args.query:
                logger.error("--query required for quote mode")
                return
            results = await bot.run_quote_bot(args.query, args.limit)
            logger.info(f"Posted {len(results)} quote tweets")
        
        elif args.mode == "thread":
            if not args.topic:
                logger.error("--topic required for thread mode")
                return
            results = await bot.run_thread_bot(args.topic, args.tweets)
            if results:
                logger.info(f"Posted thread with {len(results)} tweets")
        
        elif args.mode == "standalone":
            if not args.topic:
                logger.error("--topic required for standalone mode")
                return
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
