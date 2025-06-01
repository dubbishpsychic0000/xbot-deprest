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

load_dotenv()

# Fetch credentials from .env
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")

def setup_driver() -> webdriver.Chrome:
    """Initialize and return a Chrome WebDriver with enhanced options."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Disable images and CSS for faster loading
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)

    try:
        service = Service(executable_path=CM().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Execute script to hide automation indicators
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        print(f"Failed to initialize Chrome driver: {e}")
        raise

def login(driver: webdriver.Chrome) -> bool:
    """Log in to Twitter (x.com) with enhanced error handling."""
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        print("Twitter credentials not found in environment variables")
        return False
        
    try:
        print("Navigating to Twitter login page...")
        driver.get("https://x.com/i/flow/login")
        time.sleep(5)
        
        # Wait for and find username input
        username_selectors = [
            'input[autocomplete="username"]',
            'input[name="text"]',
            'input[data-testid="ocfEnterTextTextInput"]'
        ]
        
        username_inp = None
        for selector in username_selectors:
            try:
                username_inp = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                print(f"Found username input with selector: {selector}")
                break
            except TimeoutException:
                continue
        
        if not username_inp:
            print("Could not find username input field")
            return False
            
        username_inp.clear()
        username_inp.send_keys(TWITTER_USERNAME)
        username_inp.send_keys(Keys.RETURN)
        print("Username entered successfully")
        
        time.sleep(3)
        
        # Wait for and find password input
        password_selectors = [
            'input[name="password"]',
            'input[type="password"]',
            'input[data-testid="ocfEnterTextTextInput"]'
        ]
        
        password_inp = None
        for selector in password_selectors:
            try:
                password_inp = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                print(f"Found password input with selector: {selector}")
                break
            except TimeoutException:
                continue
        
        if not password_inp:
            print("Could not find password input field")
            return False
            
        password_inp.clear()
        password_inp.send_keys(TWITTER_PASSWORD)
        password_inp.send_keys(Keys.RETURN)
        print("Password entered successfully")

        # Wait for login completion
        print("Waiting for login to complete...")
        time.sleep(10)
        
        # Check for successful login
        try:
            WebDriverWait(driver, 30).until(
                lambda d: any(keyword in d.current_url.lower() for keyword in ["home", "twitter.com", "x.com"]) 
                         and "login" not in d.current_url.lower()
            )
            print("Login successful!")
            return True
        except TimeoutException:
            current_url = driver.current_url
            print(f"Login verification timeout. Current URL: {current_url}")
            
            # Check if we're actually logged in despite timeout
            if "login" not in current_url.lower():
                print("Login appears successful based on URL")
                return True
            return False

    except Exception as e:
        print(f"Login failed with error: {e}")
        return False

def extract_tweet_data_original_format(tweet_element) -> Optional[Tuple[str, str, str, str]]:
    """
    Extract tweet data from a Selenium WebElement with enhanced selectors.
    Returns tuple: (tweet_text, tweet_date, external_link, images_links)
    """
    try:
        # Extract tweet text
        tweet_text = ""
        text_selectors = [
            'div[data-testid="tweetText"]',
            'div[lang]',
            'span[lang]',
            '.css-901oao'
        ]
        
        for selector in text_selectors:
            try:
                text_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                tweet_text = text_elem.text.strip()
                if tweet_text:
                    break
            except NoSuchElementException:
                continue

        # Extract timestamp
        tweet_date = ""
        try:
            time_elem = tweet_element.find_element(By.TAG_NAME, "time")
            timestamp = time_elem.get_attribute("datetime")
            if timestamp:
                tweet_date = parse(timestamp).isoformat().split("T")[0]
            else:
                # Fallback to title or text
                timestamp = time_elem.get_attribute("title") or time_elem.text
                if timestamp:
                    try:
                        tweet_date = parse(timestamp).isoformat().split("T")[0]
                    except:
                        tweet_date = datetime.now().isoformat().split("T")[0]
        except NoSuchElementException:
            tweet_date = datetime.now().isoformat().split("T")[0]

        # Extract external link
        external_link = ""
        link_selectors = [
            "a[href*='/status/']",
            "a[role='link'][href*='status']",
            "time[datetime]"
        ]
        
        for selector in link_selectors:
            try:
                if selector == "time[datetime]":
                    # Get parent link of time element
                    time_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                    parent_link = time_elem.find_element(By.XPATH, "./ancestor::a[@href]")
                    href = parent_link.get_attribute("href")
                else:
                    anchor = tweet_element.find_element(By.CSS_SELECTOR, selector)
                    href = anchor.get_attribute("href")
                
                if href and "/status/" in href:
                    external_link = href
                    break
            except NoSuchElementException:
                continue

        # Extract images
        tweet_images = []
        image_selectors = [
            'div[data-testid="tweetPhoto"] img',
            'img[alt*="Image"]',
            'div[data-testid="card.layoutLarge.media"] img',
            'img[src*="pbs.twimg.com"]'
        ]
        
        for selector in image_selectors:
            try:
                images = tweet_element.find_elements(By.CSS_SELECTOR, selector)
                for img in images:
                    src = img.get_attribute("src")
                    if src and "pbs.twimg.com" in src and src not in tweet_images:
                        tweet_images.append(src)
            except Exception:
                continue

        images_links = ', '.join(tweet_images) if tweet_images else "No Images"

        return (tweet_text, tweet_date, external_link, images_links)

    except Exception as e:
        print(f"Failed to extract tweet data: {e}")
        return None

def extract_tweet_data_bot_format(tweet_element) -> Optional[Dict]:
    """
    Extract tweet data from a Selenium WebElement and return in bot-compatible format.
    Returns dict with keys: id, text, url, created_at, author, media
    """
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

        # Extract author username
        author = "unknown"
        author_selectors = [
            'div[data-testid="User-Name"] a span',
            'div[data-testid="User-Name"] span',
            '[data-testid="User-Name"] span',
            'a[role="link"] span'
        ]
        
        for selector in author_selectors:
            try:
                usr_elems = tweet_element.find_elements(By.CSS_SELECTOR, selector)
                for elem in usr_elems:
                    text = elem.text.strip()
                    if text.startswith("@"):
                        author = text.replace("@", "")
                        break
                if author != "unknown":
                    break
            except:
                continue

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
    """
    Common tweet scraping logic for both timeline and user tweets.
    """
    # State management
    state_file = f"{page_type}_scroll_state.pkl" if not username else f"user_{username}_scroll_state.pkl"
    
    # Initialize variables
    scroll_count = 0
    tweets_collected = set()
    tweets_data = []
    last_height = driver.execute_script("return window.pageYOffset;")

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

    # Scraping parameters
    scroll_pause_time = 8
    max_scrolls = 15
    stuck_threshold = 3
    stuck_count = 0

    # Tweet selectors
    tweet_selectors = [
        'article[data-testid="tweet"]',
        'div[data-testid="tweet"]',
        'article[role="article"]'
    ]

    print(f"Starting to scrape {page_type} tweets...")

    while scroll_count < max_scrolls and len(tweets_data) < limit:
        try:
            print(f"\n--- Scroll iteration {scroll_count + 1} ---")
            
            # Find tweets using multiple selectors
            tweets = []
            for selector in tweet_selectors:
                try:
                    found_tweets = driver.find_elements(By.CSS_SELECTOR, selector)
                    if found_tweets:
                        tweets = found_tweets
                        print(f"Found {len(tweets)} tweets using selector: {selector}")
                        break
                except Exception as e:
                    continue
            
            if not tweets:
                print("No tweets found, scrolling to load more...")
                driver.execute_script("window.scrollBy(0, 1000);")
                time.sleep(5)
                scroll_count += 1
                continue

            # Process tweets
            processed_count = 0
            for i, tweet in enumerate(tweets):
                if len(tweets_data) >= limit:
                    break
                    
                try:
                    # Extract data
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
                    if bot_format_data:
                        tweets_data.append(bot_format_data)
                        processed_count += 1
                        
                        print(f"Tweet {len(tweets_data)}: {tweet_text[:80]}..." if len(tweet_text) > 80 else f"Tweet {len(tweets_data)}: {tweet_text}")
                
                except Exception as e:
                    print(f"Error processing tweet {i+1}: {e}")
                    continue

            print(f"Processed {processed_count} new tweets")
            
            if len(tweets_data) >= limit:
                print(f"Reached limit of {limit} tweets")
                break

            # Scroll and check for progress
            print("Scrolling down...")
            driver.execute_script("window.scrollBy(0, 1500);")
            time.sleep(scroll_pause_time)

            # Check if we're stuck
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                stuck_count += 1
                print(f"Scrolling stuck (attempt {stuck_count}/{stuck_threshold})")
                
                if stuck_count >= stuck_threshold:
                    print("Maximum stuck attempts reached. Ending scrape.")
                    break
                    
                # Try recovery
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_pause_time * 2)
                new_height = driver.execute_script("return document.body.scrollHeight")
            else:
                stuck_count = 0  # Reset stuck counter

            last_height = new_height
            scroll_count += 1

            # Save state periodically
            if scroll_count % 3 == 0:
                save_state()

        except WebDriverException as e:
            print(f"WebDriver error: {e}")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            break

    # Final save and cleanup
    save_state()
    
    # Remove state file on successful completion
    if len(tweets_data) >= limit and os.path.exists(state_file):
        try:
            os.remove(state_file)
        except Exception:
            pass

    return tweets_data

def scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """
    Scrape tweets from the Twitter home timeline.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    driver = setup_driver()
    
    try:
        # Login
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to home timeline
        print("Navigating to home timeline...")
        driver.get("https://x.com/home")
        
        # Wait for timeline to load
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            print("Timeline loaded successfully!")
        except TimeoutException:
            print("Timeline loading timeout - continuing anyway")
        
        time.sleep(5)

        # Use common scraping logic
        tweets_data = _scrape_tweets_common(driver, limit, "timeline")

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
                print(f"Saved {len(original_format_data)} tweets to tweets2.xlsx")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print(f"Timeline scraping completed. Total tweets: {len(tweets_data)}")
        return tweets_data

    except Exception as e:
        print(f"Error in scrape_timeline_tweets: {e}")
        return []
    finally:
        driver.quit()

def scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """
    Scrape tweets from a specific user's profile.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    # Clean username
    username = username.replace('@', '').strip()
    if not username:
        print("Invalid username provided")
        return []
    
    driver = setup_driver()
    
    try:
        # Login
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to user profile
        profile_url = f"https://x.com/{username}"
        print(f"Navigating to user profile: {profile_url}")
        driver.get(profile_url)
        
        # Wait for profile to load
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            print("Profile loaded successfully!")
        except TimeoutException:
            print("Profile loading timeout - checking if user exists...")
            
            # Check if profile exists
            if any(phrase in driver.page_source.lower() for phrase in 
                   ["this account doesn't exist", "account suspended", "user not found"]):
                print(f"User @{username} does not exist or is suspended!")
                return []
            
            print("Continuing anyway...")
        
        time.sleep(5)

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
                df.to_excel(f"{username}_tweets.xlsx", index=False)
                print(f"Saved {len(original_format_data)} tweets to {username}_tweets.xlsx")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        print(f"User scraping completed. Total tweets: {len(tweets_data)}")
        return tweets_data

    except Exception as e:
        print(f"Error in scrape_user_tweets: {e}")
        return []
    finally:
        driver.quit()
