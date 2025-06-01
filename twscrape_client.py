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

def extract_tweet_data_original_format(tweet_element) -> Optional[tuple]:
    """
    Extract tweet data from a Selenium WebElement and return in ORIGINAL format.
    Returns tuple: (tweet_text, tweet_date, external_link, images_links)
    """
    try:
        # Tweet text - exactly like the original
        try:
            tweet_text = tweet_element.find_element(By.CSS_SELECTOR, 'div[lang]').text
        except NoSuchElementException:
            tweet_text = ""
            print("No tweet text found")

        # Timestamp - exactly like the original
        try:
            timestamp = tweet_element.find_element(By.TAG_NAME, "time").get_attribute("datetime")
            tweet_date = parse(timestamp).isoformat().split("T")[0]
        except Exception as ex:
            tweet_date = ""
            print(f"Error parsing date: {ex}")

        # External link - exactly like the original
        try:
            anchor = tweet_element.find_element(By.CSS_SELECTOR, "a[aria-label][dir]")
            external_link = anchor.get_attribute("href")
        except Exception as ex:
            external_link = ""
            print(f"Error finding external link: {ex}")

        # Images - exactly like the original
        try:
            images = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
            tweet_images = [img.get_attribute("src") for img in images]
        except Exception as ex:
            tweet_images = []
            print(f"Error finding images: {ex}")

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
                created_at = f"{tweet_date}T00:00:00"  # Add time component
            else:
                created_at = datetime.now().isoformat()
        except Exception:
            created_at = datetime.now().isoformat()

        # Generate tweet URL and ID - try to get real URL first
        try:
            link_elem = tweet_element.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
            tweet_url = link_elem.get_attribute("href")
            tweet_id = tweet_url.split("/status/")[-1].split("?")[0]
        except Exception:
            # Fallback: hash text+date for unique ID
            fallback_hash = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            tweet_url = f"https://x.com/status/{fallback_hash}"

        # Extract author username
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
        except Exception:
            author = "unknown"

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
    Scrape tweets from the Twitter home timeline - MATCHES ORIGINAL SCRIPT EXACTLY.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    
    # State management files
    scroll_state_file = "scroll_state.pkl"
    
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

        # Initialize scrolling variables - EXACTLY like original
        scroll_count = 0
        tweets_collected = set()  # Use a set to avoid duplicates
        tweets_data = []  # List to store tweet data

        # Load previous state from pickle file if exists - EXACTLY like original
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

        # Function to save current state to pickle file - EXACTLY like original
        def save_state():
            with open(scroll_state_file, "wb") as f:
                pickle.dump((scroll_count, last_height, tweets_collected, tweets_data), f)

        # Scrolling variables - EXACTLY like original
        scroll_pause_time = 15
        new_height = 0

        # Main scrolling loop - EXACTLY like original logic
        while True:  # Infinite loop for continuous scrolling
            try:
                tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')

                for tweet in tweets:
                    # Extract in original format first
                    original_data = extract_tweet_data_original_format(tweet)
                    if not original_data:
                        continue
                    
                    tweet_text, tweet_date, external_link, images_links = original_data

                    # Check for duplicates using original format - EXACTLY like original
                    if (tweet_text, tweet_date, external_link, images_links) not in tweets_collected:
                        tweets_collected.add((tweet_text, tweet_date, external_link, images_links))
                        
                        # Convert to bot format for return
                        bot_format_data = extract_tweet_data_bot_format(tweet)
                        if bot_format_data:
                            tweets_data.append(bot_format_data)
                        
                        # Print in original format - EXACTLY like original
                        print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")
                        
                        # Stop if we have enough tweets
                        if len(tweets_data) >= limit:
                            print(f"Reached limit of {limit} tweets, stopping...")
                            break

                # Break if we have enough tweets
                if len(tweets_data) >= limit:
                    break

                # Scroll down - EXACTLY like original
                driver.execute_script("window.scrollBy(0, 3000);")
                time.sleep(scroll_pause_time)

                # Update heights - EXACTLY like original
                new_height = driver.execute_script("return document.body.scrollHeight")
                print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

                # Check if scrolling is stuck - EXACTLY like original
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

                # Save state periodically - EXACTLY like original
                if scroll_count % 10 == 0:  # Adjust frequency of state saving as needed
                    save_state()

            except WebDriverException as e:
                print(f"An error occurred during scraping: {e}")
                break

        # Final save
        save_state()

        # Close the browser - EXACTLY like original
        driver.quit()

        # Create Excel file in original format for compatibility
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

        # Print the total number of tweets collected - EXACTLY like original
        print(f"Total tweets collected: {len(tweets_data)}")

        # Delete the scroll state file after successful scraping - EXACTLY like original
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
    Scrape tweets from a specific user's profile.
    Returns a list of tweet dictionaries in bot-compatible format.
    """
    # Remove @ if present
    username = username.replace('@', '')
    
    # State management files
    scroll_state_file = f"user_{username}_scroll_state.pkl"
    
    driver = setup_driver()
    
    try:
        # 1) Log in first
        if not login(driver):
            print("Login failed!")
            driver.quit()
            return []

        # 2) Navigate to user profile - like your original script
        profile_url = f"https://x.com/{username}"
        driver.get(profile_url)
        time.sleep(25)  # Wait for profile to load

        # Initialize scrolling variables - EXACTLY like original
        scroll_count = 0
        tweets_collected = set()  # Use a set to avoid duplicates
        tweets_data = []  # List to store tweet data

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
        scroll_pause_time = 15
        new_height = 0

        # Main scrolling loop - same logic as timeline
        while True:  # Infinite loop for continuous scrolling
            try:
                tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')

                for tweet in tweets:
                    # Extract in original format first
                    original_data = extract_tweet_data_original_format(tweet)
                    if not original_data:
                        continue
                    
                    tweet_text, tweet_date, external_link, images_links = original_data

                    # Check for duplicates using original format
                    if (tweet_text, tweet_date, external_link, images_links) not in tweets_collected:
                        tweets_collected.add((tweet_text, tweet_date, external_link, images_links))
                        
                        # Convert to bot format for return
                        bot_format_data = extract_tweet_data_bot_format(tweet)
                        if bot_format_data:
                            tweets_data.append(bot_format_data)
                        
                        # Print in original format
                        print(f"Date: {tweet_date}, Tweet: {tweet_text}, Link: {external_link}, Images: {images_links}")
                        
                        # Stop if we have enough tweets
                        if len(tweets_data) >= limit:
                            print(f"Reached limit of {limit} tweets, stopping...")
                            break

                # Break if we have enough tweets
                if len(tweets_data) >= limit:
                    break

                # Scroll down
                driver.execute_script("window.scrollBy(0, 3000);")
                time.sleep(scroll_pause_time)

                # Update heights
                new_height = driver.execute_script("return document.body.scrollHeight")
                print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

                # Check if scrolling is stuck
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

        # Final save
        save_state()

        # Close the browser
        driver.quit()

        # Create Excel file in original format for compatibility
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
            df.to_excel(f"{username}_tweets.xlsx", index=False)
            print(f"Saved {len(original_format_data)} tweets to {username}_tweets.xlsx")
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
        print(f"Error in scrape_user_tweets: {e}")
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
    
    # Save as Excel (for human review) - in original format
    try:
        excel_data = []
        for tweet in tweets_data:
            excel_data.append({
                "Tweet": tweet.get("text", ""),
                "Date": tweet.get("created_at", "").split("T")[0],  # Extract date part
                "Link": tweet.get("url", ""),
                "Images": ", ".join(tweet.get("media", [])) if tweet.get("media") else "No Images"
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
                for j, media_url in enumerate(tweet['media']):
                    print(f"  Media {j+1}: {media_url}")
    else:
        print("No tweets collected!")
