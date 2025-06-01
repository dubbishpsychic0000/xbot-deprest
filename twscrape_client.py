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

def setup_driver() -> webdriver.Chrome:
    """Initialize and return a Chrome WebDriver with enhanced options."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    # Comment out headless mode for debugging
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Disable images and CSS for faster loading (optional)
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)

    service = Service(executable_path=CM().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Execute script to hide automation indicators
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def login(driver: webdriver.Chrome) -> bool:
    """Log in to Twitter (x.com) with enhanced error handling."""
    try:
        print("Navigating to Twitter login page...")
        driver.get("https://x.com/i/flow/login")
        
        # Wait for page to load completely
        time.sleep(5)
        
        # Multiple selectors for username input (Twitter changes these frequently)
        username_selectors = [
            'input[autocomplete="username"]',
            'input[name="text"]',
            'input[data-testid="ocfEnterTextTextInput"]'
        ]
        
        username_inp = None
        for selector in username_selectors:
            try:
                username_inp = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
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
        
        # Wait and check for password field
        time.sleep(3)
        
        # Multiple selectors for password input
        password_selectors = [
            'input[name="password"]',
            'input[type="password"]',
            'input[data-testid="ocfEnterTextTextInput"]'
        ]
        
        password_inp = None
        for selector in password_selectors:
            try:
                password_inp = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
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

        # Wait for login to complete and check for success
        print("Waiting for login to complete...")
        time.sleep(10)
        
        # Check if we're successfully logged in by looking for home feed
        try:
            WebDriverWait(driver, 30).until(
                lambda d: "home" in d.current_url.lower() or "twitter.com" in d.current_url or "x.com" in d.current_url
            )
            print("Login successful!")
            return True
        except TimeoutException:
            print("Login may have failed - checking current URL:", driver.current_url)
            # Sometimes login succeeds but URL doesn't change immediately
            if "login" not in driver.current_url.lower():
                print("Login appears successful based on URL")
                return True
            return False

    except Exception as e:
        print(f"[!] Login failed: {e}")
        print(f"Current URL: {driver.current_url}")
        return False

def extract_tweet_data_original_format(tweet_element) -> Optional[tuple]:
    """
    Extract tweet data from a Selenium WebElement with enhanced selectors.
    Returns tuple: (tweet_text, tweet_date, external_link, images_links)
    """
    try:
        # Enhanced tweet text extraction with multiple selectors
        tweet_text = ""
        text_selectors = [
            'div[lang]',
            'div[data-testid="tweetText"]',
            'span[lang]',
            '.css-1dbjc4n .css-901oao'
        ]
        
        for selector in text_selectors:
            try:
                text_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                tweet_text = text_elem.text.strip()
                if tweet_text:
                    break
            except NoSuchElementException:
                continue
        
        if not tweet_text:
            print("No tweet text found with any selector")

        # Enhanced timestamp extraction
        tweet_date = ""
        try:
            time_elem = tweet_element.find_element(By.TAG_NAME, "time")
            timestamp = time_elem.get_attribute("datetime")
            if timestamp:
                tweet_date = parse(timestamp).isoformat().split("T")[0]
            else:
                # Fallback to title attribute or text content
                timestamp = time_elem.get_attribute("title") or time_elem.text
                if timestamp:
                    tweet_date = parse(timestamp).isoformat().split("T")[0]
        except Exception as ex:
            print(f"Error parsing date: {ex}")

        # Enhanced external link extraction
        external_link = ""
        link_selectors = [
            "a[aria-label][dir]",
            "a[href*='/status/']",
            "a[role='link'][href*='status']"
        ]
        
        for selector in link_selectors:
            try:
                anchor = tweet_element.find_element(By.CSS_SELECTOR, selector)
                href = anchor.get_attribute("href")
                if href and "/status/" in href:
                    external_link = href
                    break
            except Exception:
                continue

        # Enhanced image extraction with multiple selectors
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
                    if src and src not in tweet_images:
                        tweet_images.append(src)
            except Exception:
                continue

        images_links = ', '.join(tweet_images) if tweet_images else "No Images"

        return (tweet_text, tweet_date, external_link, images_links)

    except Exception as e:
        print(f"[!] Failed to extract tweet data: {e}")
        return None

def extract_tweet_data_bot_format(tweet_element) -> Optional[Dict]:
    """
    Extract tweet data from a Selenium WebElement and return in bot-compatible format.
    Returns dict with keys: id, text, url, created_at, author, media
    """
    try:
        # First get the original format data
        original_data = extract_tweet_data_original_format(tweet_element)
        if not original_data:
            return None
        
        tweet_text, tweet_date, external_link, images_links = original_data

        # Convert timestamp to ISO format for bot compatibility
        try:
            if tweet_date:
                created_at = f"{tweet_date}T00:00:00"
            else:
                created_at = datetime.now().isoformat()
        except Exception:
            created_at = datetime.now().isoformat()

        # Enhanced tweet URL and ID extraction
        tweet_url = ""
        tweet_id = ""
        
        # Try to get real URL first with multiple selectors
        url_selectors = [
            "a[href*='/status/']",
            "a[role='link'][href*='status']",
            "time[datetime] parent::a"
        ]
        
        for selector in url_selectors:
            try:
                link_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                href = link_elem.get_attribute("href")
                if href and "/status/" in href:
                    tweet_url = href
                    tweet_id = href.split("/status/")[-1].split("?")[0]
                    break
            except Exception:
                continue
        
        # Fallback: use external_link if found
        if not tweet_url and external_link:
            tweet_url = external_link
            if "/status/" in external_link:
                tweet_id = external_link.split("/status/")[-1].split("?")[0]
        
        # Final fallback: hash text+date for unique ID
        if not tweet_id:
            fallback_hash = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            tweet_url = f"https://x.com/status/{fallback_hash}"

        # Enhanced author username extraction
        author = "unknown"
        author_selectors = [
            'div[data-testid="User-Name"] span',
            'div[data-testid="User-Name"] a span',
            '[data-testid="User-Name"] span',
            'a[role="link"] span',
            'div[dir="ltr"] span'
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

        # Convert images to list format
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
        print(f"[!] Failed to extract tweet data for bot format: {e}")
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
        return []

def scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """
    Scrape tweets from the Twitter home timeline with enhanced debugging.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    
    # State management files
    scroll_state_file = "scroll_state.pkl"
    
    driver = setup_driver()
    
    try:
        # 1) Log in first
        print("Attempting to log in...")
        if not login(driver):
            print("Login failed!")
            driver.quit()
            return []

        # 2) Navigate to home timeline
        print("Navigating to home timeline...")
        driver.get("https://x.com/home")
        
        # Wait for timeline to load with better detection
        print("Waiting for timeline to load...")
        try:
            # Wait for tweets to appear
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            print("Timeline loaded successfully!")
        except TimeoutException:
            print("Timeline did not load properly. Checking page source...")
            print(f"Current URL: {driver.current_url}")
            print(f"Page title: {driver.title}")
            
            # Try alternative selectors
            alternative_selectors = [
                'div[aria-label*="Timeline"]',
                'section[aria-labelledby*="accessible-list"]',
                'div[data-testid="primaryColumn"]'
            ]
            
            found_timeline = False
            for selector in alternative_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    if elem:
                        print(f"Found timeline element with selector: {selector}")
                        found_timeline = True
                        break
                except:
                    continue
            
            if not found_timeline:
                print("Could not detect timeline. Continuing anyway...")
        
        time.sleep(10)  # Additional wait for content to load

        # Initialize scrolling variables
        scroll_count = 0
        tweets_collected = set()
        tweets_data = []

        # Load previous state from pickle file if exists
        if os.path.exists(scroll_state_file):
            with open(scroll_state_file, "rb") as f:
                try:
                    scroll_count, last_height, tweets_collected, tweets_data = pickle.load(f)
                    print("Resumed from previous state.")
                except Exception as e:
                    print(f"Error loading state from {scroll_state_file}: {e}")
                    print("Starting fresh.")
        else:
            print("No previous state found. Starting fresh.")
            last_height = driver.execute_script("return window.pageYOffset;")

        # Function to save current state to pickle file
        def save_state():
            with open(scroll_state_file, "wb") as f:
                pickle.dump((scroll_count, last_height, tweets_collected, tweets_data), f)

        # Scrolling variables
        scroll_pause_time = 10  # Reduced from 15 for faster testing
        new_height = 0
        max_scrolls = 20  # Add maximum scroll limit for safety

        # Enhanced tweet detection with multiple selectors
        tweet_selectors = [
            'article[data-testid="tweet"]',
            'div[data-testid="tweet"]',
            'article[role="article"]'
        ]

        # Main scrolling loop with enhanced debugging
        while scroll_count < max_scrolls:
            try:
                print(f"\n--- Scroll iteration {scroll_count + 1} ---")
                
                # Try multiple selectors to find tweets
                tweets = []
                for selector in tweet_selectors:
                    try:
                        found_tweets = driver.find_elements(By.CSS_SELECTOR, selector)
                        if found_tweets:
                            tweets = found_tweets
                            print(f"Found {len(tweets)} tweets using selector: {selector}")
                            break
                    except Exception as e:
                        print(f"Error with selector {selector}: {e}")
                        continue
                
                if not tweets:
                    print("No tweets found with any selector. Checking page structure...")
                    # Debug: Check what's actually on the page
                    body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
                    print(f"Page body preview: {body_text}")
                    
                    # Try scrolling and continue
                    driver.execute_script("window.scrollBy(0, 1000);")
                    time.sleep(5)
                    scroll_count += 1
                    continue

                print(f"Processing {len(tweets)} tweet elements...")
                processed_count = 0
                
                for i, tweet in enumerate(tweets):
                    try:
                        # Extract in original format first
                        original_data = extract_tweet_data_original_format(tweet)
                        if not original_data:
                            continue
                        
                        tweet_text, tweet_date, external_link, images_links = original_data

                        # Skip if no meaningful content
                        if not tweet_text.strip() and images_links == "No Images":
                            continue

                        # Check for duplicates using original format
                        if (tweet_text, tweet_date, external_link, images_links) not in tweets_collected:
                            tweets_collected.add((tweet_text, tweet_date, external_link, images_links))
                            
                            # Convert to bot format for return
                            bot_format_data = extract_tweet_data_bot_format(tweet)
                            if bot_format_data:
                                tweets_data.append(bot_format_data)
                                processed_count += 1
                            
                            # Print in original format
                            print(f"NEW TWEET {len(tweets_data)}: Date: {tweet_date}, Tweet: {tweet_text[:100]}..., Link: {external_link}, Images: {images_links}")
                            
                            # Stop if we have enough tweets
                            if len(tweets_data) >= limit:
                                print(f"Reached limit of {limit} tweets, stopping...")
                                break
                        else:
                            print(f"Tweet {i+1}: Duplicate detected, skipping...")
                    
                    except Exception as e:
                        print(f"Error processing tweet {i+1}: {e}")
                        continue

                print(f"Processed {processed_count} new tweets in this iteration")
                
                # Break if we have enough tweets
                if len(tweets_data) >= limit:
                    break

                # Scroll down with enhanced logic
                print("Scrolling down...")
                driver.execute_script("window.scrollBy(0, 2000);")
                time.sleep(scroll_pause_time)

                # Update heights
                new_height = driver.execute_script("return document.body.scrollHeight")
                print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

                # Enhanced stuck detection
                if new_height == last_height:
                    print("Scrolling stuck, trying recovery methods...")
                    
                    # Method 1: Wait longer
                    time.sleep(scroll_pause_time * 2)
                    new_height = driver.execute_script("return document.body.scrollHeight")

                    if new_height == last_height:
                        print("Still stuck, trying aggressive scroll...")
                        # Method 2: More aggressive scrolling
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(scroll_pause_time * 2)
                        new_height = driver.execute_script("return document.body.scrollHeight")

                        if new_height == last_height:
                            print("Scrolling completely stuck. Checking if we have any tweets...")
                            if len(tweets_data) > 0:
                                print(f"We have {len(tweets_data)} tweets, continuing with those.")
                                break
                            else:
                                print("No tweets collected and scrolling stuck. Exiting...")
                                break

                last_height = new_height
                scroll_count += 1

                # Save state periodically
                if scroll_count % 5 == 0:
                    save_state()
                    print(f"State saved. Total tweets so far: {len(tweets_data)}")

            except WebDriverException as e:
                print(f"WebDriver error during scraping: {e}")
                break
            except Exception as e:
                print(f"Unexpected error during scraping: {e}")
                break

        # Final save
        save_state()

        # Close the browser
        driver.quit()

        # Create Excel file in original format for compatibility
        if tweets_data:
            try:
                original_format_data = []
                for tweet_data in tweets_data:
                    # Convert back to original format for Excel
                    media_str = ', '.join(tweet_data.get('media', [])) if tweet_data.get('media') else "No Images"
                    original_format_data.append([
                        tweet_data.get('text', ''),
                        tweet_data.get('created_at', '').split('T')[0],  # Extract date part
                        tweet_data.get('url', ''),
                        media_str
                    ])
                
                df = pd.DataFrame(original_format_data, columns=["Tweet", "Date", "Link", "Images"])
                df.to_excel("tweets2.xlsx", index=False)
                print(f"Saved {len(original_format_data)} tweets to tweets2.xlsx")
            except Exception as e:
                print(f"Failed to save Excel file: {e}")

        # Print the total number of tweets collected
        print(f"Total tweets collected: {len(tweets_data)}")

        # Delete the scroll state file after successful scraping
        if os.path.exists(scroll_state_file):
            os.remove(scroll_state_file)

        print("Script execution completed.")
        
        return tweets_data

    except Exception as e:
        print(f"Error in scrape_timeline_tweets: {e}")
        driver.quit()
        return []

def scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """
    Scrape tweets from a specific user's profile with enhanced error handling.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    # Remove @ if present
    username = username.replace('@', '')
    
    # State management files
    scroll_state_file = f"user_{username}_scroll_state.pkl"
    
    driver = setup_driver()
    
    try:
        # 1) Log in first
        print("Attempting to log in...")
        if not login(driver):
            print("Login failed!")
            driver.quit()
            return []

        # 2) Navigate to user profile
        profile_url = f"https://x.com/{username}"
        print(f"Navigating to user profile: {profile_url}")
        driver.get(profile_url)
        
        # Wait for profile to load
        print("Waiting for profile to load...")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            print("Profile loaded successfully!")
        except TimeoutException:
            print("Profile did not load properly or user has no tweets")
            print(f"Current URL: {driver.current_url}")
            print(f"Page title: {driver.title}")
            
            # Check if profile exists
            if "This account doesn't exist" in driver.page_source:
                print(f"User @{username} does not exist!")
                driver.quit()
                return []
            
            print("Continuing anyway...")
        
        time.sleep(10)

        # Initialize scrolling variables - same as timeline
        scroll_count = 0
        tweets_collected = set()
        tweets_data = []

        # Load previous state from pickle file if exists
        if os.path.exists(scroll_state_file):
            with open(scroll_state_file, "rb") as f:
                try:
                    scroll_count, last_height, tweets_collected, tweets_data = pickle.load(f)
                    print("Resumed from previous state.")
                except Exception as e:
                    print(f"Error loading state from {scroll_state_file}: {e}")
                    print("Starting fresh.")
        else:
            print("No previous state found. Starting fresh.")
            last_height = driver.execute_script("return window.pageYOffset;")

        # Function to save current state to pickle file
        def save_state():
            with open(scroll_state_file, "wb") as f:
                pickle.dump((scroll_count, last_height, tweets_collected, tweets_data), f)

        # Scrolling variables
        scroll_pause_time = 10
        new_height = 0
        max_scrolls = 20

        # Enhanced tweet detection with multiple selectors
        tweet_selectors = [
            'article[data-testid="tweet"]',
            'div[data-testid="tweet"]',
            'article[role="article"]'
        ]

        # Main scrolling loop - same enhanced logic as timeline
        while scroll_count < max_scrolls:
            try:
                print(f"\n--- Scroll iteration {scroll_count + 1} ---")
                
                # Try multiple selectors to find tweets
                tweets = []
                for selector in tweet_selectors:
                    try:
                        found_tweets = driver.find_elements(By.CSS_SELECTOR, selector)
                        if found_tweets:
                            tweets = found_tweets
                            print(f"Found {len(tweets)} tweets using selector: {selector}")
                            break
                    except Exception as e:
                        print(f"Error with selector {selector}: {e}")
                        continue
                
                if not tweets:
                    print("No tweets found. Trying to scroll and continue...")
                    driver.execute_script("window.scrollBy(0, 1000);")
                    time.sleep(5)
                    scroll_count += 1
                    continue

                print(f"Processing {len(tweets)} tweet elements...")
                processed_count = 0
                
                for i, tweet in enumerate(tweets):
                    try:
                        # Extract in original format first
                        original_data = extract_tweet_data_original_format(tweet)
                        if not original_data:
                            continue
                        
                        tweet_text, tweet_date, external_link, images_links = original_data

                        # Skip if no meaningful content
                        if not tweet_text.strip() and images_links == "No Images":
                            continue

                        # Check for duplicates using original format
                        if (tweet_text, tweet_date, external_link, images_links) not in tweets_collected:
                            tweets_collected.add((tweet_text, tweet_date, external_link, images_links))
                            
                            # Convert to bot format for return
                            bot_format_data = extract_tweet_data_bot_format(tweet)
                            if bot_format_data:
                                tweets_data.append(bot_format_data)
                                processed_count += 1
                            
                            # Print in original format
                            print(f"NEW TWEET {len(tweets_data)}: Date: {tweet_date}, Tweet: {tweet_text[:100]}..., Link: {external_link}, Images: {images_links}")
                            
                            # Stop if we have enough tweets
                            if len(tweets_data) >= limit:
                                print(f"Reached limit of {limit} tweets, stopping...")
                                break
                        else:
                            print(f"Tweet {i+1}: Duplicate detected, skipping...")
                    
                    except Exception as e:
                        print(f"Error processing tweet {i+1}: {e}")
                        continue

                print(f"Processed {processed_count} new tweets in this iteration")
                
                # Break if we have enough tweets
                if len(tweets_data) >= limit:
                    break

                # Scroll down
                print("Scrolling down...")
                driver.execute_script("window.scrollBy(0, 2000);")
                time.sleep(scroll_pause_time)

                # Update heights
                new_height = driver.execute_script("return document.body.scrollHeight")
                print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

                # Check if scrolling is stuck (same logic as timeline)
                if new_height == last_height:
                    print("Scrolling stuck, trying recovery methods...")
                    time.sleep(scroll_pause_time * 2)
                    new_height = driver.execute_script("return document.body.scrollHeight")

                    if new_height == last_height:
                        print("Still stuck, trying aggressive scroll...")
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(scroll_pause_time * 2)
                        new_height = driver.execute_script("return document.body.scrollHeight")

                        if new_height == last_height:
                            print("Scrolling completely stuck.")
                            if len(tweets_data) > 0:
                                print(f"We have {len(tweets_data)} tweets, continuing with those.")
                                break
                            else:
                                print("No tweets collected and scrolling stuck. Exiting...")
                                break

                last_height = new_height
                scroll_count += 1

                # Save state periodically
                if scroll_count % 5 == 0:
                    save_state()

            except WebDriverException as e:
                print(f"WebDriver error during scraping: {e}")
                break
            except Exception as e:
                print(f"Unexpected error during scraping: {e}")
                break

        # Final save
        save_state()

        # Close the browser
