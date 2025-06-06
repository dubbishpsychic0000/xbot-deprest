# Modular AI-Powered Twitter Bot

A clean, modular Python bot that fetches tweets, generates AI-powered responses using Gemini, and posts them via Twitter API.

## Features

- **Modular Design**: Each component runs independently for easy testing
- **Multiple Modes**: Reply, quote tweet, thread, standalone tweet, media processing
- **AI-Powered**: Uses Google Gemini for intelligent content generation  
- **Rate Limiting**: Built-in delays and Twitter API rate limit handling
- **Media Support**: Download and process tweet media
- **Scheduling**: GitHub Actions workflow for automated posting
- **Clean Logging**: Comprehensive error handling and logging

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env` template and add your API keys:
- Twitter API credentials (X Developer Essential Plan)
- Google Gemini API key

### 3. Test Individual Modules
```bash
# Test tweet scraping
python twscrape_client.py

# Test AI generation  
python ai_generator.py

# Test posting
python poster.py

# Test media handling
python media_handler.py
```

## Usage

### CLI Commands

```bash
# Reply to recent tweets from a user
python main.py reply --target "username" --limit 5

# Quote tweet search results
python main.py quote --query "#AI" --limit 3

# Generate and post a thread
python main.py thread --topic "AI trends" --tweets 4

# Post standalone tweet
python main.py standalone --topic "Machine learning"

# Process tweets with media
python main.py media --target "username"
```

### Module Usage

Each module can be imported and used independently:

```python
# Fetch tweets
from twscrape_client import fetch_tweets
tweets = await fetch_tweets("user", "elonmusk", 10)

# Generate AI content
from ai_generator import generate_ai_content
reply = await generate_ai_content("reply", "Original tweet text")

# Post to Twitter
from poster import post_content
tweet_id = post_content("tweet", "Hello world!")
```

## Automation

Use the included GitHub Actions workflow (`scheduler.yml`) to run the bot automatically:

1. Add secrets to your GitHub repository
2. Configure the schedule in the workflow file
3. The bot will run automatically and upload logs as artifacts

## File Structure

- `config.py` - Configuration and environment setup
- `twscrape_client.py` - Tweet fetching via twscrape
- `media_handler.py` - Media download and processing
- `ai_generator.py` - AI content generation via Gemini
- `poster.py` - Twitter API posting functionality
- `main.py` - CLI interface and bot orchestration
- `scheduler.yml` - GitHub Actions automation
- `.env` - Environment variables (create from template)

## Error Handling

All modules include comprehensive error handling:
- API rate limiting and timeouts
- Network connectivity issues  
- Invalid responses and malformed data
- Missing configuration or credentials

Errors are logged to both console and `bot.log` file.

## Rate Limits

The bot respects Twitter API rate limits:
- 2-second delays between posts
- Built-in tweepy rate limit handling
- Configurable delays in `config.py`

## Security

- No hardcoded credentials
- Environment variable configuration
- Secure API key handling
- GitHub secrets integration