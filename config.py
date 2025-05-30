import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
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
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# Media settings
MEDIA_DOWNLOAD_DIR = "media"
MEDIA_CLEANUP_DAYS = 7
MAX_MEDIA_SIZE_MB = 50

# Bot username (optional)
BOT_USERNAME = os.getenv('BOT_USERNAME', 'your_bot')

# Target accounts for monitoring (optional)
TARGET_ACCOUNTS = os.getenv('TARGET_ACCOUNTS', '').split(',') if os.getenv('TARGET_ACCOUNTS') else []

# Logging setup
def setup_logging(log_level: str = "INFO", log_file: str = "bot.log"):
    """Setup logging configuration"""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress some noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('tweepy').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging(os.getenv('LOG_LEVEL', 'INFO'))

def validate_config() -> bool:
    """Validate configuration and environment variables"""
    required_vars = {
        'TWITTER_API_KEY': TWITTER_API_KEY,
        'TWITTER_API_SECRET': TWITTER_API_SECRET,
        'TWITTER_ACCESS_TOKEN': TWITTER_ACCESS_TOKEN,
        'TWITTER_ACCESS_TOKEN_SECRET': TWITTER_ACCESS_TOKEN_SECRET,
        'GEMINI_API_KEY': GEMINI_API_KEY
    }
    
    missing = [var for var, value in required_vars.items() if not value]
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please check your .env file and ensure all required variables are set")
        return False
    
    # Validate API key formats (basic check)
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith('AIza'):
        logger.warning("GEMINI_API_KEY doesn't appear to be in the correct format")
    
    if TWITTER_BEARER_TOKEN and not TWITTER_BEARER_TOKEN.startswith('AAAA'):
        logger.warning("TWITTER_BEARER_TOKEN doesn't appear to be in the correct format")
    
    logger.info("Configuration validation passed")
    return True

def get_env_info() -> dict:
    """Get environment information for debugging"""
    return {
        'python_version': os.sys.version,
        'has_twitter_keys': bool(TWITTER_API_KEY and TWITTER_API_SECRET),
        'has_gemini_key': bool(GEMINI_API_KEY),
        'bot_username': BOT_USERNAME,
        'target_accounts_count': len(TARGET_ACCOUNTS),
        'log_level': logger.level,
        'media_dir': MEDIA_DOWNLOAD_DIR
    }

if __name__ == "__main__":
    try:
        is_valid = validate_config()
        if is_valid:
            logger.info("Configuration validated successfully")
            env_info = get_env_info()
            logger.info(f"Environment info: {env_info}")
        else:
            logger.error("Configuration validation failed")
            exit(1)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        exit(1)
