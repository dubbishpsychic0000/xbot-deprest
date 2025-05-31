import asyncio
import json
import time
import random
import hashlib
from typing import List, Dict, Optional, Union, AsyncGenerator
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import logging
from contextlib import asynccontextmanager
import aiohttp
from twscrape import API, gather
from config import logger

class ContentType(Enum):
    """Content filtering types"""
    ALL = "all"
    ORIGINAL = "original"  # No retweets
    MEDIA = "media"       # Only tweets with media
    REPLIES = "replies"   # Only replies
    NO_REPLIES = "no_replies"  # Exclude replies

@dataclass
class TweetData:
    """Structured tweet data model"""
    id: str
    text: str
    user: str
    user_id: Optional[str]
    created_at: str
    reply_count: int
    retweet_count: int
    like_count: int
    quote_count: int
    view_count: int
    engagement_score: float
    media: List[str]
    hashtags: List[str]
    mentions: List[str]
    urls: List[str]
    is_reply: bool
    is_quote: bool
    is_retweet: bool
    language: Optional[str]
    source: Optional[str]
    verified_user: bool
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_tweet(cls, tweet, query: Optional[str] = None) -> 'TweetData':
        """Create TweetData from raw tweet object"""
        try:
            # Extract text content
            text = tweet.rawContent or tweet.fullText or ""
            
            # Calculate engagement score with weighted metrics
            like_count = getattr(tweet, 'likeCount', 0) or 0
            retweet_count = getattr(tweet, 'retweetCount', 0) or 0
            reply_count = getattr(tweet, 'replyCount', 0) or 0
            quote_count = getattr(tweet, 'quoteCount', 0) or 0
            view_count = getattr(tweet, 'viewCount', 0) or 0
            
            engagement_score = (
                like_count * 1.0 +
                retweet_count * 2.0 +
                reply_count * 1.5 +
                quote_count * 1.8 +
                view_count * 0.001
            )
            
            # Extract media URLs
            media = []
            if hasattr(tweet, 'media') and tweet.media:
                for media_item in tweet.media:
                    if hasattr(media_item, 'url'):
                        media.append(media_item.url)
                    elif hasattr(media_item, 'mediaUrlHttps'):
                        media.append(media_item.mediaUrlHttps)
            
            # Extract hashtags, mentions, and URLs using regex
            import re
            hashtags = re.findall(r'#\w+', text)
            mentions = re.findall(r'@\w+', text)
            urls = re.findall(
                r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
                text
            )
            
            return cls(
                id=str(tweet.id),
                text=text,
                user=tweet.user.username if tweet.user else "unknown",
                user_id=str(tweet.user.id) if tweet.user and hasattr(tweet.user, 'id') else None,
                created_at=tweet.date.isoformat() if tweet.date else datetime.now(timezone.utc).isoformat(),
                reply_count=reply_count,
                retweet_count=retweet_count,
                like_count=like_count,
                quote_count=quote_count,
                view_count=view_count,
                engagement_score=engagement_score,
                media=media,
                hashtags=hashtags,
                mentions=mentions,
                urls=urls,
                is_reply=getattr(tweet, 'inReplyToTweetId', None) is not None,
                is_quote=getattr(tweet, 'quotedTweet', None) is not None,
                is_retweet=text.startswith('RT @'),
                language=getattr(tweet, 'lang', None),
                source=getattr(tweet, 'source', None),
                verified_user=getattr(tweet.user, 'verified', False) if tweet.user else False
            )
        except Exception as e:
            logger.error(f"Error creating TweetData: {e}")
            raise

class AdvancedTweetScraper:
    """Enhanced Twitter scraper with improved error handling and features"""
    
    def __init__(self, 
                 min_request_interval: float = 2.0,
                 max_retries: int = 3,
                 timeout: int = 30,
                 enable_cache: bool = True):
        self.api = API()
        self.last_request_time = 0
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_cache = enable_cache
        self._cache = {} if enable_cache else None
        self._session = None
        
        # Rate limiting settings
        self.requests_per_window = 100
        self.window_duration = 900  # 15 minutes
        self.request_timestamps = []
        
    async def __aenter__(self):
        """Async context manager entry"""
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._session:
            await self._session.close()
    
    def _generate_cache_key(self, source_type: str, source_value: str, **kwargs) -> str:
        """Generate cache key for requests"""
        key_data = f"{source_type}:{source_value}:{json.dumps(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict, max_age: int = 300) -> bool:
        """Check if cache entry is still valid (default 5 minutes)"""
        return time.time() - cache_entry['timestamp'] < max_age
    
    async def _advanced_rate_limit(self):
        """Advanced rate limiting with sliding window"""
        current_time = time.time()
        
        # Remove old timestamps outside the window
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < self.window_duration
        ]
        
        # Check if we're hitting rate limits
        if len(self.request_timestamps) >= self.requests_per_window:
            oldest_request = min(self.request_timestamps)
            sleep_time = self.window_duration - (current_time - oldest_request)
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping for {sleep_time:.1f} seconds")
                await asyncio.sleep(sleep_time)
        
        # Regular interval rate limiting with jitter
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            jitter = random.uniform(0.1, 0.5)
            delay = self.min_request_interval - time_since_last + jitter
            await asyncio.sleep(delay)
        
        # Record this request
        self.last_request_time = time.time()
        self.request_timestamps.append(self.last_request_time)
    
    async def setup_accounts(self, accounts: List[Dict[str, str]]) -> bool:
        """Enhanced account setup with validation"""
        successful_accounts = 0
        failed_accounts = []
        
        for i, account in enumerate(accounts):
            try:
                # Validate account structure
                required_fields = ['username', 'password', 'email', 'email_password']
                if not all(field in account for field in required_fields):
                    logger.error(f"Account {i+1} missing required fields: {required_fields}")
                    failed_accounts.append(account.get('username', f'account_{i+1}'))
                    continue
                
                await self.api.pool.add_account(
                    account['username'], 
                    account['password'], 
                    account['email'], 
                    account['email_password']
                )
                logger.info(f"✓ Successfully added account: {account['username']}")
                successful_accounts += 1
                
                # Small delay between account additions
                await asyncio.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"✗ Failed to add account {account.get('username', f'account_{i+1}')}: {e}")
                failed_accounts.append(account.get('username', f'account_{i+1}'))
        
        if successful_accounts == 0:
            logger.critical("⚠️  No accounts were successfully added. Scraper will not function properly.")
            return False
        
        logger.info(f"📊 Account setup complete: {successful_accounts}/{len(accounts)} successful")
        if failed_accounts:
            logger.warning(f"Failed accounts: {', '.join(failed_accounts)}")
        
        return True
    
    async def _robust_api_call(self, api_func, *args, **kwargs):
        """Enhanced API call wrapper with exponential backoff"""
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                await self._advanced_rate_limit()
                result = await asyncio.wait_for(api_func(*args, **kwargs), timeout=self.timeout)
                return result
                
            except asyncio.TimeoutError:
                last_exception = Exception("Request timeout")
                wait_time = min(60, (2 ** attempt) * 5)  # Cap at 60 seconds
                
            except Exception as e:
                last_exception = e
                
                # Handle specific error types
                if "rate limit" in str(e).lower():
                    wait_time = min(300, (2 ** attempt) * 30)  # Longer wait for rate limits
                elif "authorization" in str(e).lower():
                    logger.error(f"Authorization error - check account credentials: {e}")
                    raise e
                else:
                    wait_time = min(60, (2 ** attempt) * 3)
            
            if attempt < self.max_retries - 1:
                jitter = random.uniform(0.5, 1.5)
                total_wait = wait_time + jitter
                logger.warning(f"🔄 API call failed (attempt {attempt + 1}/{self.max_retries}), "
                             f"retrying in {total_wait:.1f}s: {last_exception}")
                await asyncio.sleep(total_wait)
        
        logger.error(f"❌ API call failed after {self.max_retries} attempts")
        raise last_exception
    
    def _filter_tweets(self, tweets: List[TweetData], content_type: ContentType) -> List[TweetData]:
        """Filter tweets based on content type"""
        if content_type == ContentType.ALL:
            return tweets
        elif content_type == ContentType.ORIGINAL:
            return [t for t in tweets if not t.is_retweet]
        elif content_type == ContentType.MEDIA:
            return [t for t in tweets if t.media]
        elif content_type == ContentType.REPLIES:
            return [t for t in tweets if t.is_reply]
        elif content_type == ContentType.NO_REPLIES:
            return [t for t in tweets if not t.is_reply]
        return tweets
    
    async def get_user_tweets(self, 
                            username: str, 
                            limit: int = 20,
                            content_type: ContentType = ContentType.ALL,
                            include_replies: bool = False) -> List[TweetData]:
        """Enhanced user tweet fetching with filtering options"""
        cache_key = self._generate_cache_key("user", username, limit=limit, content_type=content_type.value)
        
        # Check cache
        if self._cache and cache_key in self._cache:
            if self._is_cache_valid(self._cache[cache_key]):
                logger.info(f"📋 Using cached data for @{username}")
                return self._cache[cache_key]['data']
        
        try:
            tweets = []
            
            async def fetch_user_tweets():
                tweet_list = []
                count = 0
                async for tweet in self.api.user_tweets(username, limit=limit * 2):  # Fetch extra for filtering
                    tweet_list.append(tweet)
                    count += 1
                    if count >= limit * 2:  # Safety limit
                        break
                return tweet_list
            
            raw_tweets = await self._robust_api_call(fetch_user_tweets)
            
            for tweet in raw_tweets:
                try:
                    tweet_data = TweetData.from_tweet(tweet)
                    tweets.append(tweet_data)
                    
                except Exception as tweet_error:
                    logger.warning(f"⚠️  Error processing tweet {getattr(tweet, 'id', 'unknown')}: {tweet_error}")
                    continue
            
            # Filter tweets based on content type
            filtered_tweets = self._filter_tweets(tweets, content_type)[:limit]
            
            # Cache the results
            if self._cache:
                self._cache[cache_key] = {
                    'data': filtered_tweets,
                    'timestamp': time.time()
                }
            
            logger.info(f"✅ Fetched {len(filtered_tweets)} tweets from @{username} "
                       f"(filtered from {len(tweets)} total)")
            return filtered_tweets
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch tweets from @{username}: {e}")
            return []
    
    async def search_tweets(self, 
                          query: str, 
                          limit: int = 20,
                          content_type: ContentType = ContentType.ORIGINAL,
                          sort_by: str = "engagement") -> List[TweetData]:
        """Enhanced tweet search with advanced filtering and sorting"""
        cache_key = self._generate_cache_key("search", query, limit=limit, content_type=content_type.value)
        
        # Check cache
        if self._cache and cache_key in self._cache:
            if self._is_cache_valid(self._cache[cache_key]):
                logger.info(f"📋 Using cached search results for '{query}'")
                return self._cache[cache_key]['data']
        
        try:
            tweets = []
            
            async def fetch_search_tweets():
                tweet_list = []
                count = 0
                async for tweet in self.api.search(query, limit=limit * 3):  # Fetch more for better filtering
                    tweet_list.append(tweet)
                    count += 1
                    if count >= limit * 3:
                        break
                return tweet_list
            
            raw_tweets = await self._robust_api_call(fetch_search_tweets)
            
            for tweet in raw_tweets:
                try:
                    tweet_data = TweetData.from_tweet(tweet, query)
                    tweets.append(tweet_data)
                    
                except Exception as tweet_error:
                    logger.warning(f"⚠️  Error processing search tweet: {tweet_error}")
                    continue
            
            # Filter tweets
            filtered_tweets = self._filter_tweets(tweets, content_type)
            
            # Sort tweets
            if sort_by == "engagement":
                filtered_tweets.sort(key=lambda x: x.engagement_score, reverse=True)
            elif sort_by == "recent":
                filtered_tweets.sort(key=lambda x: x.created_at, reverse=True)
            elif sort_by == "likes":
                filtered_tweets.sort(key=lambda x: x.like_count, reverse=True)
            elif sort_by == "retweets":
                filtered_tweets.sort(key=lambda x: x.retweet_count, reverse=True)
            
            # Apply limit after filtering and sorting
            result_tweets = filtered_tweets[:limit]
            
            # Cache results
            if self._cache:
                self._cache[cache_key] = {
                    'data': result_tweets,
                    'timestamp': time.time()
                }
            
            logger.info(f"🔍 Found {len(result_tweets)} tweets for '{query}' "
                       f"(filtered from {len(tweets)} total)")
            return result_tweets
            
        except Exception as e:
            logger.error(f"❌ Failed to search tweets for '{query}': {e}")
            return []
    
    async def get_trending_tweets(self, 
                                limit: int = 20, 
                                language: str = "en",
                                min_engagement: int = 10) -> List[TweetData]:
        """Enhanced trending tweets with better discovery and filtering"""
        cache_key = self._generate_cache_key("trending", language, limit=limit, min_engagement=min_engagement)
        
        # Check cache
        if self._cache and cache_key in self._cache:
            if self._is_cache_valid(self._cache[cache_key], max_age=180):  # 3 minutes for trending
                logger.info(f"📋 Using cached trending tweets")
                return self._cache[cache_key]['data']
        
        try:
            all_tweets = []
            
            # Enhanced trending search queries
            trending_queries = [
                f"filter:top_tweet lang:{language}",
                f"filter:verified lang:{language}",
                f"min_replies:5 lang:{language}",
                f"min_faves:50 lang:{language}",
                "#trending",
                "#viral",
                "#breaking",
                "filter:news",
            ]
            
            tweets_per_query = max(1, limit // len(trending_queries))
            
            for query in trending_queries:
                try:
                    async def fetch_trending():
                        tweet_list = []
                        count = 0
                        async for tweet in self.api.search(query, limit=tweets_per_query * 2):
                            tweet_list.append(tweet)
                            count += 1
                            if count >= tweets_per_query * 2:
                                break
                        return tweet_list
                    
                    raw_tweets = await self._robust_api_call(fetch_trending)
                    
                    for tweet in raw_tweets:
                        try:
                            tweet_data = TweetData.from_tweet(tweet)
                            
                            # Filter by engagement threshold
                            if tweet_data.engagement_score >= min_engagement:
                                all_tweets.append(tweet_data)
                                
                        except Exception as tweet_error:
                            logger.warning(f"⚠️  Error processing trending tweet: {tweet_error}")
                            continue
                
                except Exception as query_error:
                    logger.warning(f"⚠️  Error with trending query '{query}': {query_error}")
                    continue
                
                # Small delay between queries
                await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Remove duplicates and sort by engagement
            unique_tweets = {}
            for tweet in all_tweets:
                if tweet.id not in unique_tweets:
                    unique_tweets[tweet.id] = tweet
            
            result_tweets = list(unique_tweets.values())
            result_tweets.sort(key=lambda x: x.engagement_score, reverse=True)
            result_tweets = result_tweets[:limit]
            
            # Cache results
            if self._cache:
                self._cache[cache_key] = {
                    'data': result_tweets,
                    'timestamp': time.time()
                }
            
            logger.info(f"🔥 Fetched {len(result_tweets)} trending tweets")
            return result_tweets
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch trending tweets: {e}")
            return []
    
    async def get_user_info(self, username: str) -> Optional[Dict]:
        """Get detailed user information"""
        try:
            async def fetch_user():
                return await self.api.user_by_login(username)
            
            user = await self._robust_api_call(fetch_user)
            
            if user:
                return {
                    'id': str(user.id),
                    'username': user.username,
                    'display_name': user.displayname,
                    'description': user.rawDescription or "",
                    'followers_count': getattr(user, 'followersCount', 0),
                    'following_count': getattr(user, 'friendsCount', 0),
                    'tweets_count': getattr(user, 'statusesCount', 0),
                    'verified': getattr(user, 'verified', False),
                    'created_at': user.created.isoformat() if hasattr(user, 'created') and user.created else None,
                    'profile_image': getattr(user, 'profileImageUrlHttps', ''),
                    'banner_image': getattr(user, 'profileBannerUrl', ''),
                    'location': getattr(user, 'location', ''),
                    'url': getattr(user, 'url', '')
                }
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch user info for @{username}: {e}")
            return None
    
    def clear_cache(self):
        """Clear the request cache"""
        if self._cache:
            self._cache.clear()
            logger.info("🗑️  Cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        if not self._cache:
            return {"cache_enabled": False}
        
        return {
            "cache_enabled": True,
            "entries": len(self._cache),
            "size_mb": len(json.dumps(self._cache)) / (1024 * 1024)
        }

# Convenience functions for easy usage
async def fetch_tweets(source_type: str, 
                      source_value: str, 
                      limit: int = 20,
                      content_type: str = "original",
                      sort_by: str = "engagement",
                      **kwargs) -> List[Dict]:
    """Enhanced main function with more options"""
    
    content_type_enum = ContentType(content_type) if content_type in [ct.value for ct in ContentType] else ContentType.ORIGINAL
    
    async with AdvancedTweetScraper() as scraper:
        try:
            if source_type == "user":
                tweets = await scraper.get_user_tweets(
                    source_value, 
                    limit=limit, 
                    content_type=content_type_enum
                )
            elif source_type == "search":
                tweets = await scraper.search_tweets(
                    source_value, 
                    limit=limit, 
                    content_type=content_type_enum,
                    sort_by=sort_by
                )
            elif source_type == "trending":
                min_engagement = kwargs.get('min_engagement', 10)
                language = kwargs.get('language', 'en')
                tweets = await scraper.get_trending_tweets(
                    limit=limit, 
                    language=language,
                    min_engagement=min_engagement
                )
            else:
                logger.error(f"❌ Invalid source type: {source_type}")
                return []
            
            return [tweet.to_dict() for tweet in tweets]
            
        except Exception as e:
            logger.error(f"❌ Error in fetch_tweets: {e}")
            return []

async def setup_scraper_accounts(accounts_config: List[Dict[str, str]]) -> bool:
    """Setup scraper accounts with validation"""
    async with AdvancedTweetScraper() as scraper:
        return await scraper.setup_accounts(accounts_config)

async def get_user_profile(username: str) -> Optional[Dict]:
    """Get user profile information"""
    async with AdvancedTweetScraper() as scraper:
        return await scraper.get_user_info(username)

# Advanced batch processing
async def batch_fetch_tweets(requests: List[Dict], 
                           max_concurrent: int = 3,
                           delay_between_batches: float = 2.0) -> List[Dict]:
    """Process multiple tweet fetch requests concurrently"""
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    
    async def process_request(request: Dict) -> Dict:
        async with semaphore:
            try:
                tweets = await fetch_tweets(**request)
                return {
                    'request': request,
                    'tweets': tweets,
                    'success': True,
                    'count': len(tweets)
                }
            except Exception as e:
                logger.error(f"❌ Batch request failed: {e}")
                return {
                    'request': request,
                    'tweets': [],
                    'success': False,
                    'error': str(e)
                }
    
    # Process requests in batches
    batch_size = max_concurrent
    for i in range(0, len(requests), batch_size):
        batch = requests[i:i + batch_size]
        batch_results = await asyncio.gather(*[process_request(req) for req in batch])
        results.extend(batch_results)
        
        # Delay between batches
        if i + batch_size < len(requests):
            await asyncio.sleep(delay_between_batches)
    
    logger.info(f"📊 Batch processing complete: {len(results)} requests processed")
    return results

if __name__ == "__main__":
    async def comprehensive_test():
        """Comprehensive test suite"""
        print("🚀 Starting comprehensive Twitter scraper test...\n")
        
        async with AdvancedTweetScraper() as scraper:
            # Test 1: Search tweets
            print("1️⃣  Testing search functionality...")
            search_tweets = await scraper.search_tweets(
                "#AI", 
                limit=5, 
                content_type=ContentType.ORIGINAL,
                sort_by="engagement"
            )
            print(f"   ✅ Found {len(search_tweets)} AI-related tweets")
            if search_tweets:
                top_tweet = search_tweets[0]
                print(f"   📊 Top tweet: {top_tweet.text[:100]}...")
                print(f"   💫 Engagement: {top_tweet.engagement_score:.1f}")
            
            # Test 2: User tweets
            print("\n2️⃣  Testing user tweets...")
            user_tweets = await scraper.get_user_tweets(
                "elonmusk", 
                limit=3,
                content_type=ContentType.ORIGINAL
            )
            print(f"   ✅ Fetched {len(user_tweets)} tweets from @elonmusk")
            
            # Test 3: Trending tweets
            print("\n3️⃣  Testing trending tweets...")
            trending = await scraper.get_trending_tweets(
                limit=3,
                min_engagement=20
            )
            print(f"   ✅ Found {len(trending)} trending tweets")
            
            # Test 4: User info
            print("\n4️⃣  Testing user info...")
            user_info = await scraper.get_user_info("elonmusk")
            if user_info:
                print(f"   ✅ User info: {user_info['display_name']} "
                      f"({user_info['followers_count']:,} followers)")
            
            # Test 5: Cache stats
            print("\n5️⃣  Cache statistics...")
            cache_stats = scraper.get_cache_stats()
            print(f"   📊 Cache: {cache_stats}")
        
        # Test 6: Batch processing
        print("\n6️⃣  Testing batch processing...")
        batch_requests = [
            {"source_type": "search", "source_value": "#Python", "limit": 2},
            {"source_type": "search", "source_value": "#JavaScript", "limit": 2},
            {"source_type": "user", "source_value": "github", "limit": 2}
        ]
        batch_results = await batch_fetch_tweets(batch_requests, max_concurrent=2)
        print(f"   ✅ Batch processing: {len(batch_results)} requests completed")
        
        print("\n🎉 All tests completed successfully!")
    
    # Run the comprehensive test
    asyncio.run(comprehensive_test())
