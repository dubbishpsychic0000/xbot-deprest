import asyncio
import os
import hashlib
import json
import pickle
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import random
import time

# Import twscrape - latest version 0.17.0
from twscrape import API, gather, Tweet, User
from twscrape.logger import set_log_level

load_dotenv()

# Fetch credentials from .env
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD") 
TWITTER_EMAIL = os.getenv("TWITTER_EMAIL", "")
TWITTER_EMAIL_PASSWORD = os.getenv("TWITTER_EMAIL_PASSWORD", "")
TWITTER_COOKIES = os.getenv("TWITTER_COOKIES", "")

# Global API instance
api = None

def setup_driver() -> bool:
    """Initialize twscrape API instance with anti-detection options."""
    global api
    try:
        print("Initializing twscrape API...")
        
        # Initialize API with accounts database
        api = API("accounts.db")
        
        # Set debug level for troubleshooting
        set_log_level("INFO")
        
        print("twscrape API initialized successfully")
        return True
        
    except Exception as e:
        print(f"Failed to initialize twscrape API: {e}")
        return False

def human_like_delay():
    """Add human-like delays to avoid detection."""
    time.sleep(random.uniform(1, 3))

async def login() -> bool:
    """Login function using twscrape account management."""
    global api
    
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        print("Twitter credentials not found in environment variables")
        return False
        
    try:
        print("Setting up Twitter account...")
        
        # Check if account already exists
        accounts = await api.pool.accounts_info()
        account_exists = any(acc.username == TWITTER_USERNAME for acc in accounts)
        
        if not account_exists:
            print(f"Adding new account: {TWITTER_USERNAME}")
            
            # Add account with cookies if available (more stable)
            if TWITTER_COOKIES:
                await api.pool.add_account(
                    username=TWITTER_USERNAME,
                    password=TWITTER_PASSWORD,
                    email=TWITTER_EMAIL,
                    email_password=TWITTER_EMAIL_PASSWORD,
                    cookies=TWITTER_COOKIES
                )
                print("Account added with cookies")
            else:
                # Add account with login/password (requires email verification)
                await api.pool.add_account(
                    username=TWITTER_USERNAME,
                    password=TWITTER_PASSWORD,
                    email=TWITTER_EMAIL,
                    email_password=TWITTER_EMAIL_PASSWORD
                )
                print("Account added with login credentials")
        else:
            print(f"Account {TWITTER_USERNAME} already exists")
        
        # Login to all accounts
        print("Logging in to Twitter accounts...")
        await api.pool.login_all()
        
        # Check if login was successful
        logged_in_accounts = [acc for acc in await api.pool.accounts_info() if acc.logged_in]
        if not logged_in_accounts:
            print("No accounts successfully logged in")
            return False
            
        print(f"Successfully logged in {len(logged_in_accounts)} account(s)")
        return True
                
    except Exception as e:
        print(f"Login failed with error: {e}")
        return False

def extract_tweet_data_original_format(tweet: Tweet) -> Optional[Tuple[str, str, str, str]]:
    """Extract tweet data in original format - matching working script exactly."""
    try:
        # Extract tweet text
        tweet_text = tweet.rawContent or ""
        
        # Extract timestamp and format as date
        tweet_date = ""
        if tweet.date:
            tweet_date = tweet.date.strftime("%Y-%m-%d")
        
        # Extract external link - use tweet URL
        external_link = tweet.url or ""
        
        # Extract images
        tweet_images = []
        if hasattr(tweet, 'media') and tweet.media:
            for media in tweet.media:
                if hasattr(media, 'mediaUrl') and media.mediaUrl:
                    tweet_images.append(media.mediaUrl)
                elif hasattr(media, 'url') and media.url:
                    tweet_images.append(media.url)

        images_links = ', '.join(tweet_images) if tweet_images else "No Images"

        return (tweet_text, tweet_date, external_link, images_links)

    except Exception as e:
        print(f"Failed to extract tweet data: {e}")
        return None

def extract_tweet_data_bot_format(tweet: Tweet) -> Optional[Dict]:
    """Extract tweet data and return in bot-compatible format."""
    try:
        # Get original format data first
        original_data = extract_tweet_data_original_format(tweet)
        if not original_data:
            return None
        
        tweet_text, tweet_date, external_link, images_links = original_data

        # Convert timestamp to ISO format
        try:
            if tweet.date:
                created_at = tweet.date.isoformat()
            else:
                created_at = datetime.now().isoformat()
        except Exception:
            created_at = datetime.now().isoformat()

        # Extract tweet URL and ID
        tweet_url = tweet.url or external_link
        tweet_id = str(tweet.id) if tweet.id else ""
        
        # Fallback ID generation
        if not tweet_id:
            fallback_hash = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            if not tweet_url:
                tweet_url = f"https://x.com/status/{fallback_hash}"

        # Extract author
        author = "unknown"
        if hasattr(tweet, 'user') and tweet.user:
            if hasattr(tweet.user, 'username') and tweet.user.username:
                author = tweet.user.username
            elif hasattr(tweet.user, 'displayname') and tweet.user.displayname:
                author = tweet.user.displayname

        # Convert images to list
        media = []
        if images_links and images_links != "No Images":
            media = [img.strip() for img in images_links.split(',') if img.strip()]

        # Skip if no meaningful content
        if not tweet_text.strip() and not media:
            return None

        return {
            "id": tweet_id,
            "text": tweet_text,
            "url": tweet_url,
            "created_at": created_at,
            "author": author,
            "media": media
        }

    except Exception as e:
        print(f"Failed to extract tweet data for bot format: {e}")
        return None

async def fetch_tweets(source_type: str, source: str, limit: int = 20) -> List[Dict]:
    """
    Main function to fetch tweets - compatible with your bot's interface.
    
    Args:
        source_type: "timeline", "user", or "search"
        source: username (for user) or query (for search) or ignored (for timeline)
        limit: maximum number of tweets to fetch
    
    Returns:
        List of tweet dictionaries with keys: id, text, url, created_at, author, media
    """
    if source_type == "timeline":
        return await async_scrape_timeline_tweets(limit)
    elif source_type == "user":
        return await async_scrape_user_tweets(source, limit)
    elif source_type == "search":
        return await async_scrape_search_tweets(source, limit)
    else:
        print(f"Unsupported source_type: {source_type}")
        return []

async def async_scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """Async version of timeline scraping using twscrape."""
    global api
    
    try:
        print(f"Starting to scrape timeline tweets (limit: {limit})...")
        
        # Get user ID for timeline (use first available account)
        accounts = await api.pool.accounts_info()
        if not accounts or not any(acc.logged_in for acc in accounts):
            print("No logged in accounts available")
            return []
        
        # Get current user's timeline - this is tricky with twscrape
        # We'll use search with a broad query as fallback
        print("Fetching timeline tweets...")
        tweets_data = []
        
        try:
            # Try to get user's own tweets if possible
            logged_in_account = next(acc for acc in accounts if acc.logged_in)
            user_info = await api.user_by_login(logged_in_account.username)
            if user_info:
                tweets = await gather(api.user_tweets(user_info.id, limit=limit))
                
                for tweet in tweets:
                    if len(tweets_data) >= limit:
                        break
                    
                    bot_format_data = extract_tweet_data_bot_format(tweet)
                    if bot_format_data and bot_format_data.get('text', '').strip():
                        tweets_data.append(bot_format_data)
                        
                        # Print progress
                        original_data = extract_tweet_data_original_format(tweet)
                        if original_data:
                            tweet_text, tweet_date, external_link, images_links = original_data
                            print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")
                            
        except Exception as e:
            print(f"Error fetching timeline: {e}")
            # Fallback to search with popular terms
            return await async_scrape_search_tweets("lang:en", limit)

        # Save to Excel file for compatibility
        if tweets_data:
            try:
                original_format_data = []
                for tweet_data in tweets_data:
                    media_str = ', '.join(tweet_data.get('media', [])) if tweet_data.get('media') else "No Images"
                    original_format_data.append([
                        tweet_data.get('text', ''),
                        tweet_data.get('created_at', '').split('T')[0],
                        tweet_data.get('url', ''),
                        media_str
                    ])
                
                df = pd.DataFrame(original_format_data, columns=["Tweet", "Date", "Link", "Images"])
                df.to_excel("tweets2.xlsx", index=False)
                print(f"Total tweets collected: {len(original_format_data)}")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print("Script execution completed.")
        return tweets_data

    except Exception as e:
        print(f"Error in async_scrape_timeline_tweets: {e}")
        return []

async def async_scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Async version of user tweet scraping using twscrape."""
    global api
    
    # Clean username
    username = username.replace('@', '').strip()
    if not username:
        print("Invalid username provided")
        return []
    
    try:
        print(f"Starting to scrape user tweets for @{username} (limit: {limit})...")
        
        # Get user info
        user_info = await api.user_by_login(username)
        if not user_info:
            print(f"User @{username} not found")
            return []
        
        print(f"Found user: {user_info.displayname} (@{user_info.username})")
        
        # Get user tweets
        tweets = await gather(api.user_tweets(user_info.id, limit=limit))
        
        tweets_data = []
        for tweet in tweets:
            if len(tweets_data) >= limit:
                break
                
            bot_format_data = extract_tweet_data_bot_format(tweet)
            if bot_format_data and bot_format_data.get('text', '').strip():
                tweets_data.append(bot_format_data)
                
                # Print progress
                original_data = extract_tweet_data_original_format(tweet)
                if original_data:
                    tweet_text, tweet_date, external_link, images_links = original_data
                    print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")

        # Save to Excel file
        if tweets_data:
            try:
                original_format_data = []
                for tweet_data in tweets_data:
                    media_str = ', '.join(tweet_data.get('media', [])) if tweet_data.get('media') else "No Images"
                    original_format_data.append([
                        tweet_data.get('text', ''),
                        tweet_data.get('created_at', '').split('T')[0],
                        tweet_data.get('url', ''),
                        media_str
                    ])
                
                df = pd.DataFrame(original_format_data, columns=["Tweet", "Date", "Link", "Images"])
                filename = f"{username}_tweets.xlsx"
                df.to_excel(filename, index=False)
                print(f"Total tweets collected: {len(original_format_data)}")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print("Script execution completed.")
        return tweets_data

    except Exception as e:
        print(f"Error in async_scrape_user_tweets: {e}")
        return []

async def async_scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Async version of search tweet scraping using twscrape."""
    global api
    
    if not query.strip():
        print("Invalid search query provided")
        return []
    
    try:
        print(f"Starting to scrape search tweets for query: '{query}' (limit: {limit})...")
        
        # Search for tweets
        tweets = await gather(api.search(query, limit=limit))
        
        tweets_data = []
        for tweet in tweets:
            if len(tweets_data) >= limit:
                break
                
            bot_format_data = extract_tweet_data_bot_format(tweet)
            if bot_format_data and bot_format_data.get('text', '').strip():
                tweets_data.append(bot_format_data)
                
                # Print progress
                original_data = extract_tweet_data_original_format(tweet)
                if original_data:
                    tweet_text, tweet_date, external_link, images_links = original_data
                    print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")

        # Save to Excel file
        if tweets_data:
            try:
                original_format_data = []
                for tweet_data in tweets_data:
                    media_str = ', '.join(tweet_data.get('media', [])) if tweet_data.get('media') else "No Images"
                    original_format_data.append([
                        tweet_data.get('text', ''),
                        tweet_data.get('created_at', '').split('T')[0],
                        tweet_data.get('url', ''),
                        media_str
                    ])
                
                df = pd.DataFrame(original_format_data, columns=["Tweet", "Date", "Link", "Images"])
                safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"search_{safe_query[:30]}_tweets.xlsx"
                df.to_excel(filename, index=False)
                print(f"Total tweets collected: {len(original_format_data)}")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print("Script execution completed.")
        return tweets_data

    except Exception as e:
        print(f"Error in async_scrape_search_tweets: {e}")
        return []

# Synchronous wrapper functions to maintain compatibility
def scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """Scrape timeline tweets - maintaining exact function signature."""
    try:
        # Setup API
        if not setup_driver():
            print("Failed to setup twscrape API")
            return []
        
        # Run async function
        return asyncio.run(async_timeline_wrapper(limit))
    except Exception as e:
        print(f"Error in scrape_timeline_tweets: {e}")
        return []

def scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Scrape user tweets - maintaining exact function signature."""
    try:
        # Setup API
        if not setup_driver():
            print("Failed to setup twscrape API")
            return []
        
        # Run async function
        return asyncio.run(async_user_wrapper(username, limit))
    except Exception as e:
        print(f"Error in scrape_user_tweets: {e}")
        return []

def scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Scrape search tweets - maintaining exact function signature."""
    try:
        # Setup API
        if not setup_driver():
            print("Failed to setup twscrape API")
            return []
        
        # Run async function
        return asyncio.run(async_search_wrapper(query, limit))
    except Exception as e:
        print(f"Error in scrape_search_tweets: {e}")
        return []

async def async_timeline_wrapper(limit: int) -> List[Dict]:
    """Async wrapper for timeline scraping."""
    if not await login():
        print("Login failed!")
        return []
    return await async_scrape_timeline_tweets(limit)

async def async_user_wrapper(username: str, limit: int) -> List[Dict]:
    """Async wrapper for user scraping."""
    if not await login():
        print("Login failed!")
        return []
    return await async_scrape_user_tweets(username, limit)

async def async_search_wrapper(query: str, limit: int) -> List[Dict]:
    """Async wrapper for search scraping."""
    if not await login():
        print("Login failed!")
        return []
    return await async_scrape_search_tweets(query, limit)

# Utility functions maintained for compatibility
def check_rate_limit() -> bool:
    """Check if we've hit Twitter's rate limit - handled automatically by twscrape."""
    return False

def handle_popup_dialogs():
    """Handle various popup dialogs - not needed with twscrape."""
    pass

def wait_for_stable_page(timeout: int = 30):
    """Wait for page to become stable - not needed with twscrape."""
    return True

# Additional convenience functions
async def get_user_info(username: str) -> Optional[Dict]:
    """Get user information."""
    global api
    try:
        if not await login():
            return None
        
        username = username.replace('@', '').strip()
        user_info = await api.user_by_login(username)
        
        if user_info:
            return {
                "id": str(user_info.id),
                "username": user_info.username,
                "displayname": user_info.displayname,
                "description": user_info.rawDescription or "",
                "followers_count": user_info.followersCount or 0,
                "following_count": user_info.followingCount or 0,
                "tweet_count": user_info.tweetsCount or 0,
                "verified": user_info.verified or False,
                "profile_image": user_info.profileImageUrl or "",
                "banner_image": user_info.profileBannerUrl or "",
                "created_at": user_info.created.isoformat() if user_info.created else "",
                "location": user_info.location or "",
                "url": user_info.linkUrl or ""
            }
        return None
    except Exception as e:
        print(f"Error getting user info: {e}")
        return None

def get_user_info_sync(username: str) -> Optional[Dict]:
    """Synchronous version of get_user_info."""
    try:
        if not setup_driver():
            return None
        return asyncio.run(get_user_info(username))
    except Exception as e:
        print(f"Error in get_user_info_sync: {e}")
        return None

# Main execution example
if __name__ == "__main__":
    # Example usage
    print("Testing Twitter scraper with twscrape...")
    
    # Test user tweets
    user_tweets = scrape_user_tweets("elonmusk", 5)
    print(f"Retrieved {len(user_tweets)} user tweets")
    
    # Test search
    search_tweets = scrape_search_tweets("python programming", 5)
    print(f"Retrieved {len(search_tweets)} search tweets")
    
    # Test user info
    user_info = get_user_info_sync("elonmusk")
    if user_info:
        print(f"User info: {user_info['displayname']} (@{user_info['username']})")
