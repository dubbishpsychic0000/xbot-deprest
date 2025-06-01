import time
import os
import hashlib
import json
import pickle
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
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Fetch credentials from .env
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")

# Debug mode flag
DEBUG_MODE = True

def debug_print(message):
    """Print debug messages if debug mode is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def setup_driver(headless=True) -> webdriver.Chrome:
    """Initialize and return a Chrome WebDriver."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    if headless:
        options.add_argument("--headless")
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    service = Service(executable_path=CM().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Execute script to hide webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def login_with_debug(driver: webdriver.Chrome) -> bool:
    """Log in to Twitter with enhanced debugging."""
    try:
        debug_print("Starting login process...")
        driver.get("https://x.com/i/flow/login")
        
        # Take screenshot for debugging
        if DEBUG_MODE:
            driver.save_screenshot("login_page.png")
            debug_print("Saved login page screenshot")

        # Wait for the username input with multiple selectors
        username_selectors = [
            'input[autocomplete="username"]',
            'input[name="text"]',
            'input[placeholder*="username"]',
            'input[placeholder*="email"]'
        ]
        
        username_inp = None
        for selector in username_selectors:
            try:
                debug_print(f"Trying username selector: {selector}")
                username_inp = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                debug_print(f"Found username input with selector: {selector}")
                break
            except TimeoutException:
                debug_print(f"Selector {selector} failed")
                continue
        
        if not username_inp:
            debug_print("No username input found!")
            return False
            
        username_inp.clear()
        username_inp.send_keys(TWITTER_USERNAME)
        debug_print(f"Entered username: {TWITTER_USERNAME}")
        username_inp.send_keys(Keys.RETURN)
        
        time.sleep(3)

        # Wait for the password input with multiple selectors
        password_selectors = [
            'input[name="password"]',
            'input[type="password"]',
            'input[placeholder*="password"]'
        ]
        
        password_inp = None
        for selector in password_selectors:
            try:
                debug_print(f"Trying password selector: {selector}")
                password_inp = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                )
                debug_print(f"Found password input with selector: {selector}")
                break
            except TimeoutException:
                debug_print(f"Password selector {selector} failed")
                continue
        
        if not password_inp:
            debug_print("No password input found!")
            if DEBUG_MODE:
                driver.save_screenshot("password_page.png")
                debug_print("Saved password page screenshot")
            return False
            
        password_inp.clear()
        password_inp.send_keys(TWITTER_PASSWORD)
        debug_print("Entered password")
        password_inp.send_keys(Keys.RETURN)

        # Wait for login to complete - look for home page elements
        debug_print("Waiting for login to complete...")
        time.sleep(10)
        
        # Check if we're successfully logged in by looking for home timeline elements
        try:
            WebDriverWait(driver, 30).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[aria-label="Home timeline"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'main[role="main"]'))
                )
            )
            debug_print("Login successful - found home page elements")
            
            if DEBUG_MODE:
                driver.save_screenshot("after_login.png")
                debug_print("Saved after-login screenshot")
            
            return True
            
        except TimeoutException:
            debug_print("Login verification failed - timeout waiting for home page")
            if DEBUG_MODE:
                driver.save_screenshot("login_failed.png")
                debug_print("Saved login failed screenshot")
            return False

    except Exception as e:
        debug_print(f"Login failed with exception: {e}")
        if DEBUG_MODE:
            driver.save_screenshot("login_exception.png")
        return False

def find_tweets_with_debug(driver) -> List:
    """Find tweet elements with enhanced debugging"""
    tweet_selectors = [
        'article[data-testid="tweet"]',
        'div[data-testid="tweet"]',
        'article[role="article"]',
        'div[data-testid="cellInnerDiv"]'
    ]
    
    tweets = []
    for selector in tweet_selectors:
        try:
            debug_print(f"Trying tweet selector: {selector}")
            found_tweets = driver.find_elements(By.CSS_SELECTOR, selector)
            debug_print(f"Found {len(found_tweets)} elements with selector: {selector}")
            
            if found_tweets:
                tweets = found_tweets
                debug_print(f"Using selector: {selector} with {len(tweets)} tweets")
                break
                
        except Exception as e:
            debug_print(f"Error with selector {selector}: {e}")
    
    return tweets

def extract_tweet_data_with_debug(tweet_element) -> Optional[Dict]:
    """Extract tweet data with enhanced debugging"""
    try:
        debug_print("Extracting tweet data...")
        
        # Tweet text - try multiple selectors
        text_selectors = [
            'div[lang]',
            'div[data-testid="tweetText"]',
            'span[lang]',
            'div[dir="auto"]'
        ]
        
        tweet_text = ""
        for selector in text_selectors:
            try:
                text_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                tweet_text = text_elem.text.strip()
                if tweet_text:
                    debug_print(f"Found tweet text with selector {selector}: {tweet_text[:50]}...")
                    break
            except NoSuchElementException:
                continue
        
        if not tweet_text:
            debug_print("No tweet text found")
            return None

        # Timestamp - try multiple selectors
        timestamp_selectors = [
            'time',
            'a[href*="/status/"] time',
            '[datetime]'
        ]
        
        tweet_date = ""
        for selector in timestamp_selectors:
            try:
                time_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                timestamp = time_elem.get_attribute("datetime")
                if timestamp:
                    tweet_date = parse(timestamp).isoformat().split("T")[0]
                    debug_print(f"Found timestamp: {tweet_date}")
                    break
            except Exception:
                continue
        
        if not tweet_date:
            tweet_date = datetime.now().strftime("%Y-%m-%d")
            debug_print(f"Using current date: {tweet_date}")

        # Tweet URL and ID
        try:
            link_elem = tweet_element.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
            tweet_url = link_elem.get_attribute("href")
            tweet_id = tweet_url.split("/status/")[-1].split("?")[0]
            debug_print(f"Found tweet URL: {tweet_url}")
        except Exception:
            # Fallback: hash text+date for unique ID
            fallback_hash = hashlib.md5(f"{tweet_text}_{tweet_date}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            tweet_url = f"https://x.com/status/{fallback_hash}"
            debug_print(f"Using fallback URL: {tweet_url}")

        # Author username
        author_selectors = [
            'div[data-testid="User-Name"] span',
            'div[data-testid="User-Name"] a span',
            '[data-testid="User-Name"] span',
            'a[href^="/"][role="link"] span'
        ]
        
        author = "unknown"
        for selector in author_selectors:
            try:
                usr_elems = tweet_element.find_elements(By.CSS_SELECTOR, selector)
                for elem in usr_elems:
                    text = elem.text.strip()
                    if text.startswith("@"):
                        author = text.replace("@", "")
                        debug_print(f"Found author: @{author}")
                        break
                if author != "unknown":
                    break
            except:
                continue

        # Images
        media = []
        try:
            images = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
            media = [img.get_attribute("src") for img in images if img.get_attribute("src")]
            debug_print(f"Found {len(media)} images")
        except Exception as e:
            debug_print(f"Error finding images: {e}")

        tweet_data = {
            "id": tweet_id,
            "text": tweet_text,
            "url": tweet_url,
            "created_at": f"{tweet_date}T00:00:00",
            "author": author,
            "media": media
        }
        
        debug_print(f"Successfully extracted tweet: {tweet_text[:50]}...")
        return tweet_data

    except Exception as e:
        debug_print(f"Failed to extract tweet data: {e}")
        return None

def scrape_timeline_tweets_debug(limit: int = 20, headless: bool = False) -> List[Dict]:
    """
    Enhanced timeline scraping with debugging
    """
    debug_print("Starting timeline scraping with debug mode...")
    
    driver = setup_driver(headless=headless)
    
    try:
        # 1) Log in first
        if not login_with_debug(driver):
            debug_print("Login failed!")
            driver.quit()
            return []

        # 2) Navigate to home timeline
        debug_print("Navigating to home timeline...")
        driver.get("https://x.com/home")
        time.sleep(10)  # Wait for timeline to load
        
        if DEBUG_MODE:
            driver.save_screenshot("home_timeline.png")
            debug_print("Saved home timeline screenshot")

        # Check if we can find the timeline
        try:
            WebDriverWait(driver, 30).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="primaryColumn"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'main[role="main"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
                )
            )
            debug_print("Timeline loaded successfully")
        except TimeoutException:
            debug_print("Timeline failed to load!")
            return []

        tweets_data = []
        tweets_collected = set()
        scroll_count = 0
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        debug_print(f"Initial page height: {last_height}")

        while len(tweets_data) < limit and scroll_count < 20:  # Limit scrolls to prevent infinite loops
            debug_print(f"Scroll iteration {scroll_count + 1}")
            
            # Find tweets
            tweets = find_tweets_with_debug(driver)
            debug_print(f"Found {len(tweets)} tweet elements")

            if not tweets:
                debug_print("No tweets found, scrolling...")
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(5)
                scroll_count += 1
                continue

            new_tweets_count = 0
            for i, tweet in enumerate(tweets):
                if len(tweets_data) >= limit:
                    break
                    
                debug_print(f"Processing tweet {i + 1}/{len(tweets)}")
                
                # Extract tweet data
                tweet_data = extract_tweet_data_with_debug(tweet)
                if not tweet_data:
                    continue
                
                # Check for duplicates
                tweet_key = (tweet_data['text'], tweet_data['created_at'])
                if tweet_key not in tweets_collected:
                    tweets_collected.add(tweet_key)
                    tweets_data.append(tweet_data)
                    new_tweets_count += 1
                    
                    debug_print(f"Added tweet {len(tweets_data)}: {tweet_data['text'][:50]}...")

            debug_print(f"Added {new_tweets_count} new tweets this iteration")

            if new_tweets_count == 0:
                debug_print("No new tweets found, scrolling...")
            
            # Scroll down
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(5)
            
            # Check if we've reached the bottom
            new_height = driver.execute_script("return document.body.scrollHeight")
            debug_print(f"New height: {new_height}, Last height: {last_height}")
            
            if new_height == last_height:
                debug_print("Reached bottom of page or no new content loaded")
                scroll_count += 1
                if scroll_count >= 3:  # If we're stuck for 3 iterations, break
                    debug_print("Breaking due to no new content")
                    break
            else:
                last_height = new_height
                scroll_count = 0  # Reset scroll count when we get new content

        debug_print(f"Scraping completed. Total tweets collected: {len(tweets_data)}")
        
        # Final screenshot
        if DEBUG_MODE:
            driver.save_screenshot("scraping_complete.png")
        
        driver.quit()
        return tweets_data

    except Exception as e:
        debug_print(f"Error in scrape_timeline_tweets_debug: {e}")
        if DEBUG_MODE:
            driver.save_screenshot("scraping_error.png")
        driver.quit()
        return []

def test_login_only():
    """Test login functionality only"""
    global DEBUG_MODE
    DEBUG_MODE = True
    
    debug_print("Testing login only...")
    driver = setup_driver(headless=False)  # Run in visible mode for testing
    
    try:
        success = login_with_debug(driver)
        if success:
            debug_print("Login test successful!")
            time.sleep(10)  # Keep browser open for inspection
        else:
            debug_print("Login test failed!")
        
        input("Press Enter to close browser...")
        driver.quit()
        
    except Exception as e:
        debug_print(f"Login test error: {e}")
        driver.quit()

if __name__ == "__main__":
    print("Twitter Scraper Debug Mode")
    print("1. Test login only")
    print("2. Scrape tweets (visible browser)")
    print("3. Scrape tweets (headless)")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        test_login_only()
    elif choice == "2":
        tweets = scrape_timeline_tweets_debug(limit=5, headless=False)
        print(f"Collected {len(tweets)} tweets")
        for i, tweet in enumerate(tweets):
            print(f"\n--- Tweet {i+1} ---")
            print(f"Author: @{tweet['author']}")
            print(f"Text: {tweet['text'][:100]}...")
            print(f"Date: {tweet['created_at']}")
    elif choice == "3":
        tweets = scrape_timeline_tweets_debug(limit=5, headless=True)
        print(f"Collected {len(tweets)} tweets")
        for i, tweet in enumerate(tweets):
            print(f"\n--- Tweet {i+1} ---")
            print(f"Author: @{tweet['author']}")
            print(f"Text: {tweet['text'][:100]}...")
            print(f"Date: {tweet['created_at']}")
    else:
        print("Invalid choice!")
