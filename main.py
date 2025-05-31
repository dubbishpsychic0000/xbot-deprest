import asyncio
import argparse
import random
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from config import logger, validate_config, TARGET_ACCOUNTS
from twscrape_client import fetch_tweets
from media_handler import process_tweet_media
from ai_generator import generate_ai_content
from poster import post_content

class TwitterBot:
    def __init__(self):
        self.validate_setup()
        self.last_processed_tweets = set()  # Track processed tweets to avoid duplicates
        self.running = False
        
    def validate_setup(self):
        """Validate configuration and setup"""
        try:
            validate_config()
            logger.info("Bot initialized successfully")
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            raise
    
    async def run_reply_bot(self, username: str, limit: int = 5) -> List[str]:
        """Generate and post replies to recent tweets from a user"""
        results = []
        
        # Fetch tweets
        tweets = await fetch_tweets("user", username, limit)
        if not tweets:
            logger.warning(f"No tweets found for @{username}")
            return results
        
        for tweet in tweets:
            # Skip if we've already processed this tweet
            if tweet['id'] in self.last_processed_tweets:
                continue
                
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
                    logger.info(f"Posted reply to tweet {tweet['id']} from @{username}")
                
                # Rate limiting
                await asyncio.sleep(random.randint(3, 7))
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet['id']}: {e}")
        
        return results
    
    async def run_quote_bot(self, search_query: str, limit: int = 3) -> List[str]:
        """Generate and post quote tweets for search results"""
        results = []
        
        # Fetch tweets
        tweets = await fetch_tweets("search", search_query, limit)
        if not tweets:
            logger.warning(f"No tweets found for query: {search_query}")
            return results
        
        for tweet in tweets:
            # Skip if we've already processed this tweet
            if tweet['id'] in self.last_processed_tweets:
                continue
                
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
                    logger.info(f"Posted quote tweet for {tweet['id']}")
                
                # Rate limiting
                await asyncio.sleep(random.randint(3, 7))
                
            except Exception as e:
                logger.error(f"Failed to process tweet {tweet['id']}: {e}")
        
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
                logger.info(f"Posted standalone tweet: {tweet_id}")
                return tweet_id
            
        except Exception as e:
            logger.error(f"Failed to create standalone tweet: {e}")
        
        return None
    
    async def run_media_bot(self, username: str) -> List[str]:
        """Process tweets with media and generate replies"""
        results = []
        
        # Fetch tweets
        tweets = await fetch_tweets("user", username, 10)
        if not tweets:
            return results
        
        for tweet in tweets:
            if tweet.get('media') and tweet['id'] not in self.last_processed_tweets:
                try:
                    # Download media
                    media_paths = await process_tweet_media(tweet)
                    
                    # Generate reply with media context
                    context = f"Original tweet has {len(tweet['media'])} media files"
                    reply_text = await generate_ai_content("reply", tweet['text'], context=context)
                    
                    if reply_text:
                        reply_id = post_content("reply", reply_text, reply_to_id=tweet['id'])
                        if reply_id:
                            results.append(reply_id)
                            self.last_processed_tweets.add(tweet['id'])
                            logger.info(f"Posted media reply to {tweet['id']}")
                    
                    await asyncio.sleep(random.randint(3, 7))
                    
                except Exception as e:
                    logger.error(f"Failed to process media tweet {tweet['id']}: {e}")
        
        return results
    
    async def run_hourly_cycle(self):
        """Run the main hourly cycle for replies and quotes"""
        logger.info("Starting hourly bot cycle...")
        
        # AI/ML related search queries for quote tweets
        search_queries = [
            "artificial intelligence",
            "machine learning", 
            "deep learning",
            "neural networks",
            "AI breakthrough",
            "ChatGPT OR GPT-4",
            "OpenAI",
            "transformer models",
            "AI ethics",
            "AGI artificial general intelligence"
        ]
        
        try:
            # 1. Reply to target accounts
            reply_results = []
            if TARGET_ACCOUNTS:
                for username in TARGET_ACCOUNTS[:3]:  # Limit to 3 accounts per cycle
                    username = username.strip()
                    if username:
                        logger.info(f"Processing replies for @{username}")
                        results = await self.run_reply_bot(username, limit=3)
                        reply_results.extend(results)
                        
                        # Small delay between accounts
                        await asyncio.sleep(random.randint(5, 10))
            
            # 2. Generate quote tweets from search
            quote_results = []
            selected_queries = random.sample(search_queries, min(2, len(search_queries)))
            
            for query in selected_queries:
                logger.info(f"Searching and quoting tweets for: {query}")
                results = await self.run_quote_bot(query, limit=2)
                quote_results.extend(results)
                
                # Delay between search queries
                await asyncio.sleep(random.randint(10, 15))
            
            # 3. Occasionally post a standalone tweet (20% chance)
            standalone_result = None
            if random.random() < 0.2:
                logger.info("Posting standalone tweet")
                standalone_result = await self.run_standalone_bot("AI and machine learning")
            
            # Clean up old processed tweets (keep only last 1000)
            if len(self.last_processed_tweets) > 1000:
                # Remove oldest 200 entries
                old_tweets = list(self.last_processed_tweets)[:200]
                for tweet_id in old_tweets:
                    self.last_processed_tweets.discard(tweet_id)
            
            logger.info(f"Hourly cycle completed - Replies: {len(reply_results)}, Quotes: {len(quote_results)}, Standalone: {1 if standalone_result else 0}")
            
        except Exception as e:
            logger.error(f"Error in hourly cycle: {e}")
    
    async def start_continuous_mode(self):
        """Start the bot in continuous mode with hourly cycles"""
        logger.info("Starting Twitter bot in continuous mode...")
        self.running = True
        
        # Run first cycle immediately
        await self.run_hourly_cycle()
        
        # Then run every hour
        while self.running:
            try:
                # Wait for next hour
                await asyncio.sleep(3600)  # 1 hour = 3600 seconds
                
                if self.running:
                    await self.run_hourly_cycle()
                    
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
        logger.info("Bot stopping...")

async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="AI-Powered Twitter Bot")
    parser.add_argument("mode", 
                       choices=["reply", "quote", "thread", "standalone", "media", "continuous"], 
                       help="Bot operation mode")
    parser.add_argument("--target", help="Target username for reply/media mode")
    parser.add_argument("--query", help="Search query for quote mode")
    parser.add_argument("--topic", help="Topic for thread/standalone mode")
    parser.add_argument("--limit", type=int, default=5, help="Number of tweets to process")
    parser.add_argument("--tweets", type=int, default=3, help="Number of tweets in thread")
    
    args = parser.parse_args()
    
    bot = TwitterBot()
    
    try:
        if args.mode == "continuous":
            # Run in continuous mode with hourly cycles
            logger.info("Starting continuous mode - bot will run hourly cycles")
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
        
        elif args.mode == "media":
            if not args.target:
                logger.error("--target required for media mode")
                return
            results = await bot.run_media_bot(args.target)
            logger.info(f"Posted {len(results)} media replies")
    
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        bot.stop()
    except Exception as e:
        logger.error(f"Bot execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
