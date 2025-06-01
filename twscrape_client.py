import time
import os
import hashlib
import pickle
import random

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dateutil.parser import parse

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

from dotenv import load_dotenv
load_dotenv()

TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")


def setup_driver() -> webdriver.Chrome:
    """Initialize and return a Chrome WebDriver with basic anti-detection flags."""
    import tempfile, uuid, shutil

    temp_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{uuid.uuid4().hex[:8]}_")
    options = Options()

    # Stealth flags (minimal)
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Headless if desired (uncomment for no-GUI)
    # options.add_argument("--headless=new")

    # Randomize window size
    window_sizes = ["1920,1080", "1366,768", "1536,864", "1440,900"]
    options.add_argument(f"--window-size={random.choice(window_sizes)}")

    # Rotate user-agent among a small list
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")

    # Use a fresh temp profile
    options.add_argument(f"--user-data-dir={temp_dir}")
    options.add_argument("--profile-directory=Default")

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            service = Service(executable_path=CM().install())
            driver = webdriver.Chrome(service=service, options=options)

            # Remove webdriver flag
            try:
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            except:
                pass

            driver._temp_profile_dir = temp_dir
            return driver

        except Exception as e:
            if attempt < max_attempts - 1:
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass
                temp_dir = tempfile.mkdtemp(prefix=f"chrome_profile_{uuid.uuid4().hex[:8]}_")
                # Replace --user-data-dir
                options.arguments = [arg for arg in options.arguments if not arg.startswith("--user-data-dir=")]
                options.add_argument(f"--user-data-dir={temp_dir}")
                time.sleep(random.uniform(2, 5))
            else:
                raise Exception(f"Failed to initialize Chrome driver: {e}")


def human_like_delay(min_seconds: float = 1.5, max_seconds: float = 3.0):
    """Short random delay to mimic human interactions."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def login(driver: webdriver.Chrome) -> bool:
    """
    Log in to X (formerly Twitter) with basic anti-detection steps.
    Returns True if (it appears) login succeeded.
    """
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        print("Twitter credentials missing in .env")
        return False

    for attempt in range(3):
        try:
            driver.get("https://x.com/i/flow/login")
            human_like_delay(2, 4)

            # 1) Locate username/email input
            username_selectors = [
                'input[autocomplete="username"]',
                'input[name="text"]',
                'input[data-testid="ocfEnterTextTextInput"]',
                'input[placeholder*="username"]',
                'input[placeholder*="email"]',
                'input[placeholder*="phone"]'
            ]
            username_inp = None
            for sel in username_selectors:
                try:
                    username_inp = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    break
                except TimeoutException:
                    continue

            if not username_inp:
                print("Could not locate username input")
                return False

            # Type username slowly
            username_inp.click()
            human_like_delay(0.5, 1)
            username_inp.clear()
            for ch in TWITTER_USERNAME:
                username_inp.send_keys(ch)
                time.sleep(random.uniform(0.05, 0.15))
            username_inp.send_keys(Keys.RETURN)

            human_like_delay(3, 6)

            # 2) Locate password input
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input[data-testid="ocfEnterTextTextInput"]',
                'input[placeholder*="password"]',
                'input[autocomplete="current-password"]'
            ]
            password_inp = None
            for sel in password_selectors:
                try:
                    password_inp = WebDriverWait(driver, 20).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    break
                except TimeoutException:
                    continue

            if not password_inp:
                print("Could not locate password input")
                return False

            password_inp.click()
            human_like_delay(0.5, 1)
            password_inp.clear()
            for ch in TWITTER_PASSWORD:
                password_inp.send_keys(ch)
                time.sleep(random.uniform(0.05, 0.15))
            password_inp.send_keys(Keys.RETURN)

            # Wait for login → “Home” to appear
            human_like_delay(8, 12)
            WebDriverWait(driver, 45).until(
                lambda d: "home" in d.current_url.lower() or "x.com" in d.current_url.lower()
            )
            return True

        except Exception as e:
            print(f"Login attempt {attempt + 1} failed: {e}")
            time.sleep(5)

    print("All login attempts failed.")
    return False


def extract_tweet_data_original_format(tweet_element) -> Optional[Tuple[str, str, str, str]]:
    """
    Extract tweet text, date(YYYY-MM-DD), URL, and comma-joined image URLs.
    Returns (text, date, link, images) or None on failure.
    """
    try:
        # 1) Tweet text
        try:
            tweet_text = tweet_element.find_element(By.CSS_SELECTOR, 'div[lang]').text.strip()
        except NoSuchElementException:
            tweet_text = ""

        # 2) Timestamp
        try:
            time_elem = tweet_element.find_element(By.TAG_NAME, "time")
            ts = time_elem.get_attribute("datetime")  # ISO format
            tweet_date = parse(ts).date().isoformat()
        except Exception:
            tweet_date = ""

        # 3) External link (anchor with aria-label + dir)
        try:
            anchor = tweet_element.find_element(By.CSS_SELECTOR, "a[aria-label][dir]")
            external_link = anchor.get_attribute("href")
        except Exception:
            external_link = ""

        # 4) Images
        try:
            imgs = tweet_element.find_elements(By.CSS_SELECTOR, 'div[data-testid="tweetPhoto"] img')
            img_srcs = [img.get_attribute("src") for img in imgs]
        except Exception:
            img_srcs = []
        images_links = ", ".join(img_srcs) if img_srcs else "No Images"

        return (tweet_text, tweet_date, external_link, images_links)

    except Exception as e:
        print(f"extract_tweet_data_original_format failed: {e}")
        return None


def extract_tweet_data_bot_format(tweet_element) -> Optional[Dict]:
    """
    Convert original-format tuple into bot-format dict:
      {"id","text","url","created_at","author","media"}.
    """
    try:
        orig = extract_tweet_data_original_format(tweet_element)
        if not orig:
            return None

        tweet_text, tweet_date, external_link, images_links = orig

        # created_at: YYYY-MM-DDT00:00:00 or now
        created_at = f"{tweet_date}T00:00:00" if tweet_date else datetime.now().isoformat()

        # Derive tweet_id from URL
        tweet_id = ""
        if external_link and "/status/" in external_link:
            tweet_id = external_link.split("/status/")[-1].split("?")[0].split("/")[0]
        if not tweet_id:
            fallback = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback
            if not external_link:
                external_link = f"https://x.com/status/{fallback}"

        # Extract author (@username)
        author = "unknown"
        author_selectors = [
            'div[data-testid="User-Name"] a span',
            'span[class*="username"]',
            '[data-testid="User-Name"] span',
            'a[role="link"] span'
        ]
        for sel in author_selectors:
            try:
                elems = tweet_element.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    txt = e.text.strip()
                    if txt.startswith("@"):
                        author = txt.replace("@", "")
                        break
                if author != "unknown":
                    break
            except:
                continue

        # Build media list
        media = []
        if images_links and images_links != "No Images":
            media = [u.strip() for u in images_links.split(",") if u.strip()]

        # Skip pure ads/promoted or empty
        if (not tweet_text.strip() and not media) or any(k in tweet_text.lower() for k in ["promoted", "ad", "sponsored"]):
            return None

        return {
            "id": tweet_id,
            "text": tweet_text,
            "url": external_link,
            "created_at": created_at,
            "author": author,
            "media": media
        }

    except Exception as e:
        print(f"extract_tweet_data_bot_format failed: {e}")
        return None


async def fetch_tweets(source_type: str, source: str, limit: int = 20) -> List[Dict]:
    """
    Entry point for your bot.  
      - source_type="timeline" → scrape_timeline_tweets(limit)  
      - source_type="user"     → scrape_user_tweets(source, limit)
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
    Core scraping logic, with:
    1) A “post-login debug” block that shows URL/title + first 1000 chars of page source.
    2) A “selector debug” block that prints how many elements each tweet-selector finds.
    3) Up-to-date (June 2025) tweet‐wrapper selectors, plus a few fallbacks.
    """

    # State file (pickle) for resumability
    state_file = f"{page_type}_scroll_state.pkl" if not username else f"user_{username}_scroll_state.pkl"

    scroll_count = 0
    tweets_collected = set()
    tweets_data: List[Dict] = []
    last_height = driver.execute_script("return window.pageYOffset;")
    consecutive_failures = 0
    max_failures = 5

    # Attempt to load previous state if it exists
    if os.path.exists(state_file):
        try:
            with open(state_file, "rb") as f:
                scroll_count, last_height, tweets_collected, tweets_data = pickle.load(f)
                print(f"Resumed from state: {len(tweets_data)} tweets, scroll_count={scroll_count}")
        except Exception as e:
            print(f"Could not load state: {e}")

    def save_state():
        try:
            with open(state_file, "wb") as f:
                pickle.dump((scroll_count, last_height, tweets_collected, tweets_data), f)
        except Exception as e:
            print(f"Error saving state: {e}")

    # --- POST-LOGIN DEBUG: confirm URL/title/page source snippet ---
    print("DEBUG: Post-login URL    =", driver.current_url)
    print("DEBUG: Post-login title  =", driver.title)
    snippet = driver.page_source[:1000].replace("\n", " ")
    print(f"DEBUG: Page source (first 1000 chars):\n{snippet}\n")
    # (If you need to see more of the source, increase slice above.)

    # Up‐to‐date selectors that wrap a tweet in June 2025
    tweet_selectors = [
        'article[data-testid="tweet"]',
        'div[data-testid="tweet"]',
        'article[role="article"]',
        'div[data-testid="cellInnerDiv"] article',
        '[data-testid="tweet"]',
        'div[aria-label="Timeline: Your Home Timeline"] article',
        'div[aria-label="Timeline: Home"] article'
    ]

    # --- SELECTOR DEBUG: show how many elements each selector currently matches ---
    print("DEBUG: Testing tweet selectors on the loaded page…")
    for sel in tweet_selectors:
        try:
            count = len(driver.find_elements(By.CSS_SELECTOR, sel))
        except Exception:
            count = -1
        print(f"  • Selector '{sel}' → {count} elements")
    print("DEBUG: End selector test. If all counts are 0, you must adjust tweet_selectors!\n")
    # --------------------------------------------------------------------------------------

    print(f"Starting to scrape {page_type} tweets (limit={limit})…")

    while len(tweets_data) < limit and consecutive_failures < max_failures:
        try:
            human_like_delay(1.0, 2.5)

            # 1) Find tweets using the first selector that returns any elements
            tweets = []
            for sel in tweet_selectors:
                try:
                    found = driver.find_elements(By.CSS_SELECTOR, sel)
                    if found:
                        tweets = found
                        print(f"Found {len(tweets)} tweet elements using selector: {sel}")
                        break
                except Exception:
                    continue

            # 2) If none found, scroll down and retry
            if not tweets:
                print("No tweet elements found this iteration → scrolling to load more…")
                consecutive_failures += 1
                driver.execute_script("window.scrollBy(0, 3000);")
                time.sleep(8)
                continue

            consecutive_failures = 0
            processed_in_loop = 0

            # 3) Loop through each tweet element and extract data
            for idx, tweet in enumerate(tweets):
                if len(tweets_data) >= limit:
                    break

                try:
                    if idx % 5 == 0:
                        human_like_delay(0.3, 1.0)

                    orig = extract_tweet_data_original_format(tweet)
                    if not orig:
                        continue
                    ttext, tdate, tlink, timgs = orig

                    if (not ttext.strip() and timgs == "No Images") or any(k in ttext.lower() for k in ["promoted", "ad", "sponsored"]):
                        continue

                    signature = (ttext.strip(), tdate, tlink, timgs)
                    if signature in tweets_collected:
                        continue
                    tweets_collected.add(signature)

                    bot_data = extract_tweet_data_bot_format(tweet)
                    if bot_data:
                        tweets_data.append(bot_data)
                        processed_in_loop += 1
                        print(f"  → Collected tweet #{len(tweets_data)}: {ttext[:50]}…")

                except Exception as e:
                    print(f"Error processing tweet #{idx+1}: {e}")
                    continue

            print(f"Iteration added {processed_in_loop} new tweets (total so far: {len(tweets_data)})")

            if len(tweets_data) >= limit:
                print(f"Reached requested limit ({limit}).")
                break

            # 4) Scroll a bit more and pause
            driver.execute_script("window.scrollBy(0, 3000);")
            pause = random.uniform(8, 15)
            time.sleep(pause)

            new_height = driver.execute_script("return document.body.scrollHeight")
            current_scroll = driver.execute_script("return window.pageYOffset;")
            print(f"Scroll count={scroll_count}, pageHeight={new_height}, yOffset={current_scroll}")

            # 5) If stuck (no change in height), try a forced scroll
            if new_height == last_height:
                print("Scrolling appears stuck—attempting forced scroll…")
                try:
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(10)
                    new_height2 = driver.execute_script("return document.body.scrollHeight")
                    if new_height2 == new_height:
                        consecutive_failures += 1
                        print(f"No new content after forced scroll. consecutive_failures={consecutive_failures}")
                    else:
                        new_height = new_height2
                except:
                    consecutive_failures += 1

                if consecutive_failures >= max_failures:
                    print("Too many consecutive failures—stopping scrape.")
                    break

            last_height = new_height
            scroll_count += 1

            if scroll_count % 8 == 0:
                save_state()

        except WebDriverException as e:
            print(f"WebDriver error during scraping: {e}")
            consecutive_failures += 1
            time.sleep(5)
        except Exception as e:
            print(f"Unexpected error during scraping: {e}")
            consecutive_failures += 1
            time.sleep(3)

    # Save state at the end
    save_state()
    if len(tweets_data) >= limit and os.path.exists(state_file):
        try:
            os.remove(state_file)
        except:
            pass

    return tweets_data


def scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """Scrape the home timeline (logged-in) and return up to `limit` tweets."""
    driver = None
    try:
        driver = setup_driver()
        print("Logging in…")
        if not login(driver):
            print("Login failed.")
            return []

        # Navigate to home timeline (retry up to 3 times)
        for attempt in range(3):
            try:
                driver.get("https://x.com/home")
                human_like_delay(5, 8)
                # Wait for at least one tweet-wrapper element to appear
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
                )
                break
            except TimeoutException:
                print(f"Timeline did not load on attempt #{attempt+1}")
                time.sleep(3)

        tweets_data = _scrape_tweets_common(driver, limit, "timeline")

        # Save an Excel in original format (if any tweets found)
        if tweets_data:
            rows = []
            for td in tweets_data:
                media_str = ", ".join(td.get("media", [])) if td.get("media") else "No Images"
                rows.append([td.get("text", ""), td.get("created_at", "").split("T")[0], td.get("url", ""), media_str])
            df = pd.DataFrame(rows, columns=["Tweet", "Date", "Link", "Images"])
            df.to_excel("tweets2.xlsx", index=False)
            print(f"Saved {len(rows)} tweets to tweets2.xlsx")

        return tweets_data

    except Exception as e:
        print(f"Error in scrape_timeline_tweets: {e}")
        return []
    finally:
        if driver:
            try:
                tmp = getattr(driver, "_temp_profile_dir", None)
                driver.quit()
                if tmp:
                    import shutil
                    shutil.rmtree(tmp, ignore_errors=True)
            except Exception as e:
                print(f"Error cleaning driver: {e}")


def scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Scrape a given user’s timeline (username) and return up to `limit` tweets."""
    username = username.replace("@", "").strip()
    if not username:
        print("Invalid username.")
        return []

    driver = None
    try:
        driver = setup_driver()
        print("Logging in…")
        if not login(driver):
            print("Login failed.")
            return []

        profile_url = f"https://x.com/{username}"
        for attempt in range(3):
            try:
                driver.get(profile_url)
                human_like_delay(5, 8)
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
                )
                break
            except TimeoutException:
                print(f"Profile did not load on attempt #{attempt+1}")
                time.sleep(3)

        # Check for “account doesn’t exist” or “suspended” messages
        page_text = driver.page_source.lower()
        for phrase in ["this account doesn’t exist", "account suspended", "user not found", "something went wrong"]:
            if phrase in page_text:
                print(f"Account issue detected: {phrase}")
                return []

        tweets_data = _scrape_tweets_common(driver, limit, "user", username)

        if tweets_data:
            rows = []
            for td in tweets_data:
                media_str = ", ".join(td.get("media", [])) if td.get("media") else "No Images"
                rows.append([td.get("text", ""), td.get("created_at", "").split("T")[0], td.get("url", ""), media_str])
            filename = f"{username}_tweets.xlsx"
            df = pd.DataFrame(rows, columns=["Tweet", "Date", "Link", "Images"])
            df.to_excel(filename, index=False)
            print(f"Saved {len(rows)} tweets to {filename}")

        return tweets_data

    except Exception as e:
        print(f"Error in scrape_user_tweets: {e}")
        return []
    finally:
        if driver:
            try:
                tmp = getattr(driver, "_temp_profile_dir", None)
                driver.quit()
                if tmp:
                    import shutil
                    shutil.rmtree(tmp, ignore_errors=True)
            except Exception as e:
                print(f"Error cleaning driver: {e}")
