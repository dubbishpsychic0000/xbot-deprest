import os
from dotenv import load_dotenv
import logging

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Twitter API Configuration
TWITTER_API_KEY = os.getenv('TWITTER_API_KEY')
TWITTER_API_SECRET = os.getenv('TWITTER_API_SECRET')
TWITTER_ACCESS_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# Bot Configuration
BOT_USERNAME = os.getenv('BOT_USERNAME', 'default_bot')
TARGET_ACCOUNTS = os.getenv('TARGET_ACCOUNTS', '').split(',') if os.getenv('TARGET_ACCOUNTS') else []

# Twitter Configuration
MAX_TWEET_LENGTH = 280
RATE_LIMIT_DELAY = 2  # seconds between requests
THREAD_DELAY = 3  # seconds between thread tweets

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Validate configuration
def validate_config():
    missing_vars = []
    
    if not GEMINI_API_KEY:
        missing_vars.append("GEMINI_API_KEY")
    
    if not TWITTER_API_KEY:
        missing_vars.append("TWITTER_API_KEY")
    
    if not TWITTER_API_SECRET:
        missing_vars.append("TWITTER_API_SECRET")
    
    if not TWITTER_ACCESS_TOKEN:
        missing_vars.append("TWITTER_ACCESS_TOKEN")
    
    if not TWITTER_ACCESS_TOKEN_SECRET:
        missing_vars.append("TWITTER_ACCESS_TOKEN_SECRET")
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logger.info("Configuration validated successfully")

if __name__ == "__main__":
    validate_config()
