import os
from dotenv import load_dotenv
import logging
from datetime import datetime

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
THREAD_DELAY = 5  # Increased delay between thread tweets
ENGAGEMENT_DELAY = 30  # Delay between engagement actions

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 5

# File paths
LOG_FILE = 'bot.log'
STATE_DIR = 'state'
MEDIA_DIR = 'media'

# Create necessary directories
os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(MEDIA_DIR, exist_ok=True)

# Enhanced Logging Configuration
def setup_logging():
    """Setup enhanced logging with rotation"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create formatters
    detailed_formatter = logging.Formatter(log_format)
    simple_formatter = logging.Formatter('%(levelname)s: %(message)s')
    
    # Setup file handler with rotation
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    
    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Setup root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logging()

def validate_config():
    """Validate configuration with detailed error reporting"""
    missing_vars = []
    invalid_vars = []
    
    required_vars = {
        'GEMINI_API_KEY': GEMINI_API_KEY,
        'TWITTER_API_KEY': TWITTER_API_KEY,
        'TWITTER_API_SECRET': TWITTER_API_SECRET,
        'TWITTER_ACCESS_TOKEN': TWITTER_ACCESS_TOKEN,
        'TWITTER_ACCESS_TOKEN_SECRET': TWITTER_ACCESS_TOKEN_SECRET,
        'TWITTER_USERNAME': TWITTER_USERNAME,
        'TWITTER_PASSWORD': TWITTER_PASSWORD
    }
    
    # Check for missing variables
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing_vars.append(var_name)
        elif var_name.endswith('_KEY') or var_name.endswith('_SECRET') or var_name.endswith('_TOKEN'):
            # Basic validation for API keys/tokens
            if len(var_value.strip()) < 10:
                invalid_vars.append(f"{var_name} (too short)")
    
    # Optional variables with warnings
    optional_vars = {
        'TWITTER_BEARER_TOKEN': TWITTER_BEARER_TOKEN,
        'TWITTER_EMAIL': TWITTER_EMAIL,
        'BOT_USERNAME': BOT_USERNAME
    }
    
    for var_name, var_value in optional_vars.items():
        if not var_value:
            logger.warning(f"Optional variable {var_name} not set")
    
    # Report issues
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    if invalid_vars:
        error_msg = f"Invalid environment variables: {', '.join(invalid_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Additional validations
    if TARGET_ACCOUNTS and len(TARGET_ACCOUNTS) > 0:
        valid_accounts = [acc.strip() for acc in TARGET_ACCOUNTS if acc.strip()]
        if valid_accounts:
            logger.info(f"Target accounts configured: {len(valid_accounts)}")
        else:
            logger.warning("TARGET_ACCOUNTS is set but contains no valid accounts")
    
    logger.info("Configuration validated successfully")
    logger.info(f"Bot username: {BOT_USERNAME}")
    logger.info(f"Twitter username: {TWITTER_USERNAME}")

def get_bot_status():
    """Get current bot status and configuration summary"""
    return {
        'timestamp': datetime.now().isoformat(),
        'bot_username': BOT_USERNAME,
        'twitter_username': TWITTER_USERNAME,
        'has_gemini_key': bool(GEMINI_API_KEY),
        'has_twitter_api': bool(TWITTER_API_KEY and TWITTER_API_SECRET),
        'has_twitter_access': bool(TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET),
        'has_scraping_creds': bool(TWITTER_USERNAME and TWITTER_PASSWORD),
        'target_accounts_count': len([acc for acc in TARGET_ACCOUNTS if acc.strip()]),
        'log_file': LOG_FILE,
        'state_dir': STATE_DIR,
        'media_dir': MEDIA_DIR
    }

def clear_bot_cache():
    """Clear all bot cache and state files"""
    import glob
    
    cache_files = [
        'accounts.db',
        'bot.log',
        'timeline_tweets.xlsx'
    ]
    
    state_files = glob.glob(os.path.join(STATE_DIR, '*'))
    
    cleared_files = []
    for file_path in cache_files + state_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                cleared_files.append(file_path)
        except Exception as e:
            logger.warning(f"Could not clear {file_path}: {e}")
    
    if cleared_files:
        logger.info(f"Cleared cache files: {', '.join(cleared_files)}")
    else:
        logger.info("No cache files to clear")

def log_bot_startup():
    """Log bot startup information"""
    logger.info("=" * 60)
    logger.info("Twitter Bot Starting Up")
    logger.info("=" * 60)
    
    status = get_bot_status()
    logger.info(f"Timestamp: {status['timestamp']}")
    logger.info(f"Bot Username: {status['bot_username']}")
    logger.info(f"Twitter Username: {status['twitter_username']}")
    logger.info(f"Gemini API: {'✓' if status['has_gemini_key'] else '✗'}")
    logger.info(f"Twitter API: {'✓' if status['has_twitter_api'] else '✗'}")
    logger.info(f"Twitter Access: {'✓' if status['has_twitter_access'] else '✗'}")
    logger.info(f"Scraping Credentials: {'✓' if status['has_scraping_creds'] else '✗'}")
    logger.info(f"Target Accounts: {status['target_accounts_count']}")
    logger.info("=" * 60)

if __name__ == "__main__":
    # Test configuration
    try:
        validate_config()
        log_bot_startup()
        print("✅ Configuration is valid!")
    except Exception as e:
        print(f"❌ Configuration error: {e}")
