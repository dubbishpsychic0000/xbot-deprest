import asyncio
import json
import time
from typing import List, Dict, Optional
from twscrape import API, gather
from config import logger
import random

class TweetScraper:
    def __init__(self):
        self.api = API()
        self.last_request_time = 0
        self.min_request_interval = 2.0  # 2 seconds between requests
        self.max_retries = 3
    
    async def _rate_limit_delay(self):
        """Implement rate limiting with random jitter"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            # Add random jitter to avoid synchronized requests
            delay = self.min_request_interval - time_since_last + random.uniform(0.5, 1.5)
            await asyncio.sleep(delay)
        self.last_request_time = time.time()
    
    async def setup_accounts(self, accounts: List[Dict[str, str]]):
        """Add accounts for scraping with improved error handling"""
        successful_accounts = 0
        for account in accounts:
            try:
                await self.api.pool.add_account(
                    account['username'], 
                    account['password'], 
                    account['email'], 
                    account['email_password']
                )
                logger.info(f"Successfully added account: {account['username']}")
                successful_accounts += 1
            except Exception as e:
                logger.error(f"Failed to add account {account['username']}: {e}")
        
        if successful_accounts == 0:
            logger.warning("No accounts were successfully added. Some features may not work.")
        else:
            logger.info(f"Successfully added {successful_accounts}/{len(accounts)} accounts")
        
        return successful_accounts > 0
    
    async def _safe_api_call(self, api_func, *args, **kwargs):
        """Wrapper for API calls with retry logic and rate limiting"""
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit_delay()
                return await api_func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                
                # Wait longer between retries
                wait_time = (2 ** attempt) * 3 + random.uniform(1, 3)
                logger.warning(f"API call failed (attempt {attempt + 1}), retrying in {wait_time:.1f}s: {e}")
                await asyncio.sleep(wait_time)
    
    async def get_user_tweets(self, username: str, limit: int = 10) -> List[Dict]:
        """Fetch recent tweets from a specific user with better error handling"""
        try:
            tweets = []
            
            # Use the safe API call wrapper
            async def fetch_tweets():
                tweet_list = []
                async for tweet in self.api.user_tweets(username, limit=limit):
                    tweet_list.append(tweet)
                return tweet_list
            
            raw_tweets = await self._safe_api_call(fetch_tweets)
            
            for tweet in raw_tweets:
                try:
                    tweet_data = {
                        'id': str(tweet.id),
                        'text': tweet.rawContent or tweet.fullText or "",
                        'user': tweet.user.username if tweet.user else username,
                        'created_at': tweet.date.isoformat() if tweet.date else None,
                        'reply_count': getattr(tweet, 'replyCount', 0) or 0,
                        'retweet_count': getattr(tweet, 'retweetCount', 0) or 0,
                        'like_count': getattr(tweet, 'likeCount', 0) or 0,
                        'quote_count': getattr(tweet, 'quoteCount', 0) or 0,
                        'media': [],
                        'hashtags': [],
                        'mentions': [],
                        'urls': []
                    }
                    
                    # Safely extract media
                    if hasattr(tweet, 'media') and tweet.media:
                        for media in tweet.media:
                            if hasattr(media, 'url'):
                                tweet_data['media'].append(media.url)
                    
                    # Extract hashtags from text
                    if tweet_data['text']:
                        import re
                        hashtags = re.findall(r'#\w+', tweet_data['text'])
                        tweet_data['hashtags'] = hashtags
                        
                        mentions = re.findall(r'@\w+', tweet_data['text'])
                        tweet_data['mentions'] = mentions
                        
                        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', tweet_data['text'])
                        tweet_data['urls'] = urls
                    
                    tweets.append(tweet_data)
                    
                except Exception as tweet_error:
                    logger.warning(f"Error processing individual tweet: {tweet_error}")
                    continue
            
            logger.info(f"Successfully fetched {len(tweets)} tweets from @{username}")
            return tweets
            
        except Exception as e:
            logger.error(f"Failed to fetch tweets from @{username}: {e}")
            return []
    
    async def search_tweets(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for tweets by keyword or hashtag with improved filtering"""
        try:
            tweets = []
            
            async def fetch_search_tweets():
                tweet_list = []
                async for tweet in self.api.search(query, limit=limit * 2):  # Fetch more to filter
                    tweet_list.append(tweet)
                return tweet_list
            
            raw_tweets = await self._safe_api_call(fetch_search_tweets)
            
            for tweet in raw_tweets[:limit]:  # Limit after processing
                try:
                    # Skip retweets and replies if desired
                    if hasattr(tweet, 'rawContent') and tweet.rawContent:
                        if tweet.rawContent.startswith('RT @'):
                            continue  # Skip retweets
                    
                    tweet_data = {
                        'id': str(tweet.id),
                        'text': tweet.rawContent or tweet.fullText or "",
                        'user': tweet.user.username if tweet.user else "unknown",
                        'created_at': tweet.date.isoformat() if tweet.date else None,
                        'reply_count': getattr(tweet, 'replyCount', 0) or 0,
                        'retweet_count': getattr(tweet, 'retweetCount', 0) or 0,
                        'like_count': getattr(tweet, 'likeCount', 0) or 0,
                        'quote_count': getattr(tweet, 'quoteCount', 0) or 0,
                        'media': [],
                        'is_reply': getattr(tweet, 'inReplyToTweetId', None) is not None,
                        'is_quote': getattr(tweet, 'quotedTweet', None) is not None,
                        'query_matched': query.lower() in (tweet.rawContent or "").lower()
                    }
                    
                    # Extract media safely
                    if hasattr(tweet, 'media') and tweet.media:
                        for media in tweet.media:
                            if hasattr(media, 'url'):
                                tweet_data['media'].append(media.url)
                    
                    tweets.append(tweet_data)
                    
                except Exception as tweet_error:
                    logger.warning(f"Error processing search tweet: {tweet_error}")
                    continue
            
            logger.info(f"Found {len(tweets)} tweets for query: '{query}'")
            return tweets
            
        except Exception as e:
            logger.error(f"Failed to search tweets for '{query}': {e}")
            return []
    
    async def get_trending_tweets(self, limit: int = 10, language: str = "en") -> List[Dict]:
        """Get trending tweets with language filtering"""
        try:
            tweets = []
            
            # Use popular hashtags or trending topics as search queries
            trending_queries = [
                "filter:top_tweet lang:en",
                "#trending",
                "#viral",
                "filter:verified lang:en"
            ]
            
            for query in trending_queries:
                try:
                    async def fetch_trending():
                        tweet_list = []
                        async for tweet in self.api.search(query, limit=limit//len(trending_queries) + 2):
                            tweet_list.append(tweet)
                        return tweet_list
                    
                    raw_tweets = await self._safe_api_call(fetch_trending)
                    
                    for tweet in raw_tweets:
                        if len(tweets) >= limit:
                            break
                        
                        try:
                            tweet_data = {
                                'id': str(tweet.id),
                                'text': tweet.rawContent or tweet.fullText or "",
                                'user': tweet.user.username if tweet.user else "unknown",
                                'created_at': tweet.date.isoformat() if tweet.date else None,
                                'reply_count': getattr(tweet, 'replyCount', 0) or 0,
                                'retweet_count': getattr(tweet, 'retweetCount', 0) or 0,
                                'like_count': getattr(tweet, 'likeCount', 0) or 0,
                                'engagement_score': (getattr(tweet, 'likeCount', 0) or 0) + 
                                                  (getattr(tweet, 'retweetCount', 0) or 0) * 2 + 
                                                  (getattr(tweet, 'replyCount', 0) or 0),
                                'media': []
                            }
                            
                            # Only include tweets with decent engagement
                            if tweet_data['engagement_score'] > 5:
                                tweets.append(tweet_data)
                                
                        except Exception as tweet_error:
                            logger.warning(f"Error processing trending tweet: {tweet_error}")
                            continue
                
                except Exception as query_error:
                    logger.warning(f"Error with trending query '{query}': {query_error}")
                    continue
            
            # Sort by engagement score
            tweets.sort(key=lambda x: x.get('engagement_score', 0), reverse=True)
            tweets = tweets[:limit]
            
            logger.info(f"Fetched {len(tweets)} trending tweets")
            return tweets
            
        except Exception as e:
            logger.error(f"Failed to fetch trending tweets: {e}")
            return []

async def fetch_tweets(source_type: str, source_value: str, limit: int = 10, **kwargs) -> List[Dict]:
    """Main function to fetch tweets based on type with enhanced options"""
    scraper = TweetScraper()
    
    try:
        if source_type == "user":
            return await scraper.get_user_tweets(source_value, limit)
        elif source_type == "search":
            return await scraper.search_tweets(source_value, limit)
        elif source_type == "trending":
            language = kwargs.get('language', 'en')
            return await scraper.get_trending_tweets(limit, language)
        else:
            logger.error(f"Invalid source type: {source_type}")
            return []
    except Exception as e:
        logger.error(f"Error in fetch_tweets: {e}")
        return []

async def setup_scraper_accounts(accounts_config: List[Dict[str, str]]) -> bool:
    """Setup scraper accounts and return success status"""
    scraper = TweetScraper()
    return await scraper.setup_accounts(accounts_config)

if __name__ == "__main__":
    async def test():
        print("Testing Twitter scraper...")
        
        # Test search
        tweets = await fetch_tweets("search", "#AI", 5)
        print(f"Search results: {len(tweets)} tweets")
        
        if tweets:
            print(f"Sample tweet: {tweets[0]['text'][:100]}...")
        
        # Test user tweets (use a public account)
        user_tweets = await fetch_tweets("user", "elonmusk", 3)
        print(f"User tweets: {len(user_tweets)} tweets")
        
        # Test trending
        trending = await fetch_tweets("trending", "", 3)
        print(f"Trending tweets: {len(trending)} tweets")
    
    asyncio.run(test())
