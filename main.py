import asyncio
import argparse
import random
from typing import Dict, List, Optional
from config import logger, validate_config
from twscrape_client import fetch_tweets
from media_handler import process_tweet_media
from ai_generator import generate_ai_content
from poster import post_content

class TwitterBot:
    def __init__(self):
        self.validate_setup()
    
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
            try:
                # Generate AI reply
                reply_text = await generate_ai_content("reply", tweet['text'])
                if not reply_text:
                    continue
                
                # Post reply
                reply_id = post_content("reply", reply_text, reply_to_id=tweet['id'])
                if reply_id:
                    results.append(reply_id)
                    logger.info(f"Posted reply to tweet {tweet['id']}")
                
                # Rate limiting
                await asyncio.sleep(2)
                
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
            try:
                # Generate AI quote tweet
                quote_text = await generate_ai_content("quote", tweet['text'])
                if not quote_text:
                    continue
                
                # Post quote tweet
                quote_id = post_content("quote", quote_text, quoted_tweet_id=tweet['id'])
                if quote_id:
                    results.append(quote_id)
                    logger.info(f"Posted quote tweet for {tweet['id']}")
                
                # Rate limiting
                await asyncio.sleep(2)
                
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
            if tweet.get('media'):
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
                            logger.info(f"Posted media reply to {tweet['id']}")
                    
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Failed to process media tweet {tweet['id']}: {e}")
        
        return results

async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="AI-Powered Twitter Bot")
    parser.add_argument("mode", choices=["reply", "quote", "thread", "standalone", "media"], help="Bot operation mode")
    parser.add_argument("--target", help="Target username for reply/media mode")
    parser.add_argument("--query", help="Search query for quote mode")
    parser.add_argument("--topic", help="Topic for thread/standalone mode")
    parser.add_argument("--limit", type=int, default=5, help="Number of tweets to process")
    parser.add_argument("--tweets", type=int, default=3, help="Number of tweets in thread")
    
    args = parser.parse_args()
    
    bot = TwitterBot()
    
    try:
        if args.mode == "reply":
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
    except Exception as e:
        logger.error(f"Bot execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())