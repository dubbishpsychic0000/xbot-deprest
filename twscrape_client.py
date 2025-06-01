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
from dotenv import load_dotenv

load_dotenv()

# Fetch credentials from .env
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")

def setup_driver() -> webdriver.Chrome:
    """Initialize and return a Chrome WebDriver."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--headless")  # Remove this line if you want to see the browser
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    service = Service(executable_path=CM().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def login(driver: webdriver.Chrome) -> bool:
    """Log in to Twitter (x.com) with the given WebDriver. Returns True on success."""
    try:
        driver.get("https://x.com/i/flow/login")

        # Wait for the username input
        username_inp = WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
        )
        username_inp.send_keys(TWITTER_USERNAME)
        username_inp.send_keys(Keys.RETURN)

        # Wait for the password input
        password_inp = WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
        )
        password_inp.send_keys(TWITTER_PASSWORD)
        password_inp.send_keys(Keys.RETURN)

        # Wait for login to complete
        time.sleep(25)
        return True

    except Exception as e:
        print(f"[!] Login failed: {e}")
        return False

def extract_tweet_data(tweet_element) -> Optional[Dict]:
    """
    Extract tweet data from a Selenium WebElement and return in bot-compatible format.
    Returns dict with keys: id, text, url, created_at, author, media
    """
    try:
        # Tweet text
        try:
            tweet_text = tweet_element.find_element(By.CSS_SELECTOR, 'div[lang]').text
        except NoSuchElementException:
            tweet_text = ""

        # Timestamp → created_at (ISO format)
        try:
            timestamp_elem = tweet_element.find_element(By.TAG_NAME, "time")
            timestamp_str = timestamp_elem.get_attribute("datetime")
            created_at = parse(timestamp_str).isoformat()
        except Exception:
            created_at = datetime.now().isoformat()

        # Tweet URL and ID
        try:
            link_elem = tweet_element.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
            tweet_url = link_elem.get_attribute("href")
            tweet_id = tweet_url.split("/status/")[-1].split("?")[0]
        except Exception:
            # Fallback: hash text+date for unique ID
            fallback_hash = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            tweet_url = f"https://x.com/status/{fallback_hash}"

        # Author username (without '@')
        try:
            # Try multiple selectors for author
            author_selectors = [
                'div[data-testid="User-Name"] span',
                'div[data-testid="User-Name"] a span',
                '[data-testid="User-Name"] span'
            ]
            author = "unknown"
            for selector in author_selectors:
                try:
                    usr_elem = tweet_element.find_element(By.CSS_SELECTOR, selector)
                    author_text = usr_elem.text
                    if author_text and not author_text.startswith("@"):
                        # Find the username (usually has @)
                        usr_elems = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="User-Name"] span')
                        for elem in usr_elems:
                            if elem.text.startswith("@"):
                                author = elem.text.replace("@", "")
                                break
                    elif author_text.startswith("@"):
                        author = author_text.replace("@", "")
                    break
                except:
                    continue
        except Exception:
            author = "unknown"

        # Images/Media
        try:
            imgs = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
            media = [img.get_attribute("src") for img in imgs if img.get_attribute("src")]
        except Exception:
            media = []

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
        print(f"[!] Failed to extract tweet data: {e}")
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
    return scrape_timeline_tweets(limit) if source_type == "timeline" else []

def scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """
    Scrape tweets from the Twitter home timeline.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    
    # State management files
    scroll_state_file = "timeline_scroll_state.pkl"
    
    driver = setup_driver()
    
    try:
        # 1) Log in first
        if not login(driver):
            print("Login failed!")
            driver.quit()
            return []

        # 2) Navigate to home timeline
        driver.get("https://x.com/home")
        time.sleep(25)  # Wait for timeline to load

        # Load previous state if exists
        scroll_count = 0
        last_height = 0
        tweets_collected = set()
        tweets_data = []

        if os.path.exists(scroll_state_file):
            try:
                with open(scroll_state_file, "rb") as f:
                    scroll_count, last_height, tweets_collected, tweets_data = pickle.load(f)
                    print(f"Resumed from previous state. Already collected: {len(tweets_data)} tweets")
            except Exception as e:
                print(f"Error loading state: {e}. Starting fresh.")

        def save_state():
            """Save current scraping state"""
            with open(scroll_state_file, "wb") as f:
                pickle.dump((scroll_count, last_height, tweets_collected, tweets_data), f)

        # 3) Scroll and collect tweets
        scroll_pause_time = 15
        max_scrolls = max(10, limit // 3)  # Estimate scrolls needed
        
        while len(tweets_data) < limit and scroll_count < max_scrolls:
            try:
                # Find all tweet elements on current page
                tweet_elements = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
                
                for tweet_element in tweet_elements:
                    if len(tweets_data) >= limit:
                        break
                    
                    # Extract tweet data
                    tweet_data = extract_tweet_data(tweet_element)
                    if not tweet_data:
                        continue
                    
                    # Check for duplicates using tweet ID
                    tweet_id = tweet_data["id"]
                    if tweet_id not in tweets_collected:
                        tweets_collected.add(tweet_id)
                        tweets_data.append(tweet_data)
                        
                        print(f"Collected tweet {len(tweets_data)}/{limit}: @{tweet_data['author']} - {tweet_data['text'][:50]}...")

                # Break if we have enough tweets
                if len(tweets_data) >= limit:
                    break

                # Scroll down
                driver.execute_script("window.scrollBy(0, 3000);")
                time.sleep(scroll_pause_time)

                # Check scroll progress
                new_height = driver.execute_script("return document.body.scrollHeight")
                print(f"Scroll {scroll_count + 1}: Height {new_height}, Collected: {len(tweets_data)}")

                # Handle stuck scrolling
                if new_height == last_height:
                    print("Scrolling stuck, waiting...")
                    time.sleep(scroll_pause_time * 2)
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    
                    if new_height == last_height:
                        print("Still stuck, trying to scroll to bottom...")
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(scroll_pause_time * 2)
                        new_height = driver.execute_script("return document.body.scrollHeight")
                        
                        if new_height == last_height:
                            print("Scrolling completely stuck, breaking...")
                            break

                last_height = new_height
                scroll_count += 1

                # Save state periodically
                if scroll_count % 5 == 0:
                    save_state()

            except WebDriverException as e:
                print(f"Web driver error during scraping: {e}")
                break
            except Exception as e:
                print(f"Error during scraping: {e}")
                continue

        # Final save and cleanup
        save_state()
        
        # Clean up state file if we got enough tweets
        if len(tweets_data) >= limit and os.path.exists(scroll_state_file):
            os.remove(scroll_state_file)
            print("Scraping completed successfully, cleaned up state file.")

        driver.quit()
        
        print(f"Total tweets collected: {len(tweets_data)}")
        return tweets_data[:limit]

    except Exception as e:
        print(f"Error in scrape_timeline_tweets: {e}")
        driver.quit()
        return []

def save_tweets_to_files(tweets_data: List[Dict], filename_base: str = "timeline_tweets"):
    """Save tweets to both JSON and Excel formats"""
    if not tweets_data:
        print("No tweets to save!")
        return
    
    # Save as JSON (bot-compatible format)
    json_filename = f"{filename_base}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(tweets_data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(tweets_data)} tweets to {json_filename}")
    
    # Save as Excel (for human review)
    try:
        import pandas as pd
        
        # Flatten the data for Excel
        excel_data = []
        for tweet in tweets_data:
            excel_data.append({
                "ID": tweet["id"],
                "Author": tweet["author"],
                "Text": tweet["text"],
                "Created_At": tweet["created_at"],
                "URL": tweet["url"],
                "Media": ", ".join(tweet["media"]) if tweet["media"] else "No Media"
            })
        
        df = pd.DataFrame(excel_data)
        excel_filename = f"{filename_base}.xlsx"
        df.to_excel(excel_filename, index=False)
        print(f"Saved {len(tweets_data)} tweets to {excel_filename}")
        
    except ImportError:
        print("pandas not available, skipping Excel export")

if __name__ == "__main__":
    # Example usage - scrape timeline tweets
    print("Starting Twitter timeline scraping...")
    
    # Scrape tweets from timeline
    tweets = scrape_timeline_tweets(limit=10)  # Adjust limit as needed
    
    if tweets:
        # Save to files
        save_tweets_to_files(tweets, "timeline_tweets")
        
        # Display sample
        print(f"\nSample of collected tweets:")
        for i, tweet in enumerate(tweets[:3]):  # Show first 3
            print(f"\n--- Tweet {i+1} ---")
            print(f"ID: {tweet['id']}")
            print(f"Author: @{tweet['author']}")
            print(f"Text: {tweet['text'][:100]}...")
            print(f"Created: {tweet['created_at']}")
            print(f"URL: {tweet['url']}")
            if tweet['media']:
                print(f"Media: {len(tweet['media'])} items")
    else:
        print("No tweets collected!")
