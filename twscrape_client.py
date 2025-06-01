import time
import os
import hashlib
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
from dotenv import load_dotenv

load_dotenv()

# Fetch credentials from .env
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")

def setup_driver() -> webdriver.Chrome:
    """Initialize and return a headless Chrome WebDriver."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    service = Service(executable_path=CM().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def login(driver: webdriver.Chrome) -> bool:
    """Log in to Twitter (x.com) with the given WebDriver. Returns True on success."""
    try:
        driver.get("https://x.com/i/flow/login")

        # Wait for the username input
        username_inp = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
        )
        username_inp.send_keys(TWITTER_USERNAME)
        username_inp.send_keys(Keys.RETURN)

        # Wait for the password input
        password_inp = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
        )
        password_inp.send_keys(TWITTER_PASSWORD)
        password_inp.send_keys(Keys.RETURN)

        # Give it a short moment to complete login
        time.sleep(5)
        return True

    except Exception as e:
        print(f"[!] Login failed: {e}")
        return False

def extract_tweet_data(tweet_element) -> Optional[Dict]:
    """
    Given a Selenium WebElement corresponding to a single tweet ("article[data-testid='tweet']"),
    extract its text, timestamp, URL, author, and media. Return a dict or None on failure.
    """
    try:
        # Tweet text
        try:
            tweet_text = tweet_element.find_element(By.CSS_SELECTOR, 'div[lang]').text
        except NoSuchElementException:
            tweet_text = ""

        # Timestamp → created_at
        try:
            timestamp_elem = tweet_element.find_element(By.TAG_NAME, "time")
            timestamp_str = timestamp_elem.get_attribute("datetime")
            created_at = parse(timestamp_str).isoformat()
        except Exception:
            created_at = parse(datetime.now().isoformat()).isoformat()

        # Tweet URL and ID
        try:
            link_elem = tweet_element.find_element(By.CSS_SELECTOR, "a[href*='/status/']")
            tweet_url = link_elem.get_attribute("href")
            tweet_id = tweet_url.split("/status/")[-1].split("?")[0]
        except Exception:
            # Fallback: hash text+date
            fallback_hash = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            tweet_url = f"https://twitter.com/{TWITTER_USERNAME}/status/{fallback_hash}"

        # Author username (without '@')
        try:
            usr_elem = tweet_element.find_element(By.CSS_SELECTOR, 'div[data-testid="User-Name"] span')
            author = usr_elem.text.replace("@", "")
        except Exception:
            author = "unknown"

        # Images (if any)
        try:
            imgs = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
            media = [img.get_attribute("src") for img in imgs]
        except Exception:
            media = []

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

def scrape_user_tweets(username: str, limit: int = 10) -> List[Dict]:
    """
    Scrape up to `limit` tweets from the given `username` (without '@').
    Returns a list of dicts, each with keys: id, text, url, created_at, author, media.
    """
    driver = setup_driver()

    # 1) Log in first
    if not login(driver):
        driver.quit()
        return []

    # 2) Navigate to the profile page
    profile_url = f"https://x.com/{username}"
    driver.get(profile_url)
    time.sleep(3)

    collected: List[Dict] = []
    seen_ids = set()
    scroll_attempts = 0
    # Rough estimate: ~3 tweets per scroll
    max_scrolls = max(1, (limit // 3) + 1)

    while len(collected) < limit and scroll_attempts < max_scrolls * 2:
        tweet_elements = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')

        for te in tweet_elements:
            if len(collected) >= limit:
                break

            data = extract_tweet_data(te)
            if data and data["id"] not in seen_ids:
                seen_ids.add(data["id"])
                collected.append(data)

        if len(collected) >= limit:
            break

        # Scroll down and wait
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)
        scroll_attempts += 1

    driver.quit()
    return collected[:limit]

if __name__ == "__main__":
    # Example usage: fetch the last 5 tweets from a user
    target_username = "jack"     # ← replace with any handle (no '@')
    max_tweets = 5

    tweets_list = scrape_user_tweets(target_username, limit=max_tweets)
    print(f"Fetched {len(tweets_list)} tweets from @{target_username}\n")
    for t in tweets_list:
        print(f"- [{t['created_at']}] @{t['author']}: {t['text'][:80]}...")
        print(f"  URL: {t['url']}")
        if t["media"]:
            print(f"  Media: {t['media']}")
        print()
