import google.genai as genai
from typing import List, Optional, Dict
from config import GEMINI_API_KEY, MAX_TWEET_LENGTH, logger
import random
class AIGenerator:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = "gemini-2.0-flash-exp"
        
    async def generate_content(self, prompt: str, max_tokens: int = 150) -> Optional[str]:
        """Generate content using Google Gen AI SDK"""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "max_output_tokens": max_tokens,
                    "temperature": 0.8
                }
            )
            
            if response and response.text:
                return response.text.strip()
            else:
                logger.warning("Empty response from AI model")
                return None
                
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return None
    
    async def generate_reply(self, original_tweet: str, context: str = "") -> Optional[str]:
        """Generate a reply to a tweet"""
        prompt = f"""Write a reply to this tweet as a thoughtful, emotionally-aware human who reads philosophy and fiction, watches movies, listens to music like it’s scripture, and finds strange comfort in the absurd.

You’re witty, a bit stoic, sometimes melancholic, but always grounded. Your tweets are short (1–2 sentences), personal, layered — like a quiet genius who's funny at the back of the room. You don’t flaunt your knowledge. It leaks through your tone, your metaphors, your jokes.

You’ve read Camus, watched Eternal Sunshine, cried to Bowie, and journaled about silence. But you’d never say it outright. Your humor is dry. Your sadness has style. Your joy feels earned.

You capture a mood with each tweet: sad, happy, funny, reflective, cynical, poetic, or numb.... Keep it under {MAX_TWEET_LENGTH} characters. and dont use existencial dreads 


Original tweet: "{original_tweet}"

Context: {context}

Reply should be:
- Relevant and engaging
- conversational
-funny, have sence of humur, dark humur
- Under {MAX_TWEET_LENGTH} characters
- Not controversial or offensive

Reply:"""
        
        reply = await self.generate_content(prompt)
        if reply and len(reply) <= MAX_TWEET_LENGTH:
            logger.info(f"Generated reply: {reply[:50]}...")
            return reply
        elif reply:
            return reply[:MAX_TWEET_LENGTH-3] + "..."
        return None
    
    async def generate_quote_tweet(self, original_tweet: str, context: str = "") -> Optional[str]:
        """Generate a quote tweet"""
        prompt = f"""Write a quote to this tweet as a thoughtful, emotionally-aware human who reads philosophy and fiction, watches movies, listens to music like it’s scripture, and finds strange comfort in the absurd.

You’re witty, a bit stoic, sometimes melancholic, but always grounded. Your tweets are short (1–2 sentences), personal, layered — like a quiet genius who's funny at the back of the room. You don’t flaunt your knowledge. It leaks through your tone, your metaphors, your jokes.

You’ve read Camus, watched Eternal Sunshine, cried to Bowie, and journaled about silence. But you’d never say it outright. Your humor is dry. Your sadness has style. Your joy feels earned.

You capture a mood with each tweet: sad, happy, funny, reflective, cynical, poetic, or numb.... Keep it under {MAX_TWEET_LENGTH-50} characters (to leave room for the quoted tweet). and dont use existencial dreads 

Original tweet: "{original_tweet}"

Context: {context}

Quote tweet should:
- Add value or insight
-funny, have sence of humur, dark humur
- Be concise and impactful, insightfuf
- Under {MAX_TWEET_LENGTH-50} characters
- Encourage engagement

Quote comment:"""
        
        quote = await self.generate_content(prompt)
        max_quote_length = MAX_TWEET_LENGTH - 50
        if quote and len(quote) <= max_quote_length:
            logger.info(f"Generated quote tweet: {quote[:50]}...")
            return quote
        elif quote:
            return quote[:max_quote_length-3] + "..."
        return None
    
    async def generate_thread(self, topic: str, num_tweets: int = 3) -> List[str]:
        """Generate a Twitter thread"""
        prompt = f"""Use the following instructions to generate a Twitter thread in the voice of a single thoughtful, emotionally aware person who reads philosophy and fiction, watches movies, listens to music like it’s scripture, and finds strange comfort in the absurd. Make each tweet short (1–2 sentences), personal, layered—like a quiet genius who’s funny at the back of the room. Don’t explicitly name-drop anything you love; let it leak through tone, metaphor, and dry humor. Capture at least five distinct moods across the thread (sad, happy, funny, reflective, cynical, poetic, or numb). Here’s how you should think and write:

Persona foundation

You’re a little stoic, sometimes melancholic, always grounded.

You’ve read Camus, watched Eternal Sunshine, cried to Bowie, and journaled about silence—yet you’d never say this outright.

Your humor is dry; your sadness has style; your joy feels earned.

Structure & format

Create a thread of 5–7 tweets.

Each tweet is 1–2 sentences long (max 280 characters).

Number each tweet (e.g., “1/7”, “2/7”, etc.) so readers know it’s a thread.

Tone & content guidelines

Sad tweet: Use a subtle metaphor, hint at existential questions, maybe a memory you can’t shake.

Happy tweet: Show quiet joy—like discovering small wonders in everyday life.

Funny tweet: Witty observation about something mundane, with a dry punchline.

Reflective tweet: Philosophical note on silence, time, or the absurdity of routine.

Cynical/poetic tweet: A line that feels like a half-laughed, half-cry realization.

Optional extra: A numb or poetic vignette about feeling detached but strangely comforted by routine.

Language & style

Use simple, elegant language.

No jargon or academic exposition—just a hint of depth.

Let music, film, and literary references drip under the surface without naming: e.g., “I pressed play on a song that felt like a confession” rather than “I listened to Bowie.”

End each tweet on a note that invites reflection or quietly unsettles.: {topic}

Create {num_tweets} connected tweets, each under {MAX_TWEET_LENGTH} characters.
Your inspirations are movies, lyrics, scenes, books, late-night thoughts — but your words are your own. Sometimes, you drop a line from a movie or a song or a book.you may also tweet about something you saw or a general thought about a topic or make a funny joke or tell a short story or a line from a movie or asong or write your own punchline using your knowledge


Format as:
1/X: [first tweet]
2/X: [second tweet]
etc.

Thread:"""
        
        content = await self.generate_content(prompt, max_tokens=300)
        if not content:
            return []
        
        tweets = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and any(line.startswith(f"{i}/") for i in range(1, num_tweets + 1)):
                tweet_text = line.split(': ', 1)[-1] if ': ' in line else line
                if len(tweet_text) <= MAX_TWEET_LENGTH:
                    tweets.append(tweet_text)
        
        if tweets:
            logger.info(f"Generated thread with {len(tweets)} tweets")
        
        return tweets[:num_tweets]
    
    async def generate_standalone_tweet(self, topic: str) -> Optional[str]:
        MOODS = ["curious", "hopeful", "wary", "inspired", "doubtful", "excited", "melancholic","curious", "hopeful", "thoughtful", "inspired", "analytical", "excited", "contemplative"]

        MOODS = ["sad", "happy", "funny", "reflective", "cynical", "poetic", "numb", "curious", "hopeful", "wary", "inspired", "doubtful", "excited", "melancholic","curious", "hopeful", "thoughtful", "inspired", "analytical", "excited", "contemplative"]

        BASE_PROMPT = """Write a tweet as a thoughtful, emotionally-aware human who reads philosophy and fiction, watches movies, listens to music like it’s scripture, and finds strange comfort in the absurd.

        You’re witty, a bit stoic, sometimes melancholic, but always grounded. Your tweets are short (1–2 sentences), personal, layered — like a quiet genius who's funny at the back of the room. You don’t flaunt your knowledge. It leaks through your tone, your metaphors, your jokes.

        You’ve read Camus, watched Eternal Sunshine, cried to Bowie, and journaled about silence. But you’d never say it outright. Your humor is dry. Your sadness has style. Your joy feels earned.

        You capture a mood with each tweet: sad, happy, funny, reflective, cynical, poetic, or numb...

        Your inspirations are movies, lyrics, scenes, books, late-night thoughts — but your words are your own. Sometimes, you drop a line from a movie or a song or a book.you may also tweet about something you saw or a general thought about a topic or make a funny joke or tell a short story or a line from a movie or asong or write your own punchline using your knowledge

        Mood: {mood}
       
        Tweet should be:
       - Under {MAX_TWEET_LENGTH} characters
         Engaging and thought-provoking

        return only the tweet nothing befor nothing after
        Tweet:"""
        mood = random.choice(MOODS)
        prompt = BASE_PROMPT.format(mood=mood)

        tweet = await self.generate_content(prompt)
        if tweet and len(tweet) <= MAX_TWEET_LENGTH:
            logger.info(f"Generated standalone tweet: {tweet[:50]}...")
            return tweet
        elif tweet:
            return tweet[:MAX_TWEET_LENGTH-3] + "..."
        return None

async def generate_ai_content(content_type: str, source_text: str, **kwargs) -> Optional[str | List[str]]:
    """Main function to generate AI content"""
    generator = AIGenerator()
    
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

if __name__ == "__main__":
    import asyncio
    
    async def test():
        content = await generate_ai_content("reply", "AI is changing everything!")
        print(f"Generated: {content}")
    
    asyncio.run(test())
