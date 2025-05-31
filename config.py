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

# Twitter scraping credentials
TWITTER_USERNAME = os.getenv('TWITTER_USERNAME')
TWITTER_PASSWORD = os.getenv('TWITTER_PASSWORD')
TWITTER_EMAIL = os.getenv('TWITTER_EMAIL')

# Bot Configuration
BOT_USERNAME = os.getenv('BOT_USERNAME', 'default_bot')
TARGET_ACCOUNTS = os.getenv('TARGET_ACCOUNTS', '').split(',') if os.getenv('TARGET_ACCOUNTS') else []

# Constants
MAX_TWEET_LENGTH = 280
RATE_LIMIT_DELAY = 2
THREAD_DELAY = 3

# Logging
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
    missing_vars = []
    
    required_vars = {
        'GEMINI_API_KEY': GEMINI_API_KEY,
        'TWITTER_API_KEY': TWITTER_API_KEY,
        'TWITTER_API_SECRET': TWITTER_API_SECRET,
        'TWITTER_ACCESS_TOKEN': TWITTER_ACCESS_TOKEN,
        'TWITTER_ACCESS_TOKEN_SECRET': TWITTER_ACCESS_TOKEN_SECRET,
        'TWITTER_USERNAME': TWITTER_USERNAME,
        'TWITTER_PASSWORD': TWITTER_PASSWORD
    }
    
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logger.info("Configuration validated successfully")
