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
    import tempfile
    import uuid
    import shutil
    
    # Create unique temporary directory for this Chrome instance
    temp_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{uuid.uuid4().hex[:8]}_")
    
    options = Options()
    
    # Enhanced anti-detection measures for 2025
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=VizDisplayCompositor")
    
    # Randomize window size
    window_sizes = ["1920,1080", "1366,768", "1536,864", "1440,900"]
    selected_size = random.choice(window_sizes)
    options.add_argument(f"--window-size={selected_size}")
    
    # Randomize user agent from 2025 browsers
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Profile settings
    options.add_argument(f"--user-data-dir={temp_dir}")
    options.add_argument("--profile-directory=Default")
    
    # Additional performance and stealth arguments
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--disable-plugins-discovery")
    options.add_argument("--disable-preconnect")
    
    # Memory and performance optimizations
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max_old_space_size=4096")
    
    # Comment out headless for debugging, uncomment for production
    # options.add_argument("--headless=new")
    
    # Enhanced preferences for 2025
    prefs = {
        "profile.managed_default_content_settings.images": 1,  # Enable images for better detection
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
        "profile.managed_default_content_settings.media_stream": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.managed_default_content_settings.geolocation": 2
    }
    options.add_experimental_option("prefs", prefs)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"Initializing Chrome driver (attempt {attempt + 1}/{max_attempts})...")
            service = Service(executable_path=CM().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # Enhanced stealth scripts for 2025
            stealth_scripts = [
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
                "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})",
                "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})",
                "Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})})",
                "window.chrome = {runtime: {}};",
                "Object.defineProperty(navigator, 'connection', {get: () => ({effectiveType: '4g'})});",
                "Object.defineProperty(screen, 'colorDepth', {get: () => 24});",
                "Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});"
            ]
            
            for script in stealth_scripts:
                try:
                    driver.execute_script(script)
                except:
                    continue
            
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
            
            # Navigate to login with random delay
            driver.get("https://x.com/i/flow/login")
            human_like_delay()
            time.sleep(random.uniform(8, 15))
            
            # Enhanced username input detection for 2025
            username_selectors = [
                'input[autocomplete="username"]',
                'input[name="text"]',
                'input[data-testid="ocfEnterTextTextInput"]',
                'input[placeholder*="username"]',
                'input[placeholder*="email"]',
                'input[placeholder*="phone"]',
                'input[type="text"]'
            ]
            
            username_inp = None
            for selector in username_selectors:
                try:
                    username_inp = WebDriverWait(driver, 25).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"Found username input with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not username_inp:
                print("Could not find username input field")
                continue
            
            # Human-like typing for username
            username_inp.click()
            human_like_delay()
            username_inp.clear()
            human_like_delay()
            
            # Type username character by character with random delays
            for char in TWITTER_USERNAME:
                username_inp.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            human_like_delay()
            username_inp.send_keys(Keys.RETURN)
            print("Username entered successfully")
            
            # Wait for password field with extended timeout
            time.sleep(random.uniform(5, 12))
            
            # Enhanced password input detection
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input[data-testid="ocfEnterTextTextInput"]',
                'input[placeholder*="password"]',
                'input[autocomplete="current-password"]'
            ]
            
            password_inp = None
            for selector in password_selectors:
                try:
                    password_inp = WebDriverWait(driver, 25).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    print(f"Found password input with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not password_inp:
                print("Could not find password input field")
                continue
            
            # Human-like typing for password
            password_inp.click()
            human_like_delay()
            password_inp.clear()
            human_like_delay()
            
            # Type password character by character
            for char in TWITTER_PASSWORD:
                password_inp.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            human_like_delay()
            password_inp.send_keys(Keys.RETURN)
            print("Password entered successfully")

            # Wait for login completion with extended timeout
            print("Waiting for login to complete...")
            time.sleep(random.uniform(10, 20))
            
            # Enhanced login verification
            success_indicators = [
                "home", "twitter.com", "x.com", "timeline"
            ]
            
            try:
                WebDriverWait(driver, 90).until(
                    lambda d: any(keyword in d.current_url.lower() for keyword in success_indicators) 
                             and "login" not in d.current_url.lower()
                             and "flow" not in d.current_url.lower()
                )
                print("Login successful!")
                return True
                
            except TimeoutException:
                current_url = driver.current_url
                print(f"Login verification timeout. Current URL: {current_url}")
                
                # Check if we're actually logged in
                if ("login" not in current_url.lower() and 
                    "flow" not in current_url.lower() and 
                    any(keyword in current_url.lower() for keyword in success_indicators)):
                    print("Login appears successful based on URL")
                    return True
                    
                print(f"Login attempt {attempt + 1} failed, retrying...")
                time.sleep(random.uniform(5, 10))

        except Exception as e:
            print(f"Login attempt {attempt + 1} failed with error: {e}")
            time.sleep(random.uniform(5, 10))
    
    print("All login attempts failed")
    return False

def extract_tweet_data_original_format(tweet_element) -> Optional[Tuple[str, str, str, str]]:
    """Enhanced tweet extraction for 2025 with updated selectors."""
    try:
        # Enhanced tweet text extraction with 2025 selectors
        tweet_text = ""
        text_selectors = [
            'div[data-testid="tweetText"]',
            'div[data-testid="tweetText"] span',
            'div[lang] span',
            'span[data-testid="tweetText"]',
            '.css-1jxf684',  # Updated CSS class
            '.css-146c3p1',  # Updated CSS class
            '[data-testid="tweetText"] > div',
            '[data-testid="tweetText"] > span'
        ]
        
        for selector in text_selectors:
            try:
                elements = tweet_element.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # Get all text from all matching elements
                    texts = [elem.text.strip() for elem in elements if elem.text.strip()]
                    if texts:
                        tweet_text = ' '.join(texts)
                        break
            except NoSuchElementException:
                continue

        # Enhanced timestamp extraction
        tweet_date = ""
        try:
            time_selectors = [
                "time[datetime]",
                "time",
                "a[href*='status'] time",
                "[data-testid='Time'] time"
            ]
            
            for selector in time_selectors:
                try:
                    time_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                    timestamp = time_elem.get_attribute("datetime")
                    if timestamp:
                        tweet_date = parse(timestamp).isoformat().split("T")[0]
                        break
                    else:
                        # Try title or text content
                        timestamp = time_elem.get_attribute("title") or time_elem.text
                        if timestamp:
                            try:
                                tweet_date = parse(timestamp).isoformat().split("T")[0]
                                break
                            except:
                                continue
                except NoSuchElementException:
                    continue
        except Exception:
            pass
        
        if not tweet_date:
            tweet_date = datetime.now().isoformat().split("T")[0]

        # Enhanced external link extraction
        external_link = ""
        link_selectors = [
            "a[href*='/status/']",
            "a[role='link'][href*='status']",
            "time[datetime] + a",
            "a[href*='/x.com/'][href*='/status/']",
            "a[href*='/twitter.com/'][href*='/status/']"
        ]
        
        for selector in link_selectors:
            try:
                if selector == "time[datetime] + a":
                    # Get sibling link of time element
                    time_elem = tweet_element.find_element(By.CSS_SELECTOR, "time[datetime]")
                    try:
                        parent_link = time_elem.find_element(By.XPATH, "./ancestor::a[@href]")
                        href = parent_link.get_attribute("href")
                    except:
                        continue
                else:
                    anchor = tweet_element.find_element(By.CSS_SELECTOR, selector)
                    href = anchor.get_attribute("href")
                
                if href and "/status/" in href:
                    external_link = href
                    break
            except NoSuchElementException:
                continue

        # Enhanced image extraction with 2025 selectors
        tweet_images = []
        image_selectors = [
            'div[data-testid="tweetPhoto"] img',
            'img[alt*="Image"]',
            'div[data-testid="card.layoutLarge.media"] img',
            'img[src*="pbs.twimg.com"]',
            'div[data-testid="tweet"] img[src*="twimg.com"]',
            '[role="img"] img',
            'div[aria-label*="Image"] img'
        ]
        
        for selector in image_selectors:
            try:
                images = tweet_element.find_elements(By.CSS_SELECTOR, selector)
                for img in images:
                    src = img.get_attribute("src")
                    if (src and 
                        ("pbs.twimg.com" in src or "twimg.com" in src) and 
                        src not in tweet_images and
                        "profile_images" not in src):  # Exclude profile images
                        tweet_images.append(src)
            except Exception:
                continue

        images_links = ', '.join(tweet_images) if tweet_images else "No Images"

        return (tweet_text, tweet_date, external_link, images_links)

    except Exception as e:
        print(f"Failed to extract tweet data: {e}")
        return None

def extract_tweet_data_bot_format(tweet_element) -> Optional[Dict]:
    """Extract tweet data and return in bot-compatible format with 2025 enhancements."""
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

        # Enhanced author extraction for 2025
        author = "unknown"
        author_selectors = [
            'div[data-testid="User-Name"] a span',
            'div[data-testid="User-Names"] span',
            '[data-testid="User-Name"] span',
            'a[role="link"] span',
            'div[data-testid="User-Name"] div span',
            'span[class*="username"]'
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
    """Enhanced common tweet scraping logic for 2025."""
    # State management
    state_file = f"{page_type}_scroll_state.pkl" if not username else f"user_{username}_scroll_state.pkl"
    
    # Initialize variables
    scroll_count = 0
    tweets_collected = set()
    tweets_data = []
    last_height = driver.execute_script("return window.pageYOffset;")
    consecutive_failures = 0
    max_consecutive_failures = 5

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

    # Enhanced tweet selectors for 2025
    tweet_selectors = [
        'article[data-testid="tweet"]',
        'div[data-testid="tweet"]',
        'article[role="article"]',
        'div[data-testid="cellInnerDiv"] article',
        '[data-testid="tweet"]'
    ]

    print(f"Starting to scrape {page_type} tweets...")

    # Enhanced scrolling loop with better failure handling
    while len(tweets_data) < limit and consecutive_failures < max_consecutive_failures:
        try:
            print(f"\n--- Scroll iteration {scroll_count + 1} ---")
            
            # Add random delay before processing
            human_like_delay()
            
            # Find tweets using enhanced selectors
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
                consecutive_failures += 1
                
                # More aggressive scrolling when no tweets found
                scroll_distances = [2000, 3000, 4000]
                for distance in scroll_distances:
                    driver.execute_script(f"window.scrollBy(0, {distance});")
                    time.sleep(random.uniform(2, 5))
                
                time.sleep(random.uniform(8, 15))
                continue
            
            # Reset failure counter when tweets are found
            consecutive_failures = 0

            # Process tweets with enhanced error handling
            processed_count = 0
            for i, tweet in enumerate(tweets):
                if len(tweets_data) >= limit:
                    break
                    
                try:
                    # Add small delay between processing tweets
                    if i % 5 == 0:
                        time.sleep(random.uniform(0.5, 1.5))
                    
                    # Extract data in original format
                    original_data = extract_tweet_data_original_format(tweet)
                    if not original_data:
                        continue
                    
                    tweet_text, tweet_date, external_link, images_links = original_data

                    # Skip empty tweets and ads/promoted content
                    if (not tweet_text.strip() and images_links == "No Images") or \
                       any(keyword in tweet_text.lower() for keyword in ["promoted", "ad", "sponsored"]):
                        continue

                    # Enhanced duplicate detection
                    tweet_signature = (tweet_text.strip(), tweet_date, external_link, images_links)
                    if tweet_signature in tweets_collected:
                        continue
                    
                    tweets_collected.add(tweet_signature)
                    
                    # Convert to bot format
                    bot_format_data = extract_tweet_data_bot_format(tweet)
                    if bot_format_data and bot_format_data.get('text', '').strip():
                        tweets_data.append(bot_format_data)
                        processed_count += 1
                        
                        # Print progress
                        print(f"Tweet {len(tweets_data)}: {tweet_text[:100]}...")
                
                except Exception as e:
                    print(f"Error processing tweet {i+1}: {e}")
                    continue

            print(f"Processed {processed_count} new tweets (Total: {len(tweets_data)})")
            
            if len(tweets_data) >= limit:
                print(f"Reached limit of {limit} tweets")
                break

            # Enhanced scrolling with randomization
            scroll_distance = random.randint(2500, 4000)
            driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
            
            # Random pause time to avoid detection
            pause_time = random.uniform(8, 18)
            time.sleep(pause_time)

            # Enhanced height tracking
            new_height = driver.execute_script("return document.body.scrollHeight")
            current_scroll = driver.execute_script("return window.pageYOffset;")
            print(f"Scroll: {scroll_count}, Height: {new_height}, Position: {current_scroll}")

            # Enhanced stuck detection
            if new_height == last_height:
                print("Scrolling appears stuck, implementing recovery...")
                
                # Try multiple recovery strategies
                recovery_strategies = [
                    lambda: driver.execute_script("window.scrollTo(0, document.body.scrollHeight);"),
                    lambda: driver.refresh(),
                    lambda: driver.execute_script("location.reload();")
                ]
                
                for strategy in recovery_strategies:
                    try:
                        strategy()
                        time.sleep(random.uniform(10, 20))
                        new_height_check = driver.execute_script("return document.body.scrollHeight")
                        if new_height_check != new_height:
                            new_height = new_height_check
                            break
                    except:
                        continue
                
                if new_height == last_height:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        print("Maximum consecutive failures reached, stopping...")
                        break

            last_height = new_height
            scroll_count += 1

            # Save state periodically
            if scroll_count % 8 == 0:
                save_state()

        except WebDriverException as e:
            print(f"WebDriver error during scraping: {e}")
            consecutive_failures += 1
            time.sleep(random.uniform(5, 10))
        except Exception as e:
            print(f"Unexpected error during scraping: {e}")
            consecutive_failures += 1
            time.sleep(random.uniform(3, 8))

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
    """Enhanced timeline scraping for 2025."""
    driver = None
    try:
        driver = setup_driver()
        
        # Login with enhanced retry logic
        print("Logging in to Twitter...")
        if not login(driver):
            print("Login failed!")
            return []

        # Navigate to home timeline with retry
        max_nav_attempts = 3
        for attempt in range(max_nav_attempts):
            try:
                print(f"Navigating to home timeline (attempt {attempt + 1})...")
                driver.get("https://x.com/home")
                human_like_delay()
                
                # Wait for timeline to load with multiple fallback strategies
                timeline_selectors = [
                    'article[data-testid="tweet"]',
                    'div[data-testid="tweet"]', 
                    '[data-testid="primaryColumn"]',
                    'main[role="main"]'
                ]
                
                timeline_loaded = False
                for selector in timeline_selectors:
                    try:
                        WebDriverWait(driver, 45).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        print(f"Timeline loaded successfully with selector: {selector}")
                        timeline_loaded = True
                        break
                    except TimeoutException:
                        continue
                
                if timeline_loaded:
                    break
                elif attempt == max_nav_attempts - 1:
                    print("Timeline loading failed, but continuing...")
                    
            except Exception as e:
                print(f"Navigation attempt {attempt + 1} failed: {e}")
                if attempt < max_nav_attempts - 1:
                    time.sleep(random.uniform(5, 10))
        
        # Additional wait for content to stabilize
        time.sleep(random.uniform(15, 25))

        # Use enhanced common scraping logic
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
    """Enhanced user tweet scraping for 2025."""
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

        # Navigate to user profile with retry mechanism
        max_nav_attempts = 3
        for attempt in range(max_nav_attempts):
            try:
                profile_url = f"https://x.com/{username}"
                print(f"Navigating to user profile: {profile_url} (attempt {attempt + 1})")
                driver.get(profile_url)
                human_like_delay()
                
                # Enhanced profile loading detection
                profile_indicators = [
                    'article[data-testid="tweet"]',
                    'div[data-testid="tweet"]',
                    '[data-testid="UserName"]',
                    '[data-testid="primaryColumn"]',
                    'div[data-testid="emptyState"]'  # For accounts with no tweets
                ]
                
                profile_loaded = False
                for selector in profile_indicators:
                    try:
                        WebDriverWait(driver, 45).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        print(f"Profile loaded successfully with indicator: {selector}")
                        profile_loaded = True
                        break
                    except TimeoutException:
                        continue
                
                # Check for account issues
                error_indicators = [
                    "this account doesn't exist",
                    "account suspended", 
                    "user not found",
                    "something went wrong",
                    "doesn't exist"
                ]
                
                page_content = driver.page_source.lower()
                for error in error_indicators:
                    if error in page_content:
                        print(f"Account issue detected: {error}")
                        return []
                
                if profile_loaded or attempt == max_nav_attempts - 1:
                    break
                    
            except Exception as e:
                print(f"Profile navigation attempt {attempt + 1} failed: {e}")
                if attempt < max_nav_attempts - 1:
                    time.sleep(random.uniform(5, 10))
        
        # Additional wait for profile content to stabilize
        time.sleep(random.uniform(15, 25))

        # Use enhanced common scraping logic
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
        print("Script execution completed.")

# Additional utility functions for better reliability

def check_rate_limit(driver: webdriver.Chrome) -> bool:
    """Check if we've hit Twitter's rate limit."""
    try:
        rate_limit_indicators = [
            "rate limit exceeded",
            "too many requests",
            "try again later",
            "temporarily restricted"
        ]
        
        page_content = driver.page_source.lower()
        for indicator in rate_limit_indicators:
            if indicator in page_content:
                print(f"Rate limit detected: {indicator}")
                return True
        return False
    except:
        return False

def handle_popup_dialogs(driver: webdriver.Chrome):
    """Handle various popup dialogs that might appear."""
    try:
        popup_selectors = [
            '[data-testid="confirmationSheetDialog"]',
            '[role="dialog"]',
            '[data-testid="modal"]',
            'div[aria-modal="true"]'
        ]
        
        for selector in popup_selectors:
            try:
                popup = driver.find_element(By.CSS_SELECTOR, selector)
                if popup.is_displayed():
                    # Try to find and click close button
                    close_selectors = [
                        '[data-testid="confirmationSheetCancel"]',
                        '[aria-label="Close"]',
                        'button[aria-label*="close"]',
                        'button[aria-label*="Close"]'
                    ]
                    
                    for close_selector in close_selectors:
                        try:
                            close_btn = popup.find_element(By.CSS_SELECTOR, close_selector)
                            close_btn.click()
                            print("Closed popup dialog")
                            time.sleep(1)
                            return
                        except:
                            continue
            except:
                continue
    except:
        pass

def wait_for_stable_page(driver: webdriver.Chrome, timeout: int = 30):
    """Wait for page to become stable (no major DOM changes)."""
    try:
        start_time = time.time()
        last_height = driver.execute_script("return document.body.scrollHeight")
        stable_count = 0
        
        while time.time() - start_time < timeout:
            time.sleep(2)
            current_height = driver.execute_script("return document.body.scrollHeight")
            
            if current_height == last_height:
                stable_count += 1
                if stable_count >= 3:  # Page stable for 6 seconds
                    print("Page appears stable")
                    return True
            else:
                stable_count = 0
            
            last_height = current_height
        
        print("Page stability timeout")
        return False
    except:
        return False
