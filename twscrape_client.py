import asyncio
import json
from typing import List, Dict, Optional
from twscrape import API, gather
from config import logger

class TweetScraper:
    def __init__(self):
        self.api = API()
    
    async def setup_accounts(self, accounts: List[Dict[str, str]]):
        """Add accounts for scraping (if needed)"""
        for account in accounts:
            try:
                await self.api.pool.add_account(
                    account['username'], 
                    account['password'], 
                    account['email'], 
                    account['email_password']
                )
                logger.info(f"Added account: {account['username']}")
            except Exception as e:
                logger.error(f"Failed to add account {account['username']}: {e}")
    
    async def get_user_tweets(self, username: str, limit: int = 10) -> List[Dict]:
        """Fetch recent tweets from a specific user"""
        try:
            tweets = []
            async for tweet in self.api.user_tweets(username, limit=limit):
                tweets.append({
                    'id': tweet.id,
                    'text': tweet.rawContent,
                    'user': tweet.user.username,
                    'created_at': tweet.date.isoformat(),
                    'reply_count': tweet.replyCount,
                    'retweet_count': tweet.retweetCount,
                    'like_count': tweet.likeCount,
                    'media': [media.url for media in tweet.media] if tweet.media else []
                })
            logger.info(f"Fetched {len(tweets)} tweets from @{username}")
            return tweets
        except Exception as e:
            logger.error(f"Failed to fetch tweets from @{username}: {e}")
            return []
    
    async def search_tweets(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for tweets by keyword or hashtag"""
        try:
            tweets = []
            async for tweet in self.api.search(query, limit=limit):
                tweets.append({
                    'id': tweet.id,
                    'text': tweet.rawContent,
                    'user': tweet.user.username,
                    'created_at': tweet.date.isoformat(),
                    'reply_count': tweet.replyCount,
                    'retweet_count': tweet.retweetCount,
                    'like_count': tweet.likeCount,
                    'media': [media.url for media in tweet.media] if tweet.media else []
                })
            logger.info(f"Found {len(tweets)} tweets for query: {query}")
            return tweets
        except Exception as e:
            logger.error(f"Failed to search tweets for '{query}': {e}")
            return []
    
    async def get_trending_tweets(self, limit: int = 10) -> List[Dict]:
        """Get trending tweets"""
        try:
            tweets = []
            async for tweet in self.api.search("", limit=limit):
                tweets.append({
                    'id': tweet.id,
                    'text': tweet.rawContent,
                    'user': tweet.user.username,
                    'created_at': tweet.date.isoformat(),
                    'reply_count': tweet.replyCount,
                    'retweet_count': tweet.retweetCount,
                    'like_count': tweet.likeCount,
                    'media': [media.url for media in tweet.media] if tweet.media else []
                })
            logger.info(f"Fetched {len(tweets)} trending tweets")
            return tweets
        except Exception as e:
            logger.error(f"Failed to fetch trending tweets: {e}")
            return []

async def fetch_tweets(source_type: str, source_value: str, limit: int = 10) -> List[Dict]:
    """Main function to fetch tweets based on type"""
    scraper = TweetScraper()
    
    if source_type == "user":
        return await scraper.get_user_tweets(source_value, limit)
    elif source_type == "search":
        return await scraper.search_tweets(source_value, limit)
    elif source_type == "trending":
        return await scraper.get_trending_tweets(limit)
    else:
        logger.error(f"Invalid source type: {source_type}")
        return []

if __name__ == "__main__":
    async def test():
        tweets = await fetch_tweets("search", "#AI", 5)
        print(json.dumps(tweets, indent=2))
    
    asyncio.run(test())