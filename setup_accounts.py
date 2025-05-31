#!/usr/bin/env python3
"""
Quick setup script to add Twitter accounts for scraping
Run this BEFORE using the bot
Uses .env file for credentials
"""

import asyncio
import os
from twscrape import API
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_accounts():
    """Add Twitter accounts for scraping using .env credentials"""
    # Load environment variables from .env file
    load_dotenv()
    
    api = API()
    
    print("=" * 60)
    print("TWITTER BOT ACCOUNT SETUP")
    print("=" * 60)
    print("⚠️  IMPORTANT WARNINGS:")
    print("1. Use a SEPARATE Twitter account, not your main one!")
    print("2. This account may get rate-limited or suspended!")
    print("3. Don't use accounts with valuable data!")
    print("4. Keep your .env file secure and never commit it to git!")
    print("=" * 60)
    
    # Get account credentials from environment variables
    username = os.getenv('TWITTER_USERNAME')
    password = os.getenv('TWITTER_PASSWORD')
    email = os.getenv('TWITTER_EMAIL')
    email_password = os.getenv('TWITTER_EMAIL_PASSWORD', password)  # Default to Twitter password if not set
    
    # Validate that required credentials are present
    if not all([username, password, email]):
        print("❌ Missing required credentials in .env file!")
        print("\nRequired environment variables:")
        print("- TWITTER_USERNAME")
        print("- TWITTER_PASSWORD") 
        print("- TWITTER_EMAIL")
        print("- EMAIL_PASSWORD (optional, defaults to TWITTER_PASSWORD)")
        print("\nPlease check your .env file and try again.")
        return
    
    print(f"Setting up account for: {username}")
    print(f"Email: {email}")
    
    try:
        print("\nAdding account...")
        await api.pool.add_account(username, password, email, email_password)
        
        print("Logging in...")
        await api.pool.login_all()
        
        # Verify setup
        accounts = await api.pool.accounts_info()
        active_accounts = [acc for acc in accounts if acc.get('active', False)]
        
        print(f"\n✅ SUCCESS!")
        print(f"Total accounts: {len(accounts)}")
        print(f"Active accounts: {len(active_accounts)}")
        
        # Test with a simple search
        print("\nTesting with a simple search...")
        tweet_count = 0
        async for tweet in api.search("python", limit=3):
            tweet_count += 1
            print(f"✅ Found tweet: {tweet.rawContent[:50]}...")
        
        print(f"\n🎉 Setup complete! Found {tweet_count} test tweets.")
        print("You can now run your bot normally.")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check your .env file credentials are correct")
        print("2. Make sure the account isn't already logged in elsewhere")
        print("3. Try with a different account")
        print("4. Check if the account has 2FA enabled (not supported)")
        print("5. Ensure your .env file is in the same directory as this script")

if __name__ == "__main__":
    asyncio.run(setup_accounts())
