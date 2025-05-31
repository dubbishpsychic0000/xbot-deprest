import time
import pandas as pd
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
import pickle
import os.path
import json
import hashlib
from datetime import datetime

# Twitter login credentials
username_str = "your_tw_username"
password_str = "your_pw"

# Set up Chrome options
options = Options()
options.add_argument("--start-maximized")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_argument("--headless")

# Initialize the Chrome WebDriver
service = Service(executable_path=CM().install())
driver = webdriver.Chrome(service=service, options=options)

# Open Twitter login page
url = "https://x.com/i/flow/login"
driver.get(url)

try:
    # Wait for the username input and enter the username
    username = WebDriverWait(driver, 60).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]')))
    username.send_keys(username_str)
    username.send_keys(Keys.RETURN)

    # Wait for the password input and enter the password
    password = WebDriverWait(driver, 60).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]')))
    password.send_keys(password_str)
    password.send_keys(Keys.RETURN)

    # Wait for the profile page to load after login
    time.sleep(25)

    # Open the Twitter profile page
    driver.get("https://x.com/home")

    # Wait for the page to load
    time.sleep(25)
except TimeoutException:
    print("Loading took too much time!")
    driver.quit()
    exit()

# Scroll the page to load more tweets
scroll_pause_time = 15
new_height = 0
last_height = driver.execute_script("return window.pageYOffset;")
scrolling = True
# Initialize scrolling variables
scroll_count = 0
tweets_collected = set()  # Use a set to avoid duplicates
tweets_data = []  # List to store tweet data

# Load previous state from pickle file if exists
scroll_state_file = "scroll_state.pkl"
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

# Function to save current state to pickle file
def save_state():
    with open(scroll_state_file, "wb") as f:
        pickle.dump((scroll_count, last_height, tweets_collected, tweets_data), f)

def extract_tweet_id_from_url(url):
    """Extract tweet ID from Twitter URL"""
    try:
        if '/status/' in url:
            return url.split('/status/')[-1].split('?')[0]
        return None
    except:
        return None

def generate_tweet_id(tweet_text, timestamp):
    """Generate a unique ID for tweets without URLs"""
    content = f"{tweet_text}_{timestamp}"
    return hashlib.md5(content.encode()).hexdigest()[:16]

while True:  # Infinite loop for continuous scrolling
    try:
        tweets = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')

        for tweet in tweets:
            try:
                tweet_text = tweet.find_element(By.CSS_SELECTOR, 'div[lang]').text
            except NoSuchElementException:
                tweet_text = ""
                print("No tweet text found")

            # Extract timestamp and convert to ISO format
            try:
                timestamp_element = tweet.find_element(By.TAG_NAME, "time")
                timestamp = timestamp_element.get_attribute("datetime")
                created_at = parse(timestamp).isoformat()
                tweet_date = parse(timestamp).isoformat().split("T")[0]
            except Exception as ex:
                created_at = datetime.now().isoformat()
                tweet_date = datetime.now().date().isoformat()
                print(f"Error parsing date: {ex}")

            # Extract tweet URL to get ID
            try:
                tweet_link = tweet.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
                tweet_url = tweet_link.get_attribute("href")
                tweet_id = extract_tweet_id_from_url(tweet_url)
            except:
                tweet_id = generate_tweet_id(tweet_text, created_at)
                tweet_url = f"https://twitter.com/user/status/{tweet_id}"

            # Extract external links
            try:
                anchor = tweet.find_element(By.CSS_SELECTOR, "a[aria-label][dir]")
                external_link = anchor.get_attribute("href")
            except Exception as ex:
                external_link = ""

            # Extract images
            try:
                images = tweet.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
                tweet_images = [img.get_attribute("src") for img in images]
            except Exception as ex:
                tweet_images = []

            # Extract username/author
            try:
                username_element = tweet.find_element(By.CSS_SELECTOR, 'div[data-testid="User-Name"] span')
                author = username_element.text.replace('@', '')
            except:
                author = "unknown"

            # Extract engagement metrics
            try:
                like_count = 0
                retweet_count = 0
                reply_count = 0
                
                # Try to extract metrics (these selectors might need adjustment)
                metrics_elements = tweet.find_elements(By.CSS_SELECTOR, '[data-testid*="count"] span')
                for element in metrics_elements:
                    try:
                        count_text = element.text
                        if count_text and count_text.isdigit():
                            # This is a simplified approach - you might need more specific selectors
                            pass
                    except:
                        pass
            except:
                like_count = retweet_count = reply_count = 0

            # Create tweet data structure matching twscraper format
            tweet_data = {
                "id": tweet_id,
                "url": tweet_url,
                "date": tweet_date,
                "created_at": created_at,
                "content": tweet_text,
                "user": {
                    "username": author,
                    "displayname": author,  # Simplified - you might want to extract actual display name
                },
                "outlinks": [external_link] if external_link else [],
                "tcooutlinks": [],  # Twitter's t.co links - would need additional processing
                "media": [{"url": img} for img in tweet_images] if tweet_images else [],
                "retweetedTweet": None,  # Would need additional logic to detect retweets
                "quotedTweet": None,    # Would need additional logic to detect quotes
                "mentionedUsers": [],   # Would need regex to extract @mentions
                "hashtags": [],         # Would need regex to extract #hashtags
                "cashtags": [],         # Would need regex to extract $cashtags
                "card": None,           # Twitter cards - would need additional extraction
                "conversationId": tweet_id,  # Simplified
                "lang": "en",           # Would need language detection
                "source": None,         # Tweet source app
                "replyCount": reply_count,
                "retweetCount": retweet_count,
                "likeCount": like_count,
                "quoteCount": 0,        # Would need additional extraction
                "bookmarkCount": 0,     # Not usually available
                "viewCount": None,      # Not usually available
            }

            # Create a unique identifier for deduplication
            tweet_signature = (tweet_data["id"], tweet_data["content"], tweet_data["created_at"])
            
            if tweet_signature not in tweets_collected:
                tweets_collected.add(tweet_signature)
                tweets_data.append(tweet_data)
                print(f"Collected tweet {tweet_id}: {tweet_text[:50]}...")

        # Scroll down
        driver.execute_script("window.scrollBy(0, 3000);")
        time.sleep(scroll_pause_time)

        # Update heights
        new_height = driver.execute_script("return document.body.scrollHeight")
        print(f"Scroll count: {scroll_count}, New height: {new_height}, Last height: {last_height}")

        # Check if scrolling is stuck
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

        # Save state periodically
        if scroll_count % 10 == 0:  # Adjust frequency of state saving as needed
            save_state()

    except WebDriverException as e:
        print(f"An error occurred during scraping: {e}")
        break

# Close the browser
driver.quit()

# Save data in multiple formats to match twscraper output
# 1. JSON format (primary output)
with open("tweets_data.json", "w", encoding="utf-8") as f:
    json.dump(tweets_data, f, indent=2, ensure_ascii=False, default=str)

# 2. JSONL format (one JSON object per line)
with open("tweets_data.jsonl", "w", encoding="utf-8") as f:
    for tweet in tweets_data:
        f.write(json.dumps(tweet, ensure_ascii=False, default=str) + "\n")

# 3. CSV format for backwards compatibility
csv_data = []
for tweet in tweets_data:
    csv_row = {
        "id": tweet["id"],
        "url": tweet["url"],
        "date": tweet["date"],
        "content": tweet["content"],
        "username": tweet["user"]["username"],
        "displayname": tweet["user"]["displayname"],
        "replyCount": tweet["replyCount"],
        "retweetCount": tweet["retweetCount"],
        "likeCount": tweet["likeCount"],
        "media_urls": ", ".join([m["url"] for m in tweet["media"]]) if tweet["media"] else "",
        "outlinks": ", ".join(tweet["outlinks"]) if tweet["outlinks"] else "",
        "hashtags": ", ".join(tweet["hashtags"]) if tweet["hashtags"] else "",
        "mentions": ", ".join(tweet["mentionedUsers"]) if tweet["mentionedUsers"] else "",
    }
    csv_data.append(csv_row)

df = pd.DataFrame(csv_data)
df.to_csv("tweets_data.csv", index=False, encoding="utf-8")

# Legacy Excel format
df_legacy = pd.DataFrame([
    {
        "Tweet": tweet["content"],
        "Date": tweet["date"], 
        "Link": tweet["url"],
        "Images": ", ".join([m["url"] for m in tweet["media"]]) if tweet["media"] else "No Images"
    } 
    for tweet in tweets_data
])
df_legacy.to_excel("tweets2.xlsx", index=False)

# Print summary
print(f"Total tweets collected: {len(tweets_data)}")
print(f"Data saved to:")
print(f"  - tweets_data.json (structured JSON)")
print(f"  - tweets_data.jsonl (line-delimited JSON)")
print(f"  - tweets_data.csv (CSV format)")  
print(f"  - tweets2.xlsx (legacy Excel format)")

# Delete the scroll state file after successful scraping
if os.path.exists(scroll_state_file):
    os.remove(scroll_state_file)

print("Script execution completed.")
