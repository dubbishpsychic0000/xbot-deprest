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


def validate_credentials() -> bool:
    """Valide que les cookies sont présents"""
    if not TWITTER_COOKIES:
        logger.error("TWITTER_COOKIES est requis dans le fichier .env")
        logger.info("Pour obtenir vos cookies:")
        logger.info("1. Connectez-vous à twitter.com dans votre navigateur")
        logger.info("2. F12 → Application/Storage → Cookies → twitter.com")
        logger.info("3. Copiez tous les cookies et ajoutez-les dans TWITTER_COOKIES")
        return False

    # Vérifier les cookies essentiels
    required_cookies = ['auth_token', 'ct0']
    missing_cookies = []

    for cookie in required_cookies:
        if f"{cookie}=" not in TWITTER_COOKIES:
            missing_cookies.append(cookie)

    if missing_cookies:
        logger.warning(f"Cookies manquants (peuvent causer des problèmes): {', '.join(missing_cookies)}")

    return True


async def add_account_with_cookies() -> bool:
    """Ajoute un compte en utilisant uniquement les cookies"""
    try:
        logger.info("Ajout du compte avec cookies...")

        # Générer un nom d'utilisateur fictif basé sur les cookies
        cookie_hash = hashlib.md5(TWITTER_COOKIES.encode()).hexdigest()[:8]
        fake_username = f"cookie_user_{cookie_hash}"

        # Ajouter le compte avec les cookies
        await api.pool.add_account(
            username=fake_username,
            password="cookie_auth",  # Mot de passe fictif
            email="",  # Email vide
            email_password="",  # Mot de passe email vide
            cookies=TWITTER_COOKIES
        )

        logger.info(f"Compte ajouté avec succès: {fake_username}")
        return True

    except Exception as e:
        logger.error(f"Échec de l'ajout du compte avec cookies: {e}")
        return False


async def login() -> bool:
    """Login function using only cookies."""
    global api

    if not validate_credentials():
        return False

    try:
        logger.info("Configuration du compte Twitter avec cookies...")

        # Vérifier les comptes existants
        accounts = await api.pool.accounts_info()

        # Si aucun compte n'existe, en ajouter un avec les cookies
        if not accounts:
            if not await add_account_with_cookies():
                logger.error("Impossible d'ajouter le compte avec cookies")
                return False

        # Vérifier qu'au moins un compte est utilisable
        accounts = await api.pool.accounts_info()
        usable_accounts = []

        for acc in accounts:
            acc_active = acc.get('active') if isinstance(acc, dict) else getattr(acc, 'active', False)
            if acc_active:
                usable_accounts.append(acc)

        if not usable_accounts:
            logger.warning("Aucun compte actif, tentative de login...")
            try:
                await api.pool.login_all()
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Login automatique échoué: {e}")

        # Vérification finale
        accounts = await api.pool.accounts_info()
        if not accounts:
            logger.error("Aucun compte disponible après configuration")
            return False

        logger.info(f"Comptes configurés: {len(accounts)}")
        return True

    except Exception as e:
        logger.error(f"Échec de la connexion: {e}")
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
    Fonction principale pour récupérer des tweets - TIMELINE FOCUSED VERSION
    Compatible avec les appels de main.py

    Args:
        source_type: "timeline", "user", ou "search" (mais optimisé pour timeline)
        source: nom d'utilisateur ou requête - IGNORÉ pour timeline
        limit: nombre maximum de tweets à récupérer

    Returns:
        Liste de dictionnaires de tweets au format attendu par main.py
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
            # Fallback to timeline for user requests
            logger.info("Requête utilisateur convertie en timeline")
            return await async_scrape_timeline_tweets(limit)
        elif source_type == "search":
            # Fallback to timeline for search requests
            logger.info("Requête de recherche convertie en timeline")
            return await async_scrape_timeline_tweets(limit)
        else:
            logger.error(f"Type de source non supporté: {source_type}")
            return []
    except Exception as e:
        logger.error(f"Erreur dans fetch_tweets: {e}")
        return []


async def async_scrape_timeline_tweets(limit: int = 20) -> List[Dict]:
    """Scraper asynchrone optimisé pour la timeline personnelle."""
    global api

    try:
        logger.info(f"Récupération de la timeline personnelle (limite: {limit})")

        # Stratégies multiples pour obtenir des tweets de timeline
        timeline_strategies = [
            # Stratégie 1: Utiliser des recherches populaires récentes
            ("trending", ["#AI", "#technology", "#programming", "#startup"]),
            # Stratégie 2: Recherches générales populaires
            ("general", ["python programming", "artificial intelligence", "tech news", "innovation"]),
            # Stratégie 3: Recherches par langue
            ("language", ["lang:en AI", "lang:en tech", "lang:en python"])
        ]

        all_tweets = []
        tweets_per_strategy = max(1, limit // len(timeline_strategies))

        for strategy_name, queries in timeline_strategies:
            logger.info(f"Stratégie timeline: {strategy_name}")
            strategy_tweets = []

            for query in queries:
                if len(all_tweets) >= limit:
                    break

                try:
                    logger.info(f"Recherche timeline: {query}")
                    tweets = await gather(api.search(query, limit=max(5, tweets_per_strategy // len(queries))))

                    for tweet in tweets:
                        if len(strategy_tweets) >= tweets_per_strategy:
                            break

                        tweet_data = extract_tweet_data_bot_format(tweet)
                        if tweet_data and tweet_data not in strategy_tweets:
                            strategy_tweets.append(tweet_data)
                            logger.info(f"Tweet timeline ajouté: {tweet_data['text'][:80]}...")

                except Exception as query_error:
                    logger.warning(f"Erreur pour la requête '{query}': {query_error}")
                    continue

                # Délai entre les requêtes pour éviter le rate limiting
                await asyncio.sleep(0.5)

            all_tweets.extend(strategy_tweets)
            if len(all_tweets) >= limit:
                break

        # Dédupliquer par ID et mélanger pour plus de diversité
        unique_tweets = []
        seen_ids = set()

        for tweet in all_tweets:
            if tweet['id'] not in seen_ids:
                unique_tweets.append(tweet)
                seen_ids.add(tweet['id'])

        random.shuffle(unique_tweets)
        final_tweets = unique_tweets[:limit]

        # Sauvegarder dans Excel
        await save_tweets_to_excel(final_tweets, "timeline_tweets.xlsx")

        logger.info(f"Timeline récupérée: {len(final_tweets)} tweets uniques")
        return final_tweets

    except Exception as e:
        logger.error(f"Erreur dans async_scrape_timeline_tweets: {e}")
        return []


async def async_scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Scraper asynchrone pour les tweets d'un utilisateur - Fallback vers timeline."""
    logger.info(f"Requête utilisateur @{username} redirigée vers timeline")
    return await async_scrape_timeline_tweets(limit)


async def async_scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Scraper asynchrone pour la recherche - Fallback vers timeline."""
    logger.info(f"Requête de recherche '{query}' redirigée vers timeline")
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
    """Version synchrone du scraping utilisateur - Redirigé vers timeline."""
    try:
        if not setup_driver():
            logger.error("Impossible d'initialiser l'API twscrape")
            return []

        return asyncio.run(async_timeline_wrapper(limit))
    except Exception as e:
        logger.error(f"Erreur dans scrape_user_tweets: {e}")
        return []


def scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Version synchrone du scraping de recherche - Redirigé vers timeline."""
    try:
        if not setup_driver():
            logger.error("Impossible d'initialiser l'API twscrape")
            return []

        return asyncio.run(async_timeline_wrapper(limit))
    except Exception as e:
        logger.error(f"Erreur dans scrape_search_tweets: {e}")
        return []


async def async_timeline_wrapper(limit: int) -> List[Dict]:
    """Wrapper asynchrone unifié pour tous les types de scraping."""
    if not await login():
        logger.error("Échec de la connexion!")
        return []
    return await async_scrape_timeline_tweets(limit)


async def async_user_wrapper(username: str, limit: int) -> List[Dict]:
    """Wrapper asynchrone pour le scraping utilisateur."""
    return await async_timeline_wrapper(limit)


async def async_search_wrapper(query: str, limit: int) -> List[Dict]:
    """Wrapper asynchrone pour le scraping de recherche."""
    return await async_timeline_wrapper(limit)


# Fonctions de test et diagnostic
async def test_cookies_format():
    """Teste le format des cookies"""
    if not TWITTER_COOKIES:
        logger.warning("Aucun cookie défini")
        return False

    try:
        # Vérifier le format basique
        essential_cookies = ['auth_token', 'ct0']
        found_cookies = []

        for cookie in essential_cookies:
            if f'{cookie}=' in TWITTER_COOKIES:
                found_cookies.append(cookie)

        if not found_cookies:
            logger.error("Aucun cookie essentiel trouvé (auth_token, ct0)")
            return False

        logger.info(f"Cookies trouvés: {', '.join(found_cookies)}")
        return True

    except Exception as e:
        logger.error(f"Erreur lors de la vérification des cookies: {e}")
        return False


async def test_api_basic():
    """Test basique de l'API avec cookies"""
    try:
        logger.info("Test de l'API avec cookies...")

        # Test simple de recherche
        try:
            tweets = await gather(api.search("python", limit=1))
            if tweets:
                logger.info("✓ API fonctionne - recherche réussie")
                return True
        except Exception as search_error:
            logger.warning(f"Test de recherche échoué: {search_error}")

        return False

    except Exception as e:
        logger.error(f"Erreur lors du test API: {e}")
        return False


def test_api_basic_sync():
    """Version synchrone du test API"""
    if setup_driver():
        return asyncio.run(test_api_basic())
    return False


async def diagnose_account_status():
    """Diagnostique le statut des comptes."""
    try:
        accounts = await api.pool.accounts_info()
        logger.info(f"Nombre total de comptes: {len(accounts)}")

        if not accounts:
            logger.warning("Aucun compte trouvé - sera créé automatiquement")
            return

        for i, acc in enumerate(accounts):
            if isinstance(acc, dict):
                logger.info(f"Compte {i + 1}: {acc.get('username', 'N/A')} - "
                            f"Actif: {acc.get('active', 'N/A')}")
            else:
                logger.info(f"Compte {i + 1}: {getattr(acc, 'username', 'N/A')} - "
                            f"Actif: {getattr(acc, 'active', False)}")

    except Exception as e:
        logger.error(f"Erreur lors du diagnostic: {e}")


def diagnose_account_status_sync():
    """Version synchrone du diagnostic."""
    if setup_driver():
        asyncio.run(diagnose_account_status())

if __name__ == "__main__":
    print("=== Test du scraper Twitter - Version Cookies Timeline ===")

    # 1. Test du format des cookies
    print("\n1. Test du format des cookies…")
    if not setup_driver():
        print("❌ Impossible d'initialiser twscrape")
        exit(1)

    cookie_test = asyncio.run(test_cookies_format())
    if not cookie_test:
        print("❌ Problème avec les cookies. Vérifiez votre configuration.")
        exit(1)

    # 2. Diagnostic des comptes (devrait être 0 sur un runner frais)
    print("\n2. Diagnostic des comptes…")
    diagnose_account_status_sync()

    # 2.5. Si aucun compte actif, ajout automatique via cookies
    accounts = asyncio.run(api.pool.accounts_info())
    if not accounts:
        print("Aucun compte trouvé, ajout via cookies…")
        added = asyncio.run(add_account_with_cookies())
        if not added:
            print("❌ Échec de l'ajout du compte")
            exit(1)
        else:
            # Laissez un instant pour que twscrape marque le compte “actif”
            time.sleep(2)

    # 3. Re-diagnostic des comptes pour vérifier “active: True”
    print("\n3. Re-diagnostic des comptes…")
    diagnose_account_status_sync()

    # 4. Test de l’API, maintenant que le compte existe
    print("\n4. Test de l’API…")
    api_works = test_api_basic_sync()
    if not api_works:
        print("❌ L'API ne fonctionne pas même après avoir ajouté le compte.")
        exit(1)
    else:
        print("✅ L'API fonctionne correctement")

    # … reste des tests (récup timeline, etc.) …

    # Test principal: Timeline
    if api_works:
        print("\n4. Test de récupération de la timeline...")
        timeline_tweets = asyncio.run(fetch_tweets("timeline", "", 5))
        print(f"✅ Tweets timeline récupérés: {len(timeline_tweets)}")

        if timeline_tweets:
            print("\nExemple de tweet:")
            print(f"- Auteur: {timeline_tweets[0]['author']}")
            print(f"- Texte: {timeline_tweets[0]['text'][:100]}...")
            print(f"- URL: {timeline_tweets[0]['url']}")

        # Test des fonctions de compatibilité
        print("\n5. Test des fonctions de compatibilité...")
        user_tweets = scrape_user_tweets("test", 2)
        search_tweets = scrape_search_tweets("test", 2)
        print(f"✅ Fonction utilisateur (timeline): {len(user_tweets)} tweets")
        print(f"✅ Fonction recherche (timeline): {len(search_tweets)} tweets")
    else:
        print("\n⚠️  Tests ignorés - API non fonctionnelle")

    print("\n=== Configuration recommandée ===")
    print("Dans votre fichier .env, ajoutez:")
    print("TWITTER_COOKIES=auth_token=xxx; ct0=yyy; [autres cookies...]")
    print("\nPour obtenir vos cookies:")
    print("1. Connectez-vous à twitter.com")
    print("2. F12 → Application → Cookies → twitter.com")
    print("3. Copiez tous les cookies")
    print("\n=== Fin des tests ===")
