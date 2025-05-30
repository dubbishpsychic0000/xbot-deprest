import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Twitter API credentials
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Bot settings
MAX_TWEET_LENGTH = 280
THREAD_DELAY = 2
RATE_LIMIT_DELAY = 15

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def validate_config():
    required_vars = [
        'TWITTER_API_KEY', 'TWITTER_API_SECRET', 
        'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_TOKEN_SECRET',
        'GEMINI_API_KEY'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")
    
    return True

if __name__ == "__main__":
    try:
        validate_config()
        logger.info("Configuration validated successfully")
    except ValueError as e:
        logger.error(e)