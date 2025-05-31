import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
from twscrape import API
from config import logger

@dataclass
class Tweet:
    id: str
    text: str
    user: str
    likes: int
    retweets: int
    replies: int
    created_at: str
    
    @classmethod
    def from_raw(cls, tweet) -> 'Tweet':
        return cls(
            id=str(tweet.id),
            text=tweet.rawContent or tweet.fullText or "",
            user=tweet.user.username if tweet.user else "unknown",
            likes=getattr(tweet, 'likeCount', 0) or 0,
            retweets=getattr(tweet, 'retweetCount', 0) or 0,
            replies=getattr(tweet, 'replyCount', 0) or 0,
            created_at=tweet.date.isoformat() if tweet.date else ""
        )

class TwitterScraper:
    def __init__(self):
        self.api = API()
    
    async def setup(self, accounts: List[Dict[str, str]]) -> bool:
        """Setup Twitter accounts"""
        for acc in accounts:
            try:
                await self.api.pool.add_account(
                    acc['username'], acc['password'], 
                    acc['email'], acc['email_password']
                )
                logger.info(f"Added account: {acc['username']}")
            except Exception as e:
                logger.error(f"Failed to add {acc['username']}: {e}")
                return False
        return True
    
    async def search_tweets(self, query: str, limit: int = 20) -> List[Tweet]:
        """Search tweets by query"""
        tweets = []
        try:
            async for tweet in self.api.search(query, limit=limit):
                tweets.append(Tweet.from_raw(tweet))
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
        return tweets
    
    async def user_tweets(self, username: str, limit: int = 20) -> List[Tweet]:
        """Get user tweets"""
        tweets = []
        try:
            async for tweet in self.api.user_tweets(username, limit=limit):
                tweets.append(Tweet.from_raw(tweet))
        except Exception as e:
            logger.error(f"Failed to get tweets for @{username}: {e}")
        return tweets
    
    async def user_info(self, username: str) -> Optional[Dict]:
        """Get user info"""
        try:
            user = await self.api.user_by_login(username)
            return {
                'username': user.username,
                'name': user.displayname,
                'followers': getattr(user, 'followersCount', 0),
                'following': getattr(user, 'friendsCount', 0),
                'verified': getattr(user, 'verified', False)
            }
        except Exception as e:
            logger.error(f"Failed to get user info for @{username}: {e}")
            return None

# Convenience functions
async def search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Search tweets and return as dicts"""
    scraper = TwitterScraper()
    tweets = await scraper.search_tweets(query, limit)
    return [tweet.__dict__ for tweet in tweets]

async def get_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Get user tweets and return as dicts"""
    scraper = TwitterScraper()
    tweets = await scraper.user_tweets(username, limit)
    return [tweet.__dict__ for tweet in tweets]

async def get_user_info(username: str) -> Optional[Dict]:
    """Get user info"""
    scraper = TwitterScraper()
    return await scraper.user_info(username)

async def setup_accounts(accounts: List[Dict[str, str]]) -> bool:
    """Setup Twitter accounts"""
    scraper = TwitterScraper()
    return await scraper.setup(accounts)

# Usage example
if __name__ == "__main__":
    async def test():
        # Search for tweets
        tweets = await search_tweets("#AI", limit=5)
        print(f"Found {len(tweets)} tweets")
        
        # Get user tweets
        user_tweets_list = await get_user_tweets("elonmusk", limit=3)
        print(f"Got {len(user_tweets_list)} user tweets")
        
        # Get user info
        info = await get_user_info("elonmusk")
        if info:
            print(f"User: {info['name']} (@{info['username']})")
    
    asyncio.run(test())
