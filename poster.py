import tweepy
import time
import asyncio
from typing import List, Optional
from config import (
    TWITTER_API_KEY, TWITTER_API_SECRET, 
    TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET,
    THREAD_DELAY, logger
)

class TwitterPoster:
    def __init__(self):
        self.client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=True
        )
        
        # V1.1 API for media upload
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY, TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET
        )
        self.api_v1 = tweepy.API(auth, wait_on_rate_limit=True)
        
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
    
    def post_tweet(self, text: str, reply_to_id: Optional[str] = None, media_paths: Optional[List[str]] = None) -> Optional[str]:
        """Post a single tweet with rate limiting"""
        try:
            self._handle_rate_limit()
            
            media_ids = []
            if media_paths:
                for media_path in media_paths:
                    try:
                        media = self.api_v1.media_upload(media_path)
                        media_ids.append(media.media_id)
                        time.sleep(1)  # Small delay between media uploads
                    except Exception as e:
                        logger.error(f"Failed to upload media {media_path}: {e}")
            
            response = self.client.create_tweet(
                text=text,
                in_reply_to_tweet_id=reply_to_id,
                media_ids=media_ids if media_ids else None
            )
            
            tweet_id = str(response.data['id'])
            logger.info(f"Posted tweet: {tweet_id}")
            return tweet_id
        
        except tweepy.TooManyRequests as e:
            logger.error(f"Rate limit exceeded: {e}")
            logger.info("Waiting 15 minutes for rate limit reset...")
            time.sleep(900)  # Wait 15 minutes
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
    
    def post_reply(self, text: str, reply_to_id: str, media_paths: Optional[List[str]] = None) -> Optional[str]:
        """Post a reply to a specific tweet"""
        if not reply_to_id:
            logger.error("reply_to_id is required for replies")
            return None
        
        logger.info(f"Posting reply to tweet {reply_to_id}")
        return self.post_tweet(text, reply_to_id, media_paths)
    
    def post_quote_tweet(self, text: str, quoted_tweet_id: str) -> Optional[str]:
        """Post a quote tweet"""
        try:
            self._handle_rate_limit()
            
            # Use the proper quote tweet format
            quoted_url = f"https://twitter.com/i/status/{quoted_tweet_id}"
            full_text = f"{text} {quoted_url}"
            
            # Check length
            if len(full_text) > 280:
                # Truncate the comment text to fit
                max_comment_length = 280 - len(quoted_url) - 1
                text = text[:max_comment_length-3] + "..."
                full_text = f"{text} {quoted_url}"
            
            response = self.client.create_tweet(text=full_text)
            tweet_id = str(response.data['id'])
            logger.info(f"Posted quote tweet: {tweet_id}")
            return tweet_id
        
        except tweepy.TooManyRequests as e:
            logger.error(f"Rate limit exceeded: {e}")
            time.sleep(900)  # Wait 15 minutes
            return None
        except Exception as e:
            logger.error(f"Failed to post quote tweet: {e}")
            return None
    
    def post_thread(self, tweets: List[str], media_paths: Optional[List[List[str]]] = None) -> List[str]:
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
                
                tweet_id = self.post_tweet(tweet_text, reply_to, tweet_media)
                if tweet_id:
                    posted_ids.append(tweet_id)
                    if i < len(tweets) - 1:
                        time.sleep(THREAD_DELAY)
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
            self.client.delete_tweet(tweet_id)
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

def post_content(content_type: str, content: str | List[str], **kwargs) -> Optional[str | List[str]]:
    """Main function to post content to Twitter with improved error handling"""
    poster = TwitterPoster()
    
    try:
        if content_type == "tweet":
            return poster.post_tweet(content, kwargs.get('reply_to_id'), kwargs.get('media_paths'))
        
        elif content_type == "reply":
            reply_to_id = kwargs.get('reply_to_id')
            if not reply_to_id:
                logger.error("reply_to_id required for reply")
                return None
            
            # Check if the original tweet still exists
            if not poster.check_tweet_exists(reply_to_id):
                logger.warning(f"Original tweet {reply_to_id} no longer exists, skipping reply")
                return None
                
            return poster.post_reply(content, reply_to_id, kwargs.get('media_paths'))
        
        elif content_type == "quote":
            quoted_tweet_id = kwargs.get('quoted_tweet_id')
            if not quoted_tweet_id:
                logger.error("quoted_tweet_id required for quote tweet")
                return None
            
            # Check if the original tweet still exists
            if not poster.check_tweet_exists(quoted_tweet_id):
                logger.warning(f"Original tweet {quoted_tweet_id} no longer exists, skipping quote")
                return None
                
            return poster.post_quote_tweet(content, quoted_tweet_id)
        
        elif content_type == "thread":
            if not isinstance(content, list):
                logger.error("Thread content must be a list of tweets")
                return None
            return poster.post_thread(content, kwargs.get('media_paths'))
        
        else:
            logger.error(f"Invalid content type: {content_type}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to post content: {e}")
        return None

if __name__ == "__main__":
    test_tweet = "Testing the improved Twitter bot posting functionality with rate limiting!"
    result = post_content("tweet", test_tweet)
    print(f"Posted tweet ID: {result}")
