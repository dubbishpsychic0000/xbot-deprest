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
    """Initialize and return a Chrome WebDriver with enhanced 2025 anti-detection options."""
    options = Options()
    
    # Basic anti-detection measures
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Comment out headless for debugging, uncomment for production
    # options.add_argument("--headless")
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"Initializing Chrome driver (attempt {attempt + 1}/{max_attempts})...")
            service = Service(executable_path=CM().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Basic stealth scripts
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("Chrome driver initialized successfully")
            return driver
            
        except Exception as e:
            print(f"Chrome driver initialization attempt {attempt + 1} failed: {e}")
            if attempt < max_attempts - 1:
                time.sleep(random.uniform(2, 5))
            else:
                raise Exception(f"Failed to initialize Chrome driver after {max_attempts} attempts: {e}")

def human_like_delay():
    """Add human-like delays to avoid detection."""
    time.sleep(random.uniform(1.5, 4.0))

def login(driver: webdriver.Chrome) -> bool:
    """Enhanced login function for 2025 with better detection avoidance."""
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        print("Twitter credentials not found in environment variables")
        return False
        
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"Login attempt {attempt + 1}/{max_attempts}...")
            
            # Navigate to login
            driver.get("https://x.com/i/flow/login")
            time.sleep(random.uniform(8, 15))
            
            # Find username input
            try:
                username_inp = WebDriverWait(driver, 60).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
                )
            except TimeoutException:
                # Try alternative selector
                username_inp = WebDriverWait(driver, 30).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="text"]'))
                )
            
            username_inp.send_keys(TWITTER_USERNAME)
            username_inp.send_keys(Keys.RETURN)
            print("Username entered successfully")
            
            # Wait for password field
            time.sleep(random.uniform(5, 10))
            
            try:
                password_inp = WebDriverWait(driver, 60).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
                )
            except TimeoutException:
                # Try alternative selector
                password_inp = WebDriverWait(driver, 30).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="password"]'))
                )
            
            password_inp.send_keys(TWITTER_PASSWORD)
            password_inp.send_keys(Keys.RETURN)
            print("Password entered successfully")

            # Wait for login completion
            print("Waiting for login to complete...")
            time.sleep(random.uniform(15, 25))
            
            # Check if login was successful
            current_url = driver.current_url
            if "login" not in current_url.lower() and "flow" not in current_url.lower():
                print("Login successful!")
                return True
            else:
                print(f"Login attempt {attempt + 1} failed, current URL: {current_url}")
                time.sleep(random.uniform(5, 10))

        except Exception as e:
            print(f"Login attempt {attempt + 1} failed with error: {e}")
            time.sleep(random.uniform(5, 10))
    
    print("All login attempts failed")
    return False

def extract_tweet_data_original_format(tweet_element) -> Optional[Tuple[str, str, str, str]]:
    """Extract tweet data in original format - simplified and working version."""
    try:
        # Extract tweet text
        tweet_text = ""
        try:
            text_elem = tweet_element.find_element(By.CSS_SELECTOR, 'div[data-testid="tweetText"]')
            tweet_text = text_elem.text
        except NoSuchElementException:
            try:
                text_elem = tweet_element.find_element(By.CSS_SELECTOR, 'div[lang]')
                tweet_text = text_elem.text
            except NoSuchElementException:
                tweet_text = ""

        # Extract timestamp
        tweet_date = ""
        try:
            time_elem = tweet_element.find_element(By.TAG_NAME, "time")
            timestamp = time_elem.get_attribute("datetime")
            if timestamp:
                tweet_date = parse(timestamp).isoformat().split("T")[0]
        except Exception:
            tweet_date = datetime.now().isoformat().split("T")[0]

        # Extract external link
        external_link = ""
        try:
            anchor = tweet_element.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
            external_link = anchor.get_attribute("href")
        except NoSuchElementException:
            pass

        # Extract images
        tweet_images = []
        try:
            images = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
            tweet_images = [img.get_attribute("src") for img in images]
        except Exception:
            pass

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
            author_elem = tweet_element.find_element(By.CSS_SELECTOR, 'div[data-testid="User-Name"] span')
            author_text = author_elem.text
            if author_text.startswith("@"):
                author = author_text.replace("@", "")
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
    """Common tweet scraping logic - simplified version based on working script."""
    # State management
    state_file = f"{page_type}_scroll_state.pkl" if not username else f"user_{username}_scroll_state.pkl"
    
    # Initialize variables
    scroll_count = 0
    tweets_collected = set()
    tweets_data = []
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_pause_time = 15

    # Load previous state if exists
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

    # Main scrolling loop - similar to working script
    while len(tweets_data) < limit:
        try:
            # Find tweets
            tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
            
            if not tweets:
                print("No tweets found, scrolling to load more...")
                driver.execute_script("window.scrollBy(0, 3000);")
                time.sleep(scroll_pause_time)
                continue

            # Process tweets
            for tweet in tweets:
                if len(tweets_data) >= limit:
                    break
                    
                try:
                    # Extract data in original format (for compatibility)
                    original_data = extract_tweet_data_original_format(tweet)
                    if not original_data:
                        continue
                    
                    tweet_text, tweet_date, external_link, images_links = original_data

                    # Skip empty tweets
                    if not tweet_text.strip() and images_links == "No Images":
                        continue

                    # Check for duplicates
                    tweet_signature = (tweet_text, tweet_date, external_link, images_links)
                    if tweet_signature in tweets_collected:
                        continue
                    
                    tweets_collected.add(tweet_signature)
                    
                    # Convert to bot format
                    bot_format_data = extract_tweet_data_bot_format(tweet)
                    if bot_format_data and bot_format_data.get('text', '').strip():
                        tweets_data.append(bot_format_data)
                        
                        # Print progress like working script
                        print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")
                
                except Exception as e:
                    print(f"Error processing tweet: {e}")
                    continue

            print(f"Collected {len(tweets_data)} tweets so far")
            
            if len(tweets_data) >= limit:
                break

            # Scroll down - same as working script
            driver.execute_script("window.scrollBy(0, 3000);")
            time.sleep(scroll_pause_time)

            # Check if scrolling is stuck - same logic as working script
            new_height = driver.execute_script("return document.body.scrollHeight")
            print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

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

            # Save state periodically
            if scroll_count % 10 == 0:
                save_state()

        except WebDriverException as e:
            print(f"An error occurred during scraping: {e}")
            break
        except Exception as e:
            print(f"Unexpected error during scraping: {e}")
            break

    # Final save and cleanup
    save_state()
    
    # Remove state file on successful completion
    if len(tweets_data) >= limit and os.path.exists(state_file):
        try:
            os.remove(state_file)
            print("Scroll state file cleaned up.")
        except Exception:
            pass

    return tweets_data

def scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """Scrape timeline tweets - keeping function signature and return format."""
    driver = None
    try:
        driver = setup_driver()
        
        # Login
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to home timeline
        print("Navigating to home timeline...")
        driver.get("https://x.com/home")
        time.sleep(25)  # Wait like working script

        # Use common scraping logic
        tweets_data = _scrape_tweets_common(driver, limit, "timeline")

        # Save to Excel file for compatibility with working script
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
                print(f"Saved {len(original_format_data)} tweets to tweets2.xlsx")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print(f"Total tweets collected: {len(tweets_data)}")
        print("Script execution completed.")
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
    """Scrape user tweets - keeping function signature and return format."""
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
        time.sleep(25)  # Wait like working script

        # Use common scraping logic
        tweets_data = _scrape_tweets_common(driver, limit, "user", username)

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
                print(f"Saved {len(original_format_data)} tweets to {filename}")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print(f"Total tweets collected: {len(tweets_data)}")
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

# Additional utility functions - keeping them but simplified

def check_rate_limit(driver: webdriver.Chrome) -> bool:
    """Check if we've hit Twitter's rate limit."""
    try:
        page_content = driver.page_source.lower()
        rate_limit_indicators = ["rate limit exceeded", "too many requests", "try again later"]
        return any(indicator in page_content for indicator in rate_limit_indicators)
    except:
        return False

def handle_popup_dialogs(driver: webdriver.Chrome):
    """Handle various popup dialogs that might appear."""
    try:
        popup_selectors = ['[data-testid="confirmationSheetDialog"]', '[role="dialog"]']
        for selector in popup_selectors:
            try:
                popup = driver.find_element(By.CSS_SELECTOR, selector)
                if popup.is_displayed():
                    close_btn = popup.find_element(By.CSS_SELECTOR, '[aria-label="Close"]')
                    close_btn.click()
                    time.sleep(1)
                    return
            except:
                continue
    except:
        pass

def wait_for_stable_page(driver: webdriver.Chrome, timeout: int = 30):
    """Wait for page to become stable."""
    try:
        start_time = time.time()
        last_height = driver.execute_script("return document.body.scrollHeight")
        stable_count = 0
        
        while time.time() - start_time < timeout:
            time.sleep(2)
            current_height = driver.execute_script("return document.body.scrollHeight")
            
            if current_height == last_height:
                stable_count += 1
                if stable_count >= 3:
                    return True
            else:
                stable_count = 0
            
            last_height = current_height
        
        return False
    except:
        return False
