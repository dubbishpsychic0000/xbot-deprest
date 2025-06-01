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
    """Initialize and return a Chrome WebDriver with enhanced options and proper instance management."""
    import tempfile
    import uuid
    import shutil
    
    # Create unique temporary directory for this Chrome instance
    temp_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{uuid.uuid4().hex[:8]}_")
    
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
    
    # Fix the user data directory issue
    options.add_argument(f"--user-data-dir={temp_dir}")
    options.add_argument("--profile-directory=Default")
    
    # Additional arguments to prevent crashes and conflicts
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--single-process")  # Use single process to avoid conflicts
    
    # Enable headless mode for server environments
    options.add_argument("--headless")
    options.add_argument("--disable-extensions")
    
    # Disable images for faster loading but keep notifications enabled
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0
    }
    options.add_experimental_option("prefs", prefs)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"Initializing Chrome driver (attempt {attempt + 1}/{max_attempts})...")
            service = Service(executable_path=CM().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Execute script to hide automation indicators
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Store temp directory for cleanup
            driver._temp_profile_dir = temp_dir
            
            print("Chrome driver initialized successfully")
            return driver
            
        except Exception as e:
            print(f"Chrome driver initialization attempt {attempt + 1} failed: {e}")
            
            # Clean up temp directory if driver creation failed
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
                
            if attempt < max_attempts - 1:
                # Create new temp directory for next attempt
                temp_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{uuid.uuid4().hex[:8]}_")
                options.arguments = [arg for arg in options.arguments if not arg.startswith("--user-data-dir=")]
                options.add_argument(f"--user-data-dir={temp_dir}")
                time.sleep(2)
            else:
                raise Exception(f"Failed to initialize Chrome driver after {max_attempts} attempts: {e}")

def login(driver: webdriver.Chrome) -> bool:
    """Log in to Twitter (x.com) with enhanced error handling and multiple retry attempts."""
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        print("Twitter credentials not found in environment variables")
        return False
        
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"Login attempt {attempt + 1}/{max_attempts}...")
            driver.get("https://x.com/i/flow/login")
            time.sleep(10)  # Increased wait time
            
            # Wait for and find username input with multiple selectors
            username_selectors = [
                'input[autocomplete="username"]',
                'input[name="text"]',
                'input[data-testid="ocfEnterTextTextInput"]'
            ]
            
            username_inp = None
            for selector in username_selectors:
                try:
                    username_inp = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"Found username input with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not username_inp:
                print("Could not find username input field")
                continue
                
            # Clear and enter username with retry logic
            for i in range(3):
                try:
                    username_inp.clear()
                    time.sleep(1)
                    username_inp.send_keys(TWITTER_USERNAME)
                    time.sleep(2)
                    username_inp.send_keys(Keys.RETURN)
                    print("Username entered successfully")
                    break
                except Exception as e:
                    print(f"Username entry attempt {i+1} failed: {e}")
                    time.sleep(2)
            
            time.sleep(8)  # Increased wait time
            
            # Wait for and find password input with multiple selectors
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input[data-testid="ocfEnterTextTextInput"]'
            ]
            
            password_inp = None
            for selector in password_selectors:
                try:
                    password_inp = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"Found password input with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not password_inp:
                print("Could not find password input field")
                continue
                
            # Clear and enter password with retry logic
            for i in range(3):
                try:
                    password_inp.clear()
                    time.sleep(1)
                    password_inp.send_keys(TWITTER_PASSWORD)
                    time.sleep(2)
                    password_inp.send_keys(Keys.RETURN)
                    print("Password entered successfully")
                    break
                except Exception as e:
                    print(f"Password entry attempt {i+1} failed: {e}")
                    time.sleep(2)

            # Wait for login completion with extended timeout
            print("Waiting for login to complete...")
            time.sleep(15)
            
            # Check for successful login with multiple indicators
            try:
                WebDriverWait(driver, 60).until(
                    lambda d: any(keyword in d.current_url.lower() for keyword in ["home", "twitter.com", "x.com"]) 
                             and "login" not in d.current_url.lower()
                )
                print("Login successful!")
                return True
            except TimeoutException:
                current_url = driver.current_url
                print(f"Login verification timeout. Current URL: {current_url}")
                
                # Check if we're actually logged in despite timeout
                if "login" not in current_url.lower() and any(keyword in current_url.lower() for keyword in ["home", "twitter.com", "x.com"]):
                    print("Login appears successful based on URL")
                    return True
                    
                print(f"Login attempt {attempt + 1} failed, retrying...")
                time.sleep(5)

        except Exception as e:
            print(f"Login attempt {attempt + 1} failed with error: {e}")
            time.sleep(5)
    
    print("All login attempts failed")
    return False

def extract_tweet_data_original_format(tweet_element) -> Optional[Tuple[str, str, str, str]]:
    """
    Extract tweet data from a Selenium WebElement with enhanced selectors.
    Returns tuple: (tweet_text, tweet_date, external_link, images_links)
    """
    try:
        # Extract tweet text with multiple selectors
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

        # Extract timestamp with improved parsing
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

        # Extract external link with better selectors
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

        # Extract images with enhanced selectors
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

        # Extract author username with better selectors
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
    Uses improved scrolling mechanics from the original script.
    """
    # State management
    state_file = f"{page_type}_scroll_state.pkl" if not username else f"user_{username}_scroll_state.pkl"
    
    # Initialize variables (matching original script structure)
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

    # Improved scrolling parameters (from original script)
    scroll_pause_time = 15  # Match original script timing
    
    # Tweet selectors
    tweet_selectors = [
        'article[data-testid="tweet"]',
        'div[data-testid="tweet"]',
        'article[role="article"]'
    ]

    print(f"Starting to scrape {page_type} tweets...")

    # Infinite scrolling loop (matching original script logic)
    while len(tweets_data) < limit:
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
                except Exception:
                    continue
            
            if not tweets:
                print("No tweets found, scrolling to load more...")
                driver.execute_script("window.scrollBy(0, 3000);")  # Match original scroll distance
                time.sleep(scroll_pause_time)
                continue

            # Process tweets
            processed_count = 0
            for i, tweet in enumerate(tweets):
                if len(tweets_data) >= limit:
                    break
                    
                try:
                    # Extract data in original format
                    original_data = extract_tweet_data_original_format(tweet)
                    if not original_data:
                        continue
                    
                    tweet_text, tweet_date, external_link, images_links = original_data

                    # Skip empty tweets
                    if not tweet_text.strip() and images_links == "No Images":
                        continue

                    # Check for duplicates (matching original script logic)
                    tweet_signature = (tweet_text, tweet_date, external_link, images_links)
                    if tweet_signature in tweets_collected:
                        continue
                    
                    tweets_collected.add(tweet_signature)
                    
                    # Convert to bot format
                    bot_format_data = extract_tweet_data_bot_format(tweet)
                    if bot_format_data:
                        tweets_data.append(bot_format_data)
                        processed_count += 1
                        
                        # Print progress (matching original script format)
                        print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")
                
                except Exception as e:
                    print(f"Error processing tweet {i+1}: {e}")
                    continue

            print(f"Processed {processed_count} new tweets")
            
            if len(tweets_data) >= limit:
                print(f"Reached limit of {limit} tweets")
                break

            # Enhanced scrolling logic (from original script)
            driver.execute_script("window.scrollBy(0, 3000);")
            time.sleep(scroll_pause_time)

            # Update heights
            new_height = driver.execute_script("return document.body.scrollHeight")
            print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

            # Check if scrolling is stuck (matching original script logic)
            if new_height == last_height:
                print("Scrolling stuck, waiting...")
                time.sleep(scroll_pause_time * 2)  # Wait longer to see if page loads
                new_height = driver.execute_script("return document.body.scrollHeight")

                if new_height == last_height:
                    print("Scrolling still stuck, attempting to break...")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause_time * 4)  # Wait and attempt to scroll down again
                    new_height = driver.execute_script("return document.body.scrollHeight")

                    if new_height == last_height:
                        print("Scrolling broken, exiting...")
                        break

            last_height = new_height
            scroll_count += 1

            # Save state periodically (matching original script frequency)
            if scroll_count % 10 == 0:
                save_state()

        except WebDriverException as e:
            print(f"WebDriver error during scraping: {e}")
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
    """
    Scrape tweets from the Twitter home timeline.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    driver = None
    try:
        driver = setup_driver()
        
        # Login with enhanced retry logic
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to home timeline
        print("Navigating to home timeline...")
        driver.get("https://x.com/home")
        
        # Wait for timeline to load with extended timeout
        try:
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            print("Timeline loaded successfully!")
        except TimeoutException:
            print("Timeline loading timeout - continuing anyway")
        
        time.sleep(25)  # Match original script timing

        # Use common scraping logic
        tweets_data = _scrape_tweets_common(driver, limit, "timeline")

        # Save to Excel file for compatibility (matching original script format)
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
        if driver:
            try:
                # Clean up temporary profile directory
                temp_dir = getattr(driver, '_temp_profile_dir', None)
                driver.quit()
                
                if temp_dir:
                    import shutil
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        print("Cleaned up temporary Chrome profile")
                    except:
                        pass
            except Exception as e:
                print(f"Error during driver cleanup: {e}")

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
    
    driver = None
    try:
        driver = setup_driver()
        
        # Login with enhanced retry logic
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to user profile
        profile_url = f"https://x.com/{username}"
        print(f"Navigating to user profile: {profile_url}")
        driver.get(profile_url)
        
        # Wait for profile to load with extended timeout
        try:
            WebDriverWait(driver, 60).until(
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
        
        time.sleep(25)  # Match original script timing

        # Use common scraping logic
        tweets_data = _scrape_tweets_common(driver, limit, "user", username)

        # Save to Excel file (matching original script format)
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
        if driver:
            try:
                # Clean up temporary profile directory
                temp_dir = getattr(driver, '_temp_profile_dir', None)
                driver.quit()
                
                if temp_dir:
                    import shutil
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        print("Cleaned up temporary Chrome profile")
                    except:
                        pass
            except Exception as e:
                print(f"Error during driver cleanup: {e}")
        print("Script execution completed.")  # Match original script message
