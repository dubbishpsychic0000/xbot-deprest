import os
from dotenv import load_dotenv
import logging

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Twitter Configuration
MAX_TWEET_LENGTH = 280
RATE_LIMIT_DELAY = 2  # seconds between requests

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
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    logger.info("Configuration validated successfully")

if __name__ == "__main__":
    validate_config()
