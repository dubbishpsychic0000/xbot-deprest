
import asyncio
import os
import hashlib
import json
import pickle
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import random
import time
import logging
import re

# Import twscrape - latest version
from twscrape import API, gather, Tweet, User
from twscrape.logger import set_log_level

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Fetch credentials from .env - Only cookies needed now
TWITTER_COOKIES = os.getenv("TWITTER_COOKIES", "")

# Global API instance
api = None


class TwitterScraperError(Exception):
    """Exception personnalisée pour le scraper Twitter"""
    pass


def setup_driver() -> bool:
    """Initialize twscrape API instance with anti-detection options."""
    global api
    try:
        logger.info("Initializing twscrape API...")

        # Initialize API with accounts database
        api = API("accounts.db")

        # Set debug level for troubleshooting
        set_log_level("INFO")  # Reduced logging for cleaner output

        logger.info("twscrape API initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize twscrape API: {e}")
        return False


def parse_cookies_string(cookies_string: str) -> Dict[str, str]:
    """Parse cookies string into dictionary format."""
    cookies_dict = {}
    if not cookies_string:
        return cookies_dict

    # Handle different cookie formats
    cookie_pairs = cookies_string.split(';')

    for pair in cookie_pairs:
        pair = pair.strip()
        if '=' in pair:
            key, value = pair.split('=', 1)
            cookies_dict[key.strip()] = value.strip()

    return cookies_dict


def validate_cookies_format(cookies_dict: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Validate that essential cookies are present and properly formatted."""
    essential_cookies = {
        'auth_token': 'Authentication token',
        'ct0': 'CSRF token', 
        'guest_id': 'Guest identifier'
    }

    missing_cookies = []
    for cookie, description in essential_cookies.items():
        if cookie not in cookies_dict or not cookies_dict[cookie]:
            missing_cookies.append(f"{cookie} ({description})")

    # Additional validation for cookie values
    if 'auth_token' in cookies_dict:
        auth_token = cookies_dict['auth_token']
        if len(auth_token) < 40 or not re.match(r'^[a-f0-9]+$', auth_token):
            logger.warning("auth_token format may be invalid")

    if 'ct0' in cookies_dict:
        ct0 = cookies_dict['ct0']
        if len(ct0) < 32 or not re.match(r'^[a-f0-9]+$', ct0):
            logger.warning("ct0 format may be invalid")

    return len(missing_cookies) == 0, missing_cookies


def validate_credentials() -> bool:
    """Valide que les cookies sont présents et bien formatés"""
    if not TWITTER_COOKIES:
        logger.error("TWITTER_COOKIES est requis dans le fichier .env")
        logger.info("Pour obtenir vos cookies:")
        logger.info("1. Connectez-vous à twitter.com dans votre navigateur")
        logger.info("2. F12 → Application/Storage → Cookies → twitter.com")
        logger.info("3. Copiez tous les cookies et ajoutez-les dans TWITTER_COOKIES")
        logger.info("Format: auth_token=xxx; ct0=yyy; guest_id=zzz; ...")
        return False

    # Parse and validate cookies
    cookies_dict = parse_cookies_string(TWITTER_COOKIES)
    is_valid, missing_cookies = validate_cookies_format(cookies_dict)

    if not is_valid:
        logger.error(f"Cookies manquants ou invalides: {', '.join(missing_cookies)}")
        return False

    logger.info("✓ Cookies validés avec succès")
    return True


async def add_account_with_cookies() -> bool:
    """Ajoute un compte en utilisant uniquement les cookies - Version améliorée"""
    try:
        logger.info("Ajout du compte avec cookies (version améliorée)...")

        # Parse cookies into dictionary
        cookies_dict = parse_cookies_string(TWITTER_COOKIES)

        # Validate cookies format
        is_valid, missing_cookies = validate_cookies_format(cookies_dict)
        if not is_valid:
            logger.error(f"Impossible d'ajouter le compte - cookies invalides: {', '.join(missing_cookies)}")
            return False

        # Generate a unique username based on auth_token
        auth_token = cookies_dict.get('auth_token', '')
        if auth_token:
            # Use first 8 chars of auth_token for uniqueness
            username_suffix = auth_token[:8]
        else:
            # Fallback to cookie hash
            cookie_hash = hashlib.md5(TWITTER_COOKIES.encode()).hexdigest()[:8]
            username_suffix = cookie_hash

        fake_username = f"cookie_user_{username_suffix}"
        fake_email = f"{fake_username}@cookies.local"

        # Check if account already exists
        existing_accounts = await api.pool.accounts_info()
        for acc in existing_accounts:
            acc_username = acc.get('username') if isinstance(acc, dict) else getattr(acc, 'username', '')
            if acc_username == fake_username:
                logger.info(f"Compte existant trouvé: {fake_username}")
                # Try to reactivate if inactive
                try:
                    await api.pool.set_active(fake_username, True)
                    logger.info(f"Compte {fake_username} réactivé")
                except:
                    pass
                return True

        # Add new account with enhanced cookie format
        try:
            await api.pool.add_account(
                username=fake_username,
                password="cookie_based_auth",  # Placeholder password
                email=fake_email,
                email_password="",
                cookies=TWITTER_COOKIES
            )

            logger.info(f"✓ Compte ajouté avec succès: {fake_username}")

            # Wait a moment for the account to be processed
            await asyncio.sleep(1)

            # Verify account was added and try to activate it
            accounts = await api.pool.accounts_info()
            for acc in accounts:
                acc_username = acc.get('username') if isinstance(acc, dict) else getattr(acc, 'username', '')
                if acc_username == fake_username:
                    try:
                        await api.pool.set_active(fake_username, True)
                        logger.info(f"✓ Compte {fake_username} activé")
                    except Exception as activate_error:
                        logger.warning(f"Impossible d'activer le compte: {activate_error}")
                    break

            return True

        except Exception as add_error:
            logger.error(f"Erreur lors de l'ajout du compte: {add_error}")

            # Try alternative method with individual cookie values
            try:
                logger.info("Tentative d'ajout avec méthode alternative...")

                # Create a more structured cookie format
                structured_cookies = []
                for key, value in cookies_dict.items():
                    structured_cookies.append(f"{key}={value}")
                structured_cookie_string = "; ".join(structured_cookies)

                await api.pool.add_account(
                    username=fake_username,
                    password="cookie_auth_alt",
                    email=fake_email,
                    email_password="",
                    cookies=structured_cookie_string
                )

                logger.info(f"✓ Compte ajouté avec méthode alternative: {fake_username}")
                return True

            except Exception as alt_error:
                logger.error(f"Méthode alternative échouée: {alt_error}")
                return False

    except Exception as e:
        logger.error(f"Échec de l'ajout du compte avec cookies: {e}")
        return False


async def ensure_active_account() -> bool:
    """Assure qu'au moins un compte est actif"""
    try:
        accounts = await api.pool.accounts_info()

        # Check for active accounts
        active_accounts = []
        for acc in accounts:
            is_active = acc.get('active') if isinstance(acc, dict) else getattr(acc, 'active', False)
            if is_active:
                active_accounts.append(acc)

        if active_accounts:
            logger.info(f"✓ {len(active_accounts)} compte(s) actif(s) trouvé(s)")
            return True

        # Try to activate existing accounts
        if accounts:
            logger.info("Tentative d'activation des comptes existants...")
            for acc in accounts:
                acc_username = acc.get('username') if isinstance(acc, dict) else getattr(acc, 'username', '')
                try:
                    await api.pool.set_active(acc_username, True)
                    logger.info(f"Compte {acc_username} activé")
                    return True
                except Exception as e:
                    logger.warning(f"Impossible d'activer {acc_username}: {e}")

            # Try login_all as last resort
            try:
                logger.info("Tentative de login général...")
                await api.pool.login_all()
                await asyncio.sleep(2)

                # Re-check for active accounts
                accounts = await api.pool.accounts_info()
                for acc in accounts:
                    is_active = acc.get('active') if isinstance(acc, dict) else getattr(acc, 'active', False)
                    if is_active:
                        logger.info("✓ Au moins un compte activé par login général")
                        return True
            except Exception as login_error:
                logger.warning(f"Login général échoué: {login_error}")

        return False

    except Exception as e:
        logger.error(f"Erreur lors de la vérification des comptes actifs: {e}")
        return False


async def login() -> bool:
    """Login function using only cookies - Enhanced version."""
    global api

    if not validate_credentials():
        return False

    try:
        logger.info("Configuration du compte Twitter avec cookies (version améliorée)...")

        # Check existing accounts first
        accounts = await api.pool.accounts_info()
        logger.info(f"Comptes existants trouvés: {len(accounts)}")

        # If no accounts exist, add one with cookies
        if not accounts:
            logger.info("Aucun compte existant - ajout via cookies...")
            if not await add_account_with_cookies():
                logger.error("Impossible d'ajouter le compte avec cookies")
                return False
        else:
            # Try to ensure at least one account is active
            if not await ensure_active_account():
                logger.warning("Aucun compte actif - tentative d'ajout d'un nouveau compte...")
                if not await add_account_with_cookies():
                    logger.error("Impossible d'ajouter un nouveau compte")
                    return False

        # Final verification
        accounts = await api.pool.accounts_info()
        if not accounts:
            logger.error("Aucun compte disponible après configuration")
            return False

        # Check for at least one active account
        active_count = 0
        for acc in accounts:
            is_active = acc.get('active') if isinstance(acc, dict) else getattr(acc, 'active', False)
            if is_active:
                active_count += 1

        if active_count == 0:
            logger.warning("Aucun compte actif détecté, mais poursuite du processus...")

        logger.info(f"✓ Configuration terminée: {len(accounts)} comptes, {active_count} actifs")
        return True

    except Exception as e:
        logger.error(f"Échec de la connexion: {e}")
        return False


def is_high_quality_tweet(tweet_data: Dict) -> bool:
    """Filter for high-quality tweets suitable for cultural engagement - films, music, philosophy, books."""
    try:
        text = tweet_data.get('text', '').lower()

        # Cultural keywords - Films, Music, Philosophy, Books
        cultural_keywords = [
            # Cinema & Films
            'film', 'movie', 'cinema', 'director', 'kubrick', 'tarkovsky', 'nolan', 'scorsese', 'lynch', 
            'wes anderson', 'coen brothers', 'hitchcock', 'kurosawa', 'fellini', 'bergman', 'godard',
            'cinephile', 'cinematography', 'screenplay', 'criterion', 'arthouse', 'film noir',
            'masterpiece', 'favorite film', 'best movie', 'movie recommendation', 'film analysis',

            # Music
            'music', 'album', 'song', 'artist', 'musician', 'radiohead', 'pink floyd', 'björk', 
            'kendrick', 'brian eno', 'miles davis', 'beethoven', 'bach', 'jazz', 'classical',
            'vinyl', 'soundtrack', 'composition', 'melody', 'harmony', 'lyrics', 'nowplaying',
            'musicislife', 'favorite album', 'music recommendation', 'this song', 'beautiful music',

            # Philosophy
            'philosophy', 'philosopher', 'existentialism', 'stoicism', 'nihilism', 'metaphysics',
            'nietzsche', 'kant', 'plato', 'aristotle', 'camus', 'sartre', 'kierkegaard', 'heidegger',
            'foucault', 'wittgenstein', 'consciousness', 'free will', 'meaning of life', 'ethics',
            'morality', 'existence', 'absurd', 'wisdom', 'truth', 'reality', 'being', 'time',

            # Books & Literature
            'book', 'novel', 'literature', 'author', 'writer', 'reading', 'bookworm', 'booklover',
            'murakami', 'dostoevsky', 'kafka', 'orwell', 'toni morrison', 'virginia woolf', 'borges',
            'calvino', 'nabokov', 'proust', 'joyce', 'hemingway', 'book recommendation', 'favorite book',
            'poetry', 'poem', 'poet', 'verse', 'literary', 'classic', 'fiction', 'non-fiction',
            'memoir', 'biography', 'essay', 'this book changed', 'must read', 'reading list'
        ]

        has_cultural_keywords = any(keyword in text for keyword in cultural_keywords)

        # Quality filters
        is_long_enough = len(text) > 30
        not_spam = not any(spam_word in text for spam_word in ['buy now', 'click here', 'free money', 'get rich', 'follow for follow'])
        not_too_many_hashtags = text.count('#') <= 4
        not_too_many_mentions = text.count('@') <= 3
        no_excessive_caps = sum(1 for c in text if c.isupper()) / len(text) < 0.3 if text else False

        # Cultural engagement indicators
        has_emotional_connection = any(phrase in text for phrase in [
            'changed my life', 'made me cry', 'beautiful', 'masterpiece', 'incredible', 
            'amazing', 'profound', 'moving', 'stunning', 'brilliant', 'favorite', 
            'love this', 'obsessed with', 'can\'t stop', 'highly recommend'
        ])

        return (has_cultural_keywords and is_long_enough and not_spam and 
                not_too_many_hashtags and not_too_many_mentions and no_excessive_caps) or has_emotional_connection

    except Exception as e:
        logger.warning(f"Error in quality filter: {e}")
        return False


def extract_tweet_data_bot_format(tweet: Tweet) -> Optional[Dict]:
    """Extract tweet data and return in bot-compatible format."""
    try:
        # Vérifier que le tweet a du contenu
        tweet_text = getattr(tweet, 'rawContent', '') or getattr(tweet, 'text', '')
        if not tweet_text or not tweet_text.strip():
            return None

        # Timestamp
        created_at = datetime.now().isoformat()
        if hasattr(tweet, 'date') and tweet.date:
            created_at = tweet.date.isoformat()

        # Tweet ID et URL
        tweet_id = str(tweet.id) if hasattr(tweet, 'id') and tweet.id else None
        tweet_url = getattr(tweet, 'url', '')

        if not tweet_id:
            # Générer un ID de fallback
            fallback_hash = hashlib.md5(f"{tweet_text}_{created_at}".encode()).hexdigest()[:16]
            tweet_id = fallback_hash
            if not tweet_url:
                tweet_url = f"https://x.com/status/{fallback_hash}"

        # Auteur
        author = "unknown"
        if hasattr(tweet, 'user') and tweet.user:
            if hasattr(tweet.user, 'username') and tweet.user.username:
                author = tweet.user.username
            elif hasattr(tweet.user, 'displayname') and tweet.user.displayname:
                author = tweet.user.displayname

        # Médias
        media = []
        if hasattr(tweet, "media") and tweet.media:
            # If tweet.media is already a list, use it as-is;
            # otherwise wrap the single object in a list.
            if isinstance(tweet.media, list):
                media_items = tweet.media
            else:
                media_items = [tweet.media]

            for media_item in media_items:
                media_url = getattr(media_item, "mediaUrl", None) or getattr(media_item, "url", None)
                if media_url:
                    media.append(media_url)

        return {
            "id": tweet_id,
            "text": tweet_text.strip(),
            "url": tweet_url,
            "created_at": created_at,
            "author": author,
            "media": media
        }

    except Exception as e:
        logger.error(f"Erreur lors de l'extraction des données du tweet: {e}")
        return None


async def fetch_tweets(source_type: str, source: str, limit: int = 20) -> List[Dict]:
    """
    Fonction principale pour récupérer des tweets - CULTURAL CONTENT FOCUSED VERSION
    Compatible avec les appels de main.py
    """
    global api

    # Initialiser l'API si nécessaire
    if api is None:
        if not setup_driver():
            logger.error("Impossible d'initialiser l'API twscrape")
            return []

    # Se connecter si nécessaire
    if not await login():
        logger.error("Échec de la connexion à Twitter")
        return []

    try:
        if source_type == "timeline":
            return await async_scrape_timeline_tweets(limit)
        elif source_type == "user":
            # Fallback to cultural timeline for user requests
            logger.info("Requête utilisateur convertie en timeline culturelle")
            return await async_scrape_timeline_tweets(limit)
        elif source_type == "search":
            # Fallback to cultural timeline for search requests
            logger.info("Requête de recherche convertie en timeline culturelle")
            return await async_scrape_timeline_tweets(limit)
        else:
            logger.error(f"Type de source non supporté: {source_type}")
            return []
    except Exception as e:
        logger.error(f"Erreur dans fetch_tweets: {e}")
        return []


async def async_scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """Scraper asynchrone optimisé pour le contenu culturel - FILMS, MUSIQUE, PHILOSOPHIE, LIVRES."""
    try:
        logger.info(f"Récupération de contenu culturel (limite: {limit})")

        # Utiliser la nouvelle méthode directe pour contenu culturel
        tweets = await get_cultural_tweets_direct(limit)

        if tweets:
            # Sauvegarder dans Excel
            await save_tweets_to_excel(tweets, "cultural_tweets.xlsx")
            logger.info(f"Contenu culturel récupéré: {len(tweets)} tweets")
        else:
            logger.warning("Aucun tweet culturel récupéré")

        return tweets

    except Exception as e:
        logger.error(f"Erreur dans async_scrape_timeline_tweets: {e}")
        return []


async def async_scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Scraper asynchrone pour les tweets d'un utilisateur - Fallback vers contenu culturel."""
    logger.info(f"Requête utilisateur @{username} redirigée vers contenu culturel")
    return await async_scrape_timeline_tweets(limit)


async def async_scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Scraper asynchrone pour la recherche - Fallback vers contenu culturel."""
    logger.info(f"Requête de recherche '{query}' redirigée vers contenu culturel")
    return await async_scrape_timeline_tweets(limit)


async def save_tweets_to_excel(tweets_data: List[Dict], filename: str):
    """Sauvegarde les tweets dans un fichier Excel."""
    if not tweets_data:
        return

    try:
        # Convertir au format Excel
        excel_data = []
        for tweet in tweets_data:
            media_str = ', '.join(tweet.get('media', [])) if tweet.get('media') else "No Images"
            excel_data.append([
                tweet.get('text', ''),
                tweet.get('created_at', '').split('T')[0],
                tweet.get('url', ''),
                media_str
            ])

        df = pd.DataFrame(excel_data, columns=["Tweet", "Date", "Link", "Images"])
        df.to_excel(filename, index=False)
        logger.info(f"Tweets sauvegardés dans {filename}")

    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde Excel: {e}")


# COMPATIBILITÉ: Fonctions synchrones pour la compatibilité avec l'ancien code
def scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Version synchrone du scraping utilisateur - Redirigé vers contenu culturel."""
    try:
        if not setup_driver():
            logger.error("Impossible d'initialiser l'API twscrape")
            return []

        return asyncio.run(async_cultural_wrapper(limit))
    except Exception as e:
        logger.error(f"Erreur dans scrape_user_tweets: {e}")
        return []


def scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Version synchrone du scraping de recherche - Redirigé vers contenu culturel."""
    try:
        if not setup_driver():
            logger.error("Impossible d'initialiser l'API twscrape")
            return []

        return asyncio.run(async_cultural_wrapper(limit))
    except Exception as e:
        logger.error(f"Erreur dans scrape_search_tweets: {e}")
        return []


async def get_cultural_tweets_direct(limit: int = 20) -> List[Dict]:
    """Récupère les tweets culturels directement - Films, Musique, Philosophie, Livres."""
    global api

    try:
        # Cultural search queries with high engagement - focused on Films, Music, Philosophy, Books
        cultural_queries = [
            # Cinema & Films
            "(film OR movie OR cinema OR director OR Kubrick OR Tarkovsky OR Nolan OR Scorsese OR Lynch OR #cinephile OR #filmlover OR \"this movie changed my life\" OR \"favorite movie of all time\" OR \"best film ending\" OR \"movies that made me think\") min_faves:30 min_retweets:5 -filter:replies -is:retweet lang:en",

            # Music
            "(music OR \"music that changed my life\" OR album OR \"album recommendation\" OR #nowplaying OR #musicislife OR soundtrack OR lyrics OR Radiohead OR \"Pink Floyd\" OR Björk OR Kendrick OR Eno OR \"this song speaks to me\" OR \"favorite album ever\") min_faves:25 min_retweets:3 -filter:replies -is:retweet lang:en",

            # Philosophy
            "(philosophy OR #philosophy OR existentialism OR stoicism OR Nietzsche OR Kant OR Plato OR Camus OR Kierkegaard OR \"Simone Weil\" OR Foucault OR \"life has no meaning\" OR \"what is consciousness\" OR \"free will\") min_faves:20 min_retweets:3 -filter:replies -is:retweet lang:en",

            # Books & Literature
            "(\"book recommendation\" OR novel OR \"reading list\" OR #booklover OR #amreading OR Murakami OR Dostoevsky OR Orwell OR \"Toni Morrison\" OR Kafka OR \"favorite book of all time\" OR \"this book changed my life\" OR \"books that broke me\" OR \"poetry that stayed with me\") min_faves:20 min_retweets:3 -filter:replies -is:retweet lang:en",

            # Mixed cultural content with high engagement
            "(\"changed my life\" OR masterpiece OR \"highly recommend\" OR \"can't stop thinking about\" OR \"obsessed with\") (film OR movie OR book OR album OR philosophy OR music) min_faves:15 min_retweets:2 -filter:replies -is:retweet lang:en",

            # Fallback: general high engagement cultural content
            "min_faves:50 min_retweets:10 -filter:replies -is:retweet lang:en",
        ]

        methods_to_try = [lambda query=q: api.search(query, limit=limit) for q in cultural_queries]

        # Add influential cultural accounts to target
        cultural_accounts = [
            # Film critics and cinephiles
            "RogerEbert", "filmstruck", "Letterboxd", "IndieWire", "TheFilmStage",
            # Music critics and accounts
            "pitchfork", "RollingStone", "NPRMusic", "StereoGum", "Consequence",
            # Literary accounts
            "nytbooks", "GuardianBooks", "LitHub", "poetryfound", "TheRumpus",
            # Philosophy accounts
            "philosophy_", "DailyPhilosophy", "PhilosophyMttrs", "thephilosopher", "TheSchoolLife"
        ]

        # Try account-specific searches first
        for account in cultural_accounts[:4]:  # Limit to first 4 to avoid rate limits
            try:
                logger.info(f"Fetching from cultural account: @{account}")
                account_tweets = await gather(api.user_tweets(account, limit=5))
                if account_tweets:
                    processed_tweets = []
                    for tweet in account_tweets:
                        tweet_data = extract_tweet_data_bot_format(tweet)
                        if tweet_data and is_high_quality_tweet(tweet_data):
                            processed_tweets.append(tweet_data)
                    if processed_tweets:
                        logger.info(f"✓ Found {len(processed_tweets)} quality cultural tweets from @{account}")
                        return processed_tweets[:limit]
            except Exception as account_error:
                logger.warning(f"Account fetch failed for @{account}: {account_error}")
                continue

        # Try the search methods as fallback
        for i, method in enumerate(methods_to_try):
            try:
                logger.info(f"Essai méthode de recherche culturelle {i+1}...")
                tweets = await gather(method())

                if tweets and len(tweets) > 0:
                    logger.info(f"✓ Méthode {i+1} réussie: {len(tweets)} tweets")
                    processed_tweets = []

                    for tweet in tweets:
                        tweet_data = extract_tweet_data_bot_format(tweet)
                        if tweet_data and is_high_quality_tweet(tweet_data):
                            processed_tweets.append(tweet_data)

                        if len(processed_tweets) >= limit:
                            break

                    if processed_tweets:
                        return processed_tweets[:limit]

            except Exception as method_error:
                logger.warning(f"Méthode {i+1} échouée: {method_error}")
                continue

        logger.warning("Toutes les méthodes de contenu culturel ont échoué")
        return []

    except Exception as e:
        logger.error(f"Erreur dans get_cultural_tweets_direct: {e}")
        return []


async def fetch_trending_cultural_tweets(limit: int = 10) -> List[Dict]:
    """Fetch tweets from trending cultural topics."""
    try:
        # Common trending cultural hashtags and topics
        trending_topics = [
            "#film", "#cinema", "#movies", "#music", "#nowplaying", "#philosophy",
            "#books", "#reading", "#literature", "#art", "#culture", "#poetry"
        ]

        all_tweets = []
        for topic in trending_topics[:4]:  # Limit to avoid rate limits
            try:
                query = f"{topic} min_faves:15 min_retweets:3 -filter:replies -is:retweet lang:en"
                tweets = await gather(api.search(query, limit=limit//4))

                for tweet in tweets:
                    tweet_data = extract_tweet_data_bot_format(tweet)
                    if tweet_data and is_high_quality_tweet(tweet_data):
                        all_tweets.append(tweet_data)

            except Exception as e:
                logger.warning(f"Failed to fetch from {topic}: {e}")
                continue

        return all_tweets[:limit]

    except Exception as e:
        logger.error(f"Error in fetch_trending_cultural_tweets: {e}")
        return []


async def async_cultural_wrapper(limit: int) -> List[Dict]:
    """Wrapper asynchrone unifié pour tous les types de scraping."""
    if not await login():
        logger.error("Échec de la connexion")
        return []

    return await get_cultural_tweets_direct(limit)


# Test functions
async def test_twscrape_client():
    """Test all twscrape client functionality."""
    logger.info("=== TESTING TWSCRAPE CLIENT ===")
    
    try:
        # Test 1: Initialize API
        logger.info("Test 1: Initializing API...")
        if not setup_driver():
            logger.error("❌ Failed to initialize API")
            return False
        logger.info("✅ API initialized successfully")

        # Test 2: Validate credentials
        logger.info("Test 2: Validating credentials...")
        if not validate_credentials():
            logger.error("❌ Credentials validation failed")
            return False
        logger.info("✅ Credentials validated")

        # Test 3: Login
        logger.info("Test 3: Testing login...")
        if not await login():
            logger.error("❌ Login failed")
            return False
        logger.info("✅ Login successful")

        # Test 4: Fetch cultural tweets
        logger.info("Test 4: Fetching cultural tweets...")
        tweets = await get_cultural_tweets_direct(5)
        if not tweets:
            logger.warning("⚠️ No cultural tweets fetched, but this might be normal")
        else:
            logger.info(f"✅ Fetched {len(tweets)} cultural tweets")
            for i, tweet in enumerate(tweets[:3], 1):
                logger.info(f"  Tweet {i}: {tweet['text'][:100]}...")

        # Test 5: Test main interface
        logger.info("Test 5: Testing main fetch_tweets interface...")
        tweets = await fetch_tweets("timeline", "", 3)
        if tweets:
            logger.info(f"✅ Main interface working: {len(tweets)} tweets")
        else:
            logger.warning("⚠️ Main interface returned no tweets")

        logger.info("=== ALL TESTS COMPLETED ===")
        return True

    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    """Run standalone tests"""
    print("Running twscrape_client tests...")
    
    async def run_tests():
        success = await test_twscrape_client()
        if success:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed!")
        return success

    # Run the tests
    asyncio.run(run_tests())
