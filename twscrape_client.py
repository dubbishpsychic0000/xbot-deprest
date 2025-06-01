import time
import os
import hashlib
import json
import pickle
from typing import List, Dict, Optional, Tuple
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
import random
import requests

load_dotenv()

# Fetch credentials from .env
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")

def setup_driver() -> webdriver.Chrome:
    """Initialize and return a Chrome WebDriver with anti-detection options."""
    options = Options()
    
    # Basic options similar to working script
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Comment out headless for debugging - same as working script approach
    # options.add_argument("--headless")
    
    try:
        print("Initializing Chrome driver...")
        service = Service(executable_path=CM().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Basic stealth script
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("Chrome driver initialized successfully")
        return driver
        
    except Exception as e:
        raise Exception(f"Failed to initialize Chrome driver: {e}")

def human_like_delay():
    """Add human-like delays to avoid detection."""
    time.sleep(random.uniform(2, 5))

def login(driver: webdriver.Chrome) -> bool:
    """Login function similar to working script approach."""
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        print("Twitter credentials not found in environment variables")
        return False
        
    try:
        print("Attempting to login...")
        
        # Navigate to login
        driver.get("https://x.com/i/flow/login")
        time.sleep(10)  # Wait for page load
        
        # Find username input - using same approach as working script
        try:
            username_inp = WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
            )
        except TimeoutException:
            print("Could not find username input field")
            return False
        
        # Enter username
        username_inp.send_keys(TWITTER_USERNAME)
        username_inp.send_keys(Keys.RETURN)
        print("Username entered successfully")
        
        # Wait for password field
        time.sleep(10)
        
        try:
            password_inp = WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
            )
        except TimeoutException:
            print("Could not find password input field")
            return False
        
        # Enter password
        password_inp.send_keys(TWITTER_PASSWORD)
        password_inp.send_keys(Keys.RETURN)
        print("Password entered successfully")

        # Wait for login completion - similar to working script
        print("Waiting for login to complete...")
        time.sleep(25)  # Same as working script
        
        print("Login completed!")
        return True
                
    except Exception as e:
        print(f"Login failed with error: {e}")
        return False

def extract_tweet_data_original_format(tweet_element) -> Optional[Tuple[str, str, str, str]]:
    """Extract tweet data in original format - matching working script exactly."""
    try:
        # Extract tweet text - same selectors as working script
        tweet_text = ""
        try:
            tweet_text = tweet_element.find_element(By.CSS_SELECTOR, 'div[lang]').text
        except NoSuchElementException:
            tweet_text = ""
            
        # Extract timestamp - same approach as working script
        tweet_date = ""
        try:
            timestamp = tweet_element.find_element(By.TAG_NAME, "time").get_attribute("datetime")
            tweet_date = parse(timestamp).isoformat().split("T")[0]
        except Exception as ex:
            tweet_date = ""
            
        # Extract external link - same approach as working script
        external_link = ""
        try:
            anchor = tweet_element.find_element(By.CSS_SELECTOR, "a[aria-label][dir]")
            external_link = anchor.get_attribute("href")
        except Exception as ex:
            external_link = ""
            
        # Extract images - same approach as working script
        tweet_images = []
        try:
            images = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
            tweet_images = [img.get_attribute("src") for img in images]
        except Exception as ex:
            tweet_images = []

        images_links = ', '.join(tweet_images) if tweet_images else "No Images"

        return (tweet_text, tweet_date, external_link, images_links)

    except Exception as e:
        print(f"Failed to extract tweet data: {e}")
        return None

def extract_tweet_data_bot_format(tweet_element) -> Optional[Dict]:
    """Extract tweet data and return in bot-compatible format."""
    try:
        # Get original format data first
        original_data = extract_tweet_data_original_format(tweet_element)
        if not original_data:
            return None
        
        tweet_text, tweet_date, external_link, images_links = original_data

        # Convert timestamp to ISO format
        try:
            if tweet_date:
                created_at = f"{tweet_date}T00:00:00"
            else:
                created_at = datetime.now().isoformat()
        except Exception:
            created_at = datetime.now().isoformat()

        # Extract tweet URL and ID
        tweet_url = external_link
        tweet_id = ""
        
        if tweet_url and "/status/" in tweet_url:
            tweet_id = tweet_url.split("/status/")[-1].split("?")[0].split("/")[0]
        
        # Fallback ID generation
        if not tweet_id:
            fallback_hash = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            if not tweet_url:
                tweet_url = f"https://x.com/status/{fallback_hash}"

        # Extract author
        author = "unknown"
        try:
            # Try to find username in tweet
            usr_elems = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="User-Name"] a span')
            for elem in usr_elems:
                text = elem.text.strip()
                if text.startswith("@"):
                    author = text.replace("@", "")
                    break
        except:
            pass

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
        return scrape_timeline_tweets(limit)
    elif source_type == "user":
        return scrape_user_tweets(source, limit)
    else:
        print(f"Unsupported source_type: {source_type}")
        return []

def _scrape_tweets_common(driver: webdriver.Chrome, limit: int, page_type: str, username: str = None) -> List[Dict]:
    """Common tweet scraping logic - simplified but based on working script."""
    # State management - similar to working script
    state_file = f"{page_type}_scroll_state.pkl" if not username else f"user_{username}_scroll_state.pkl"
    
    # Initialize variables - same as working script
    scroll_count = 0
    tweets_collected = set()
    tweets_data = []
    last_height = driver.execute_script("return window.pageYOffset;")
    scroll_pause_time = 15  # Same as working script

    # Load previous state if exists - same as working script
    if os.path.exists(state_file):
        try:
            with open(state_file, "rb") as f:
                scroll_count, last_height, tweets_collected, tweets_data = pickle.load(f)
                print(f"Resumed from previous state: {len(tweets_data)} tweets")
        except Exception as e:
            print(f"Error loading state: {e}. Starting fresh.")

    def save_state():
        try:
            with open(state_file, "wb") as f:
                pickle.dump((scroll_count, last_height, tweets_collected, tweets_data), f)
        except Exception as e:
            print(f"Error saving state: {e}")

    print(f"Starting to scrape {page_type} tweets...")

    # Main scraping loop - similar structure to working script
    while len(tweets_data) < limit:
        try:
            # Find tweets - same selector as working script
            tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            
            if not tweets:
                print("No tweets found, scrolling to load more...")
                # Scroll down - same as working script
                driver.execute_script("window.scrollBy(0, 3000);")
                time.sleep(scroll_pause_time)
                continue

            # Process tweets
            for tweet in tweets:
                if len(tweets_data) >= limit:
                    break
                    
                try:
                    # Extract data in original format - same as working script
                    original_data = extract_tweet_data_original_format(tweet)
                    if not original_data:
                        continue
                    
                    tweet_text, tweet_date, external_link, images_links = original_data

                    # Skip empty tweets
                    if not tweet_text.strip() and images_links == "No Images":
                        continue

                    # Check for duplicates - same logic as working script
                    tweet_signature = (tweet_text, tweet_date, external_link, images_links)
                    if tweet_signature in tweets_collected:
                        continue
                    
                    tweets_collected.add(tweet_signature)
                    
                    # Convert to bot format
                    bot_format_data = extract_tweet_data_bot_format(tweet)
                    if bot_format_data and bot_format_data.get('text', '').strip():
                        tweets_data.append(bot_format_data)
                        
                        # Print progress - same format as working script
                        print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")
                
                except Exception as e:
                    print(f"Error processing tweet: {e}")
                    continue
            
            if len(tweets_data) >= limit:
                break

            # Scroll down - same as working script
            driver.execute_script("window.scrollBy(0, 3000);")
            time.sleep(scroll_pause_time)

            # Update heights - same logic as working script
            new_height = driver.execute_script("return document.body.scrollHeight")
            print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

            # Check if scrolling is stuck - same logic as working script
            if new_height == last_height:
                print("Scrolling stuck, waiting...")
                time.sleep(scroll_pause_time * 2)
                new_height = driver.execute_script("return document.body.scrollHeight")

                if new_height == last_height:
                    print("Scrolling still stuck, attempting to break...")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause_time * 4)
                    new_height = driver.execute_script("return document.body.scrollHeight")

                    if new_height == last_height:
                        print("Scrolling broken, exiting...")
                        break

            last_height = new_height
            scroll_count += 1

            # Save state periodically - same as working script
            if scroll_count % 10 == 0:
                save_state()

        except WebDriverException as e:
            print(f"An error occurred during scraping: {e}")
            break

    # Save final state
    save_state()
    
    # Remove state file on successful completion - same as working script
    if len(tweets_data) >= limit and os.path.exists(state_file):
        try:
            os.remove(state_file)
        except Exception:
            pass

    return tweets_data

def scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """Scrape timeline tweets - maintaining exact function signature."""
    driver = None
    try:
        driver = setup_driver()
        
        # Login
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to home timeline - same as working script
        print("Navigating to home timeline...")
        driver.get("https://x.com/home")  # Changed from Twitter(X)_page_link to home
        time.sleep(25)  # Same wait time as working script

        # Use common scraping logic
        tweets_data = _scrape_tweets_common(driver, limit, "timeline")

        # Save to Excel file for compatibility - same as working script
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
                df.to_excel("tweets2.xlsx", index=False)  # Same filename as working script
                print(f"Total tweets collected: {len(original_format_data)}")  # Same message as working script
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print("Script execution completed.")  # Same message as working script
        return tweets_data

    except Exception as e:
        print(f"Error in scrape_timeline_tweets: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                print(f"Error during driver cleanup: {e}")

def scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Scrape user tweets - maintaining exact function signature."""
    # Clean username
    username = username.replace('@', '').strip()
    if not username:
        print("Invalid username provided")
        return []
    
    driver = None
    try:
        driver = setup_driver()
        
        # Login
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to user profile
        profile_url = f"https://x.com/{username}"
        print(f"Navigating to user profile: {profile_url}")
        driver.get(profile_url)
        time.sleep(25)  # Same wait time as working script

        # Use common scraping logic
        tweets_data = _scrape_tweets_common(driver, limit, "user", username)

        # Save to Excel file - same format as working script but with username
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
        print(f"Error in scrape_user_tweets: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                print(f"Error during driver cleanup: {e}")

# Keep all utility functions for compatibility but simplified
def check_rate_limit(driver: webdriver.Chrome) -> bool:
    """Check if we've hit Twitter's rate limit."""
    return False

def handle_popup_dialogs(driver: webdriver.Chrome):
    """Handle various popup dialogs that might appear."""
    pass

def wait_for_stable_page(driver: webdriver.Chrome, timeout: int = 30):
    """Wait for page to become stable."""
    time.sleep(5)
    return True
