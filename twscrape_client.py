import asyncio
import json
import os
import time
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager as CM
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from dateutil.parser import parse
import hashlib
from datetime import datetime
from config import logger
from dotenv import load_dotenv

load_dotenv()

class TwitterScraper:
    def __init__(self):
        self.username = os.getenv("TWITTER_USERNAME")
        self.password = os.getenv("TWITTER_PASSWORD")
        self.driver = None
        self.logged_in = False
    
    def setup_driver(self):
        """Initialize Chrome WebDriver"""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        service = Service(executable_path=CM().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        return self.driver
    
    async def login(self):
        """Login to Twitter"""
        if self.logged_in:
            return True
            
        try:
            self.driver.get("https://x.com/i/flow/login")
            
            # Username input
            username_input = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
            )
            username_input.send_keys(self.username)
            username_input.send_keys(Keys.RETURN)
            
            # Password input
            password_input = WebDriverWait(self.driver, 30).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
            )
            password_input.send_keys(self.password)
            password_input.send_keys(Keys.RETURN)
            
            # Wait for login to complete
            await asyncio.sleep(5)
            self.logged_in = True
            logger.info("Successfully logged in to Twitter")
            return True
            
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def extract_tweet_data(self, tweet_element) -> Optional[Dict]:
        """Extract data from a tweet element"""
        try:
            # Tweet text
            try:
                tweet_text = tweet_element.find_element(By.CSS_SELECTOR, 'div[lang]').text
            except NoSuchElementException:
                tweet_text = ""
            
            # Timestamp
            try:
                timestamp_element = tweet_element.find_element(By.TAG_NAME, "time")
                timestamp = timestamp_element.get_attribute("datetime")
                created_at = parse(timestamp).isoformat()
            except:
                created_at = datetime.now().isoformat()
            
            # Tweet URL and ID
            try:
                tweet_link = tweet_element.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
                tweet_url = tweet_link.get_attribute("href")
                tweet_id = tweet_url.split('/status/')[-1].split('?')[0]
            except:
                tweet_id = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
                tweet_url = f"https://twitter.com/user/status/{tweet_id}"
            
            # Username
            try:
                username_element = tweet_element.find_element(By.CSS_SELECTOR, 'div[data-testid="User-Name"] span')
                author = username_element.text.replace('@', '')
            except:
                author = "unknown"
            
            # Images
            try:
                images = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
                tweet_images = [img.get_attribute("src") for img in images]
            except:
                tweet_images = []
            
            return {
                "id": tweet_id,
                "text": tweet_text,
                "url": tweet_url,
                "created_at": created_at,
                "author": author,
                "media": tweet_images
            }
            
        except Exception as e:
            logger.error(f"Failed to extract tweet data: {e}")
            return None
    
    async def scrape_user_tweets(self, username: str, limit: int = 10) -> List[Dict]:
        """Scrape tweets from a specific user"""
        try:
            profile_url = f"https://x.com/{username}"
            self.driver.get(profile_url)
            await asyncio.sleep(3)
            
            tweets_data = []
            scroll_attempts = 0
            max_scrolls = limit // 3  # Approximate tweets per scroll
            
            while len(tweets_data) < limit and scroll_attempts < max_scrolls * 2:
                # Find tweet elements
                tweets = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
                
                for tweet in tweets:
                    if len(tweets_data) >= limit:
                        break
                        
                    tweet_data = self.extract_tweet_data(tweet)
                    if tweet_data and not any(t['id'] == tweet_data['id'] for t in tweets_data):
                        tweets_data.append(tweet_data)
                
                # Scroll for more tweets
                self.driver.execute_script("window.scrollBy(0, 1000);")
                await asyncio.sleep(2)
                scroll_attempts += 1
            
            logger.info(f"Scraped {len(tweets_data)} tweets from @{username}")
            return tweets_data[:limit]
            
        except Exception as e:
            logger.error(f"Failed to scrape user tweets: {e}")
            return []
    
    async def search_tweets(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for tweets by query"""
        try:
            search_url = f"https://x.com/search?q={query.replace(' ', '%20')}&src=typed_query&f=live"
            self.driver.get(search_url)
            await asyncio.sleep(3)
            
            tweets_data = []
            scroll_attempts = 0
            max_scrolls = limit // 3
            
            while len(tweets_data) < limit and scroll_attempts < max_scrolls * 2:
                tweets = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
                
                for tweet in tweets:
                    if len(tweets_data) >= limit:
                        break
                        
                    tweet_data = self.extract_tweet_data(tweet)
                    if tweet_data and not any(t['id'] == tweet_data['id'] for t in tweets_data):
                        tweets_data.append(tweet_data)
                
                self.driver.execute_script("window.scrollBy(0, 1000);")
                await asyncio.sleep(2)
                scroll_attempts += 1
            
            logger.info(f"Found {len(tweets_data)} tweets for query: {query}")
            return tweets_data[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search tweets: {e}")
            return []
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

# Global scraper instance
_scraper = None

async def get_scraper():
    """Get or create scraper instance"""
    global _scraper
    if _scraper is None:
        _scraper = TwitterScraper()
        _scraper.setup_driver()
        await _scraper.login()
    return _scraper

async def fetch_tweets(mode: str, query_or_username: str, limit: int = 10) -> List[Dict]:
    """
    Main function to fetch tweets - compatible with main.py expectations
    
    Args:
        mode: "user" or "search"
        query_or_username: Username (without @) or search query
        limit: Number of tweets to fetch
    
    Returns:
        List of tweet dictionaries
    """
    try:
        scraper = await get_scraper()
        
        if mode == "user":
            return await scraper.scrape_user_tweets(query_or_username, limit)
        elif mode == "search":
            return await scraper.search_tweets(query_or_username, limit)
        else:
            logger.error(f"Invalid mode: {mode}. Use 'user' or 'search'")
            return []
            
    except Exception as e:
        logger.error(f"Failed to fetch tweets: {e}")
        return []

# Cleanup function
import atexit

def cleanup_scraper():
    global _scraper
    if _scraper:
        _scraper.close()

atexit.register(cleanup_scraper)

if __name__ == "__main__":
    # Test the scraper
    async def test():
        tweets = await fetch_tweets("search", "artificial intelligence", 5)
        print(f"Fetched {len(tweets)} tweets")
        for tweet in tweets[:2]:
            print(f"- {tweet['text'][:100]}...")
    
    asyncio.run(test())
