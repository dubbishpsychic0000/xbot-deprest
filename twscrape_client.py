import asyncio
import json
from pathlib import Path
from typing import List, Dict
from twscrape import API
from config import logger

class TweetScraper:
    def __init__(self):
        self.api = API()
    
    async def setup_sessions(self, session_file: str = "session.json"):
        """
        Load Twitter session cookies from a JSON file for authenticated scraping.
        Expects `session.json` (in the same folder as this script) to be a valid
        twscrape session‐export file (exported via a browser extension or similar).
        If the file is missing or invalid, scraping will proceed but return no results.
        """
        path = Path(session_file)
        if not path.exists():
            logger.warning(f"No session file found at {session_file}. Proceeding without accounts.")
            return

        try:
            # This will load the single-session JSON into twscrape’s account pool.
            await self.api.pool.add_account_from_session_file(session_file)
            logger.info(f"Loaded session from {session_file}")
        except Exception as e:
            logger.error(f"Failed to load session file {session_file}: {e}")
    
    async def get_user_tweets(self, username: str, limit: int = 10) -> List[Dict]:
        """Fetch recent tweets from a specific user (requires a loaded session)."""
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
        """Search for tweets by keyword or hashtag (requires a loaded session)."""
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
        """
        Get “trending” tweets. Note: twscrape no longer offers a direct trending API.
        As a simple fallback, this runs an empty‐query search, which returns recent/popular tweets.
        """
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
    """Main function to fetch tweets based on type (user, search, or trending)."""
    scraper = TweetScraper()
    # Load session cookies before attempting any scrape
    await scraper.setup_sessions()

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
        # Example: after session.json is loaded, fetch the first 5 tweets matching "#AI"
        tweets = await fetch_tweets("search", "#AI", 5)
        print(json.dumps(tweets, indent=2))
    
    asyncio.run(test())
