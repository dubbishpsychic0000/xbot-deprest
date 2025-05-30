import tweepy
import time
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
        self.api_v1 = tweepy.API(auth)
    
    def post_tweet(self, text: str, reply_to_id: Optional[str] = None, media_paths: Optional[List[str]] = None) -> Optional[str]:
        """Post a single tweet"""
        try:
            media_ids = []
            if media_paths:
                for media_path in media_paths:
                    media = self.api_v1.media_upload(media_path)
                    media_ids.append(media.media_id)
            
            response = self.client.create_tweet(
                text=text,
                in_reply_to_tweet_id=reply_to_id,
                media_ids=media_ids if media_ids else None
            )
            
            tweet_id = str(response.data['id'])
            logger.info(f"Posted tweet: {tweet_id}")
            return tweet_id
        
        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
            return None
    
    def post_reply(self, text: str, reply_to_id: str, media_paths: Optional[List[str]] = None) -> Optional[str]:
        """Post a reply to a specific tweet"""
        return self.post_tweet(text, reply_to_id, media_paths)
    
    def post_quote_tweet(self, text: str, quoted_tweet_id: str) -> Optional[str]:
        """Post a quote tweet"""
        try:
            quoted_url = f"https://twitter.com/user/status/{quoted_tweet_id}"
            full_text = f"{text} {quoted_url}"
            
            response = self.client.create_tweet(text=full_text)
            tweet_id = str(response.data['id'])
            logger.info(f"Posted quote tweet: {tweet_id}")
            return tweet_id
        
        except Exception as e:
            logger.error(f"Failed to post quote tweet: {e}")
            return None
    
    def post_thread(self, tweets: List[str], media_paths: Optional[List[List[str]]] = None) -> List[str]:
        """Post a thread of connected tweets"""
        posted_ids = []
        
        for i, tweet_text in enumerate(tweets):
            tweet_media = media_paths[i] if media_paths and i < len(media_paths) else None
            reply_to = posted_ids[-1] if posted_ids else None
            
            tweet_id = self.post_tweet(tweet_text, reply_to, tweet_media)
            if tweet_id:
                posted_ids.append(tweet_id)
                if i < len(tweets) - 1:
                    time.sleep(THREAD_DELAY)
            else:
                logger.error(f"Failed to post tweet {i+1} in thread")
                break
        
        logger.info(f"Posted thread with {len(posted_ids)} tweets")
        return posted_ids
    
    def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet"""
        try:
            self.client.delete_tweet(tweet_id)
            logger.info(f"Deleted tweet: {tweet_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete tweet {tweet_id}: {e}")
            return False
    
    def get_tweet_info(self, tweet_id: str) -> Optional[dict]:
        """Get information about a tweet"""
        try:
            tweet = self.client.get_tweet(
                tweet_id, 
                tweet_fields=['created_at', 'public_metrics', 'author_id']
            )
            return {
                'id': tweet.data.id,
                'text': tweet.data.text,
                'created_at': tweet.data.created_at.isoformat(),
                'metrics': tweet.data.public_metrics,
                'author_id': tweet.data.author_id
            }
        except Exception as e:
            logger.error(f"Failed to get tweet info for {tweet_id}: {e}")
            return None

def post_content(content_type: str, content: str | List[str], **kwargs) -> Optional[str | List[str]]:
    """Main function to post content to Twitter"""
    poster = TwitterPoster()
    
    if content_type == "tweet":
        return poster.post_tweet(content, kwargs.get('reply_to_id'), kwargs.get('media_paths'))
    elif content_type == "reply":
        reply_to_id = kwargs.get('reply_to_id')
        if not reply_to_id:
            logger.error("reply_to_id required for reply")
            return None
        return poster.post_reply(content, reply_to_id, kwargs.get('media_paths'))
    elif content_type == "quote":
        quoted_tweet_id = kwargs.get('quoted_tweet_id')
        if not quoted_tweet_id:
            logger.error("quoted_tweet_id required for quote tweet")
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

if __name__ == "__main__":
    test_tweet = "Testing the Twitter bot posting functionality!"
    result = post_content("tweet", test_tweet)
    print(f"Posted tweet ID: {result}")