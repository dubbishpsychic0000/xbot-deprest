import asyncio
import time
from typing import List, Optional, Dict
from google import genai
from config import GEMINI_API_KEY, MAX_TWEET_LENGTH, logger

class AIGenerator:
    def __init__(self):
        # Initialize with the new Google GenAI SDK
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = "gemini-2.0-flash-exp"  # Updated model name
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Minimum 1 second between requests
        
    async def _rate_limit_delay(self):
        """Implement rate limiting to avoid 429 errors"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
        
    async def generate_content(self, prompt: str, max_tokens: int = 150, retry_count: int = 3) -> Optional[str]:
        """Generate content using Google Gen AI SDK with retry logic"""
        for attempt in range(retry_count):
            try:
                await self._rate_limit_delay()
                
                # Updated API call structure for new SDK
                response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai.GenerateContentConfig(
                        max_output_tokens=max_tokens,
                        temperature=0.8,
                        top_p=0.9,
                        top_k=40
                    )
                )
                
                if response and response.text:
                    return response.text.strip()
                else:
                    logger.warning("Empty response from AI model")
                    return None
                    
            except Exception as e:
                if "429" in str(e) and attempt < retry_count - 1:
                    # Exponential backoff for rate limit errors
                    wait_time = (2 ** attempt) * 5  # 5, 10, 20 seconds
                    logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}")
                    await asyncio.sleep(wait_time)
                    continue
                elif "404" in str(e):
                    logger.error(f"Model not found: {self.model_name}. Trying fallback model.")
                    # Fallback to a known working model
                    if self.model_name != "gemini-1.5-flash":
                        self.model_name = "gemini-1.5-flash"
                        continue
                
                logger.error(f"AI generation failed (attempt {attempt + 1}): {e}")
                if attempt == retry_count - 1:
                    return None
        
        return None
    
    async def generate_reply(self, original_tweet: str, context: str = "") -> Optional[str]:
        """Generate a reply to a tweet"""
        prompt = f"""Generate a thoughtful, engaging reply to this tweet. Keep it under {MAX_TWEET_LENGTH} characters.

Original tweet: "{original_tweet}"

Context: {context}

Requirements:
- Relevant and engaging
- Professional but conversational
- Under {MAX_TWEET_LENGTH} characters
- Not controversial or offensive
- Add value to the conversation

Reply:"""
        
        reply = await self.generate_content(prompt, max_tokens=100)
        if reply and len(reply) <= MAX_TWEET_LENGTH:
            logger.info(f"Generated reply: {reply[:50]}...")
            return reply
        elif reply:
            # Truncate if too long
            truncated = reply[:MAX_TWEET_LENGTH-3] + "..."
            logger.info(f"Truncated reply: {truncated[:50]}...")
            return truncated
        return None
    
    async def generate_quote_tweet(self, original_tweet: str, context: str = "") -> Optional[str]:
        """Generate a quote tweet"""
        max_quote_length = MAX_TWEET_LENGTH - 50  # Leave room for quoted tweet
        
        prompt = f"""Generate a quote tweet comment for this tweet. Keep it under {max_quote_length} characters.

Original tweet: "{original_tweet}"

Context: {context}

Requirements:
- Add value or insight
- Be concise and impactful
- Under {max_quote_length} characters
- Encourage engagement
- Complement, don't repeat the original

Quote comment:"""
        
        quote = await self.generate_content(prompt, max_tokens=80)
        if quote and len(quote) <= max_quote_length:
            logger.info(f"Generated quote tweet: {quote[:50]}...")
            return quote
        elif quote:
            truncated = quote[:max_quote_length-3] + "..."
            logger.info(f"Truncated quote tweet: {truncated[:50]}...")
            return truncated
        return None
    
    async def generate_thread(self, topic: str, num_tweets: int = 3) -> List[str]:
        """Generate a Twitter thread"""
        prompt = f"""Generate a Twitter thread about: {topic}

Create {num_tweets} connected tweets, each under {MAX_TWEET_LENGTH} characters.

Requirements:
- Educational or insightful
- Each tweet flows to the next
- Engaging and valuable
- Professional tone
- Include relevant hashtags
- Number each tweet (1/{num_tweets}, 2/{num_tweets}, etc.)

Format each tweet on a new line starting with the number.

Thread:"""
        
        content = await self.generate_content(prompt, max_tokens=400)
        if not content:
            return []
        
        tweets = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and any(line.startswith(f"{i}/") for i in range(1, num_tweets + 1)):
                # Extract tweet text after the numbering
                if ': ' in line:
                    tweet_text = line.split(': ', 1)[1]
                elif ' ' in line and line[0].isdigit():
                    tweet_text = ' '.join(line.split(' ')[1:])
                else:
                    tweet_text = line
                
                if len(tweet_text) <= MAX_TWEET_LENGTH and tweet_text:
                    tweets.append(tweet_text)
        
        # Ensure we have the right number of tweets
        tweets = tweets[:num_tweets]
        
        if tweets:
            logger.info(f"Generated thread with {len(tweets)} tweets")
        
        return tweets
    
    async def generate_standalone_tweet(self, topic: str) -> Optional[str]:
        """Generate a standalone tweet about a topic"""
        prompt = f"""Generate an engaging tweet about: {topic}

Requirements:
- Under {MAX_TWEET_LENGTH} characters
- Engaging and thought-provoking
- Include relevant hashtags (2-3 max)
- Professional but conversational
- Call to action or question to encourage engagement

Tweet:"""
        
        tweet = await self.generate_content(prompt, max_tokens=100)
        if tweet and len(tweet) <= MAX_TWEET_LENGTH:
            logger.info(f"Generated standalone tweet: {tweet[:50]}...")
            return tweet
        elif tweet:
            truncated = tweet[:MAX_TWEET_LENGTH-3] + "..."
            logger.info(f"Truncated standalone tweet: {truncated[:50]}...")
            return truncated
        return None

async def generate_ai_content(content_type: str, source_text: str, **kwargs) -> Optional[str | List[str]]:
    """Main function to generate AI content with improved error handling"""
    generator = AIGenerator()
    
    try:
        if content_type == "reply":
            return await generator.generate_reply(source_text, kwargs.get('context', ''))
        elif content_type == "quote":
            return await generator.generate_quote_tweet(source_text, kwargs.get('context', ''))
        elif content_type == "thread":
            return await generator.generate_thread(source_text, kwargs.get('num_tweets', 3))
        elif content_type == "standalone":
            return await generator.generate_standalone_tweet(source_text)
        else:
            logger.error(f"Invalid content type: {content_type}")
            return None
    except Exception as e:
        logger.error(f"Error in generate_ai_content: {e}")
        return None

if __name__ == "__main__":
    async def test():
        print("Testing AI content generation...")
        
        # Test standalone tweet
        content = await generate_ai_content("standalone", "artificial intelligence future")
        print(f"Standalone Tweet: {content}")
        
        # Test reply
        reply = await generate_ai_content("reply", "AI is changing everything!", context="Discussion about AI impact")
        print(f"Reply: {reply}")
        
        # Test thread
        thread = await generate_ai_content("thread", "machine learning basics", num_tweets=3)
        print(f"Thread: {thread}")
    
    asyncio.run(test())
