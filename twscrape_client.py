import asyncio
import json
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, asdict
from twscrape import API, Tweet as RawTweet
from config import logger
import re
from urllib.parse import urlparse

@dataclass
class MediaItem:
    """Represents a media item in a tweet"""
    type: str  # 'photo', 'video', 'animated_gif'
    url: str
    preview_url: Optional[str] = None
    alt_text: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

@dataclass
class Tweet:
    """Enhanced Tweet dataclass with media support"""
    id: str
    text: str
    user: str
    user_id: str
    user_display_name: str
    likes: int
    retweets: int
    replies: int
    quotes: int
    views: int
    created_at: str
    media: List[MediaItem]
    urls: List[str]
    hashtags: List[str]
    mentions: List[str]
    is_reply: bool
    is_retweet: bool
    is_quote: bool
    lang: Optional[str] = None
    source: Optional[str] = None
    
    @classmethod
    def from_raw(cls, tweet: RawTweet) -> 'Tweet':
        """Convert raw tweet to our Tweet format with enhanced media extraction"""
        
        # Extract media
        media_items = []
        if hasattr(tweet, 'media') and tweet.media:
            for media in tweet.media:
                media_type = getattr(media, 'type', 'unknown')
                
                # Get the best quality media URL
                media_url = None
                preview_url = None
                
                if media_type == 'photo':
                    # For photos, get the largest version
                    if hasattr(media, 'mediaUrlHttps'):
                        media_url = media.mediaUrlHttps
                        # Convert to larger size if possible
                        if ':large' not in media_url and ':orig' not in media_url:
                            media_url = media_url.replace(':small', ':large').replace(':medium', ':large')
                            if ':large' not in media_url:
                                media_url += ':large'
                    elif hasattr(media, 'url'):
                        media_url = media.url
                
                elif media_type in ['video', 'animated_gif']:
                    # For videos, get the best quality variant
                    if hasattr(media, 'videoInfo') and media.videoInfo:
                        if hasattr(media.videoInfo, 'variants') and media.videoInfo.variants:
                            # Sort by bitrate to get best quality
                            best_variant = None
                            best_bitrate = 0
                            
                            for variant in media.videoInfo.variants:
                                if hasattr(variant, 'url') and variant.url:
                                    bitrate = getattr(variant, 'bitrate', 0) or 0
                                    if bitrate > best_bitrate:
                                        best_bitrate = bitrate
                                        best_variant = variant
                            
                            if best_variant:
                                media_url = best_variant.url
                    
                    # Get preview image
                    if hasattr(media, 'mediaUrlHttps'):
                        preview_url = media.mediaUrlHttps
                
                if media_url:
                    media_items.append(MediaItem(
                        type=media_type,
                        url=media_url,
                        preview_url=preview_url,
                        alt_text=getattr(media, 'altText', None),
                        width=getattr(media, 'originalInfo', {}).get('width') if hasattr(media, 'originalInfo') else None,
                        height=getattr(media, 'originalInfo', {}).get('height') if hasattr(media, 'originalInfo') else None
                    ))
        
        # Extract URLs
        urls = []
        if hasattr(tweet, 'urls') and tweet.urls:
            for url in tweet.urls:
                expanded_url = getattr(url, 'expandedUrl', None) or getattr(url, 'url', None)
                if expanded_url:
                    urls.append(expanded_url)
        
        # Extract hashtags
        hashtags = []
        if hasattr(tweet, 'hashtags') and tweet.hashtags:
            hashtags = [hashtag.text for hashtag in tweet.hashtags if hasattr(hashtag, 'text')]
        
        # Extract mentions
        mentions = []
        if hasattr(tweet, 'mentionedUsers') and tweet.mentionedUsers:
            mentions = [user.username for user in tweet.mentionedUsers if hasattr(user, 'username')]
        
        # Get user info
        user_info = tweet.user if hasattr(tweet, 'user') and tweet.user else None
        username = user_info.username if user_info and hasattr(user_info, 'username') else "unknown"
        user_id = str(user_info.id) if user_info and hasattr(user_info, 'id') else "unknown"
        display_name = user_info.displayname if user_info and hasattr(user_info, 'displayname') else username
        
        # Check tweet type
        is_reply = bool(getattr(tweet, 'inReplyToTweetId', None))
        is_retweet = bool(getattr(tweet, 'retweetedTweet', None))
        is_quote = bool(getattr(tweet, 'quotedTweet', None))
        
        return cls(
            id=str(tweet.id),
            text=tweet.rawContent or tweet.fullText or "",
            user=username,
            user_id=user_id,
            user_display_name=display_name,
            likes=getattr(tweet, 'likeCount', 0) or 0,
            retweets=getattr(tweet, 'retweetCount', 0) or 0,
            replies=getattr(tweet, 'replyCount', 0) or 0,
            quotes=getattr(tweet, 'quoteCount', 0) or 0,
            views=getattr(tweet, 'viewCount', 0) or 0,
            created_at=tweet.date.isoformat() if hasattr(tweet, 'date') and tweet.date else "",
            media=media_items,
            urls=urls,
            hashtags=hashtags,
            mentions=mentions,
            is_reply=is_reply,
            is_retweet=is_retweet,
            is_quote=is_quote,
            lang=getattr(tweet, 'lang', None),
            source=getattr(tweet, 'source', None)
        )
    
    def to_dict(self) -> Dict:
        """Convert to dictionary format for compatibility"""
        result = asdict(self)
        # Convert media list to simple URL list for backward compatibility
        result['media'] = [item.url for item in self.media]
        return result
    
    def has_media(self) -> bool:
        """Check if tweet has media"""
        return len(self.media) > 0
    
    def get_media_urls(self) -> List[str]:
        """Get all media URLs"""
        return [item.url for item in self.media]
    
    def get_image_urls(self) -> List[str]:
        """Get only image URLs"""
        return [item.url for item in self.media if item.type == 'photo']
    
    def get_video_urls(self) -> List[str]:
        """Get only video URLs"""
        return [item.url for item in self.media if item.type in ['video', 'animated_gif']]

class TwitterScraper:
    def __init__(self):
        self.api = API()
        self._accounts_added = False
    
    async def ensure_accounts(self):
        """Ensure we have at least one account configured"""
        if not self._accounts_added:
            try:
                # Try to get existing accounts
                accounts = await self.api.pool.accounts_info()
                if accounts:
                    self._accounts_added = True
                    logger.info(f"Using {len(accounts)} existing accounts")
                else:
                    logger.warning("No Twitter accounts configured. Some features may not work.")
            except Exception as e:
                logger.error(f"Failed to check accounts: {e}")
    
    async def setup_accounts(self, accounts: List[Dict[str, str]]) -> bool:
        """Setup Twitter accounts for scraping"""
        success_count = 0
        for acc in accounts:
            try:
                await self.api.pool.add_account(
                    acc['username'], 
                    acc['password'], 
                    acc['email'], 
                    acc['email_password']
                )
                success_count += 1
                logger.info(f"Added account: {acc['username']}")
            except Exception as e:
                logger.error(f"Failed to add {acc['username']}: {e}")
        
        self._accounts_added = success_count > 0
        return self._accounts_added
    
    async def search_tweets(self, query: str, limit: int = 20, include_media_only: bool = False) -> List[Tweet]:
        """Search tweets by query with enhanced filtering"""
        await self.ensure_accounts()
        tweets = []
        
        try:
            # Add media filter if requested
            search_query = query
            if include_media_only:
                search_query += " filter:media"
            
            async for raw_tweet in self.api.search(search_query, limit=limit):
                try:
                    tweet = Tweet.from_raw(raw_tweet)
                    
                    # Additional filtering
                    if include_media_only and not tweet.has_media():
                        continue
                    
                    tweets.append(tweet)
                    logger.debug(f"Processed tweet {tweet.id} from @{tweet.user}")
                    
                except Exception as e:
                    logger.error(f"Failed to process tweet: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            
        logger.info(f"Found {len(tweets)} tweets for query: {query}")
        return tweets
    
    async def user_tweets(self, username: str, limit: int = 20, include_replies: bool = False) -> List[Tweet]:
        """Get user tweets with media support"""
        await self.ensure_accounts()
        tweets = []
        
        try:
            async for raw_tweet in self.api.user_tweets(username, limit=limit):
                try:
                    tweet = Tweet.from_raw(raw_tweet)
                    
                    # Filter replies if not requested
                    if not include_replies and tweet.is_reply:
                        continue
                    
                    tweets.append(tweet)
                    logger.debug(f"Processed tweet {tweet.id} from @{tweet.user}")
                    
                except Exception as e:
                    logger.error(f"Failed to process tweet: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to get tweets for @{username}: {e}")
            
        logger.info(f"Found {len(tweets)} tweets for @{username}")
        return tweets
    
    async def user_media_tweets(self, username: str, limit: int = 20) -> List[Tweet]:
        """Get only tweets with media from a user"""
        tweets = await self.user_tweets(username, limit * 2)  # Get more to filter
        media_tweets = [tweet for tweet in tweets if tweet.has_media()]
        return media_tweets[:limit]
    
    async def get_tweet(self, tweet_id: str) -> Optional[Tweet]:
        """Get a specific tweet by ID"""
        await self.ensure_accounts()
        
        try:
            raw_tweet = await self.api.tweet_details(int(tweet_id))
            if raw_tweet:
                return Tweet.from_raw(raw_tweet)
        except Exception as e:
            logger.error(f"Failed to get tweet {tweet_id}: {e}")
        
        return None
    
    async def user_info(self, username: str) -> Optional[Dict]:
        """Get detailed user information"""
        await self.ensure_accounts()
        
        try:
            user = await self.api.user_by_login(username)
            if user:
                return {
                    'id': str(user.id),
                    'username': user.username,
                    'name': user.displayname,
                    'description': getattr(user, 'description', ''),
                    'followers': getattr(user, 'followersCount', 0),
                    'following': getattr(user, 'friendsCount', 0),
                    'tweets_count': getattr(user, 'statusesCount', 0),
                    'verified': getattr(user, 'verified', False),
                    'created_at': user.created.isoformat() if hasattr(user, 'created') and user.created else None,
                    'location': getattr(user, 'location', ''),
                    'url': getattr(user, 'url', ''),
                    'profile_image': getattr(user, 'profileImageUrlHttps', ''),
                    'banner_image': getattr(user, 'profileBannerUrl', '')
                }
        except Exception as e:
            logger.error(f"Failed to get user info for @{username}: {e}")
        
        return None

# Enhanced convenience functions
async def fetch_tweets(mode: str, target: str, limit: int = 20, **kwargs) -> List[Dict]:
    """
    Enhanced fetch function with multiple modes
    
    Args:
        mode: 'search', 'user', 'media', 'replies'
        target: search query or username
        limit: number of tweets to fetch
        **kwargs: additional parameters
    """
    scraper = TwitterScraper()
    tweets = []
    
    try:
        if mode == "search":
            tweets = await scraper.search_tweets(
                target, 
                limit, 
                include_media_only=kwargs.get('media_only', False)
            )
        
        elif mode == "user":
            tweets = await scraper.user_tweets(
                target, 
                limit, 
                include_replies=kwargs.get('include_replies', False)
            )
        
        elif mode == "media":
            tweets = await scraper.user_media_tweets(target, limit)
        
        elif mode == "replies":
            tweets = await scraper.user_tweets(target, limit, include_replies=True)
            tweets = [t for t in tweets if t.is_reply]
        
        else:
            logger.error(f"Invalid mode: {mode}")
            return []
        
        # Convert to dict format for compatibility
        return [tweet.to_dict() for tweet in tweets]
        
    except Exception as e:
        logger.error(f"Failed to fetch tweets: {e}")
        return []

async def search_tweets(query: str, limit: int = 20, media_only: bool = False) -> List[Dict]:
    """Search tweets and return as dicts"""
    return await fetch_tweets("search", query, limit, media_only=media_only)

async def get_user_tweets(username: str, limit: int = 20, include_replies: bool = False) -> List[Dict]:
    """Get user tweets and return as dicts"""
    return await fetch_tweets("user", username, limit, include_replies=include_replies)

async def get_media_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Get only tweets with media from a user"""
    return await fetch_tweets("media", username, limit)

async def get_user_info(username: str) -> Optional[Dict]:
    """Get user info"""
    scraper = TwitterScraper()
    return await scraper.user_info(username)

async def get_tweet_by_id(tweet_id: str) -> Optional[Dict]:
    """Get a specific tweet by ID"""
    scraper = TwitterScraper()
    tweet = await scraper.get_tweet(tweet_id)
    return tweet.to_dict() if tweet else None

async def setup_accounts(accounts: List[Dict[str, str]]) -> bool:
    """Setup Twitter accounts"""
    scraper = TwitterScraper()
    return await scraper.setup_accounts(accounts)

# Usage examples and testing
if __name__ == "__main__":
    async def test():
        print("Testing enhanced Twitter scraper...")
        
        # Test 1: Search for tweets with media
        print("\n1. Searching for AI tweets with media...")
        media_tweets = await search_tweets("#AI", limit=3, media_only=True)
        print(f"Found {len(media_tweets)} tweets with media")
        
        for tweet in media_tweets:
            print(f"  - @{tweet['user']}: {tweet['text'][:50]}...")
            if tweet['media']:
                print(f"    Media URLs: {tweet['media']}")
        
        # Test 2: Get user tweets
        print("\n2. Getting user tweets...")
        user_tweets = await get_user_tweets("elonmusk", limit=3)
        print(f"Found {len(user_tweets)} user tweets")
        
        for tweet in user_tweets:
            print(f"  - {tweet['created_at']}: {tweet['text'][:50]}...")
            if tweet['media']:
                print(f"    Has {len(tweet['media'])} media items")
        
        # Test 3: Get media-only tweets from user
        print("\n3. Getting media tweets from user...")
        media_user_tweets = await get_media_tweets("elonmusk", limit=2)
        print(f"Found {len(media_user_tweets)} media tweets")
        
        for tweet in media_user_tweets:
            print(f"  - Media URLs: {tweet['media']}")
        
        # Test 4: Get user info
        print("\n4. Getting user info...")
        user_info = await get_user_info("elonmusk")
        if user_info:
            print(f"  User: {user_info['name']} (@{user_info['username']})")
            print(f"  Followers: {user_info['followers']:,}")
    
    asyncio.run(test())
