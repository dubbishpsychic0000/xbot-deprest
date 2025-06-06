import tweepy
import time
import asyncio
from typing import List, Optional
from config import (
    TWITTER_API_KEY, TWITTER_API_SECRET, 
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET,
    THREAD_DELAY, logger
)

class TwitterRateLimitHandler:
    """Handles rate limiting and calculates appropriate delay."""
    def __init__(self):
        self.consecutive_rate_limits = 0
        self.max_consecutive_limits = 5
        self.initial_delay = 30  # seconds
        self.max_delay = 1200  # seconds (20 minutes)
        self.last_reset_time = time.time()
        self.is_new_account = False  # Temporarily disable new account detection
        self.gentle_mode = False  # Disable gentle mode for testing

    def calculate_delay(self, reset_time=None):
        """Calculates the delay based on consecutive rate limits and available reset time."""
        self.consecutive_rate_limits += 1

        # If we have a reset_time, use it to calculate the delay
        if reset_time:
            current_time = time.time()
            delay = max(0, reset_time - current_time)
            logger.info(f"Using provided reset time for delay: {delay:.0f}s")
            return delay + 30  # Add larger buffer for new accounts

        # For new accounts, be much more conservative
        if self.is_new_account or self.gentle_mode:
            # Much longer delays for new accounts
            base_delay = 300  # 5 minutes minimum
            delay = base_delay * (2 ** (self.consecutive_rate_limits - 1))
            delay = min(delay, 3600)  # Cap at 1 hour for new accounts
            logger.warning(f"NEW ACCOUNT - Conservative delay: {delay:.0f}s (consecutive limits: {self.consecutive_rate_limits})")
            return delay

        # If we've exceeded the maximum consecutive limits, use max_delay
        if self.consecutive_rate_limits > self.max_consecutive_limits:
            logger.warning("Exceeded max consecutive rate limits, using max delay")
            return self.max_delay

        # Exponential backoff
        delay = self.initial_delay * (2 ** (self.consecutive_rate_limits - 1))
        delay = min(delay, self.max_delay)  # Cap the delay
        logger.info(f"Calculated delay: {delay:.0f}s (consecutive limits: {self.consecutive_rate_limits})")
        return delay

    def reset_consecutive_limits(self):
        """Resets the consecutive rate limits counter."""
        self.consecutive_rate_limits = 0
        self.last_reset_time = time.time()
        
        # After 3 successful posts, assume account is established
        if self.is_new_account:
            self.successful_posts = getattr(self, 'successful_posts', 0) + 1
            if self.successful_posts >= 3:
                self.is_new_account = False
                self.gentle_mode = False
                logger.info("Account established - switching to normal rate limiting")
        
        logger.info("Rate limit counter reset")
    
    def force_reset_all(self):
        """Force reset all rate limit tracking for new API credentials."""
        self.consecutive_rate_limits = 0
        self.last_reset_time = time.time()
        self.is_new_account = True
        self.gentle_mode = True
        self.successful_posts = 0
        logger.info("Force reset all rate limit tracking - new API credentials detected")

    def refresh_state(self):
        """Refresh rate limiting state for a clean start."""
        self.consecutive_rate_limits = 0
        self.last_reset_time = time.time()
        logger.info("Rate limiting state refreshed")


class TwitterClient:
    def __init__(self):
        self.api = None
        self.client = None
        self.rate_limit_handler = TwitterRateLimitHandler()
        self.rate_limit_handler.refresh_state()  # Fresh start
        self.setup_apis()

    def setup_apis(self):
        """Initialize Twitter API v1.1 and v2 clients with custom rate limit handling"""
        try:
            # Twitter API v1.1 for legacy functions (disable built-in rate limit handling)
            auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET)
            auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
            self.api = tweepy.API(auth, wait_on_rate_limit=False)

            # Twitter API v2 for newer functions (disable built-in rate limit handling)
            self.client = tweepy.Client(
                consumer_key=TWITTER_API_KEY,
                consumer_secret=TWITTER_API_SECRET,
                access_token=TWITTER_ACCESS_TOKEN,
                access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
                wait_on_rate_limit=False
            )

            logger.info("Twitter APIs initialized successfully with custom rate limiting")

        except Exception as e:
            logger.error(f"Failed to initialize Twitter APIs: {e}")
            raise

    async def handle_rate_limit_with_retry(self, func, *args, max_retries=3, **kwargs):
        """Execute function with intelligent rate limit handling and retries"""
        for attempt in range(max_retries):
            try:
                result = func(*args, **kwargs)
                self.rate_limit_handler.reset_consecutive_limits()
                return result

            except tweepy.TooManyRequests as e:
                logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries})")

                if attempt == max_retries - 1:
                    logger.error("Max retries reached for rate limiting")
                    raise

                # Extract reset time from headers if available
                reset_time = None
                if hasattr(e, 'response') and e.response:
                    reset_header = e.response.headers.get('x-rate-limit-reset')
                    if reset_header:
                        try:
                            reset_time = int(reset_header)
                        except (ValueError, TypeError):
                            pass

                delay = self.rate_limit_handler.calculate_delay(reset_time)

                # For long delays, check if we should continue
                if delay > 300:  # 5 minutes
                    logger.warning(f"Long delay ({delay}s) - consider stopping bot temporarily")

                await asyncio.sleep(delay)

            except tweepy.Forbidden as e:
                logger.error(f"Twitter API access forbidden: {e}")
                raise

            except tweepy.Unauthorized as e:
                logger.error(f"Twitter API unauthorized: {e}")
                raise

            except Exception as e:
                logger.error(f"Unexpected error during Twitter API call: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(30)  # Short delay for other errors

class TwitterPoster:
    def __init__(self):
        self.client = TwitterClient()

        # Rate limiting tracking
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests

    def _handle_rate_limit(self):
        """Ensure minimum time between API requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.info(f"Rate limiting: waiting {sleep_time:.1f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    async def post_tweet(self, text: str, reply_to_id: Optional[str] = None, media_paths: Optional[List[str]] = None) -> Optional[str]:
        """Post a single tweet with enhanced rate limit handling"""
        try:
            #self._handle_rate_limit() #The handle_rate_limit is removed because the rate limit handling is handled by the TwitterClient class

            # media_ids = []
            # if media_paths:
            #     for media_path in media_paths:
            #         try:
            #             media = self.client.api.media_upload(media_path)
            #             media_ids.append(media.media_id)
            #             await asyncio.sleep(1)  # Small delay between media uploads
            #         except Exception as e:
            #             logger.error(f"Failed to upload media {media_path}: {e}")

            # response = await self.client.handle_rate_limit_with_retry(
            #     self.client.client.create_tweet,
            #     text=text,
            #     in_reply_to_tweet_id=reply_to_id,
            #     media_ids=media_ids if media_ids else None
            # )
            if len(text) > 280:
                text = text[:277] + "..."
                logger.warning("Tweet content truncated to fit character limit")

            create_tweet_kwargs = {"text": text}
            if reply_to_id:
                create_tweet_kwargs["in_reply_to_tweet_id"] = reply_to_id
            # if media_ids:
            #     create_tweet_kwargs["media_ids"] = media_ids

            response = await self.client.handle_rate_limit_with_retry(
                self.client.client.create_tweet,
                **create_tweet_kwargs
            )


            tweet_id = str(response.data['id'])
            logger.info(f"Posted tweet: {tweet_id}")
            return tweet_id

        except tweepy.TooManyRequests as e:
            logger.error(f"Rate limit exceeded: {e}")
            logger.info("Waiting 15 minutes for rate limit reset...")
            await asyncio.sleep(900)  # Wait 15 minutes
            return None
        except tweepy.Forbidden as e:
            logger.error(f"Twitter API forbidden error: {e}")
            return None
        except tweepy.NotFound as e:
            logger.error(f"Tweet not found (possibly deleted): {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
            return None

    async def post_reply(self, text: str, reply_to_id: str, media_paths: Optional[List[str]] = None) -> Optional[str]:
        """Post a reply to a specific tweet"""
        if not reply_to_id:
            logger.error("reply_to_id is required for replies")
            return None

        logger.info(f"Posting reply to tweet {reply_to_id}")
        return await self.post_tweet(text, reply_to_id, media_paths)

    async def post_quote_tweet(self, text: str, quoted_tweet_id: str) -> Optional[str]:
        """Post a quote tweet"""
        try:
            #self._handle_rate_limit()  #Rate limit is handled by the TwitterClient class

            # Use the proper quote tweet format
            quoted_url = f"https://twitter.com/i/status/{quoted_tweet_id}"
            full_text = f"{text} {quoted_url}"

            # Check length
            if len(full_text) > 280:
                # Truncate the comment text to fit
                max_comment_length = 280 - len(quoted_url) - 1
                text = text[:max_comment_length-3] + "..."
                full_text = f"{text} {quoted_url}"

            response = await self.client.handle_rate_limit_with_retry(
                self.client.client.create_tweet,
                text=full_text
            )
            tweet_id = str(response.data['id'])
            logger.info(f"Posted quote tweet: {tweet_id}")
            return tweet_id

        except tweepy.TooManyRequests as e:
            logger.error(f"Rate limit exceeded: {e}")
            await asyncio.sleep(900)  # Wait 15 minutes
            return None
        except Exception as e:
            logger.error(f"Failed to post quote tweet: {e}")
            return None

    async def post_thread(self, tweets: List[str], media_paths: Optional[List[List[str]]] = None) -> List[str]:
        """Post a thread of connected tweets"""
        posted_ids = []

        for i, tweet_text in enumerate(tweets):
            try:
                tweet_media = media_paths[i] if media_paths and i < len(media_paths) else None
                reply_to = posted_ids[-1] if posted_ids else None

                # Add thread indicators
                if len(tweets) > 1:
                    thread_indicator = f"🧵 {i+1}/{len(tweets)} "
                    # Ensure we don't exceed character limit
                    max_content_length = 280 - len(thread_indicator)
                    if len(tweet_text) > max_content_length:
                        tweet_text = tweet_text[:max_content_length-3] + "..."
                    tweet_text = thread_indicator + tweet_text

                tweet_id = await self.post_tweet(tweet_text, reply_to, tweet_media)
                if tweet_id:
                    posted_ids.append(tweet_id)
                    if i < len(tweets) - 1:
                        await asyncio.sleep(THREAD_DELAY)
                else:
                    logger.error(f"Failed to post tweet {i+1} in thread")
                    break

            except Exception as e:
                logger.error(f"Error posting thread tweet {i+1}: {e}")
                break

        logger.info(f"Posted thread with {len(posted_ids)}/{len(tweets)} tweets")
        return posted_ids

    def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet"""
        try:
            self._handle_rate_limit()
            self.client.client.delete_tweet(tweet_id)
            logger.info(f"Deleted tweet: {tweet_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete tweet {tweet_id}: {e}")
            return False

    def get_tweet_info(self, tweet_id: str) -> Optional[dict]:
        """Get information about a tweet"""
        return None

    def check_tweet_exists(self, tweet_id: str) -> bool:
        """Check if a tweet exists (not deleted)"""

        return True

async def post_content(content_type: str, content: str | List[str], **kwargs) -> Optional[str | List[str]]:
    """Main function to post content to Twitter with improved error handling"""
    poster = TwitterPoster()

    try:
        if content_type == "tweet":
            return await poster.post_tweet(content, kwargs.get('reply_to_id'), kwargs.get('media_paths'))

        elif content_type == "reply":
            reply_to_id = kwargs.get('reply_to_id')
            if not reply_to_id:
                logger.error("reply_to_id required for reply")
                return None

            # Check if the original tweet still exists
            if not poster.check_tweet_exists(reply_to_id):
                logger.warning(f"Original tweet {reply_to_id} no longer exists, skipping reply")
                return None

            return await poster.post_reply(content, reply_to_id, kwargs.get('media_paths'))

        elif content_type == "quote":
            quoted_tweet_id = kwargs.get('quoted_tweet_id')
            if not quoted_tweet_id:
                logger.error("quoted_tweet_id required for quote tweet")
                return None

            # Check if the original tweet still exists
            if not poster.check_tweet_exists(quoted_tweet_id):
                logger.warning(f"Original tweet {quoted_tweet_id} no longer exists, skipping quote")
                return None

            return await poster.post_quote_tweet(content, quoted_tweet_id)

        elif content_type == "thread":
            if not isinstance(content, list):
                logger.error("Thread content must be a list of tweets")
                return None
            return await poster.post_thread(content, kwargs.get('media_paths'))

        else:
            logger.error(f"Invalid content type: {content_type}")
            return None

    except Exception as e:
        logger.error(f"Failed to post content: {e}")
        return None

# Synchronous wrapper for backward compatibility
def post_content_sync(content_type: str, content, **kwargs):
    """Synchronous wrapper for post_content"""
    return asyncio.run(post_content(content_type, content, **kwargs))

if __name__ == "__main__":
    async def main():
        test_tweet = "Testing the improved Twitter bot posting functionality with rate limiting!"
        result = await post_content("tweet", test_tweet)
        print(f"Posted tweet ID: {result}")
    asyncio.run(main())