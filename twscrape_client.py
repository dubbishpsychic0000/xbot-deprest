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

# Fetch credentials from .env
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD") 
TWITTER_EMAIL = os.getenv("TWITTER_EMAIL", "")
TWITTER_EMAIL_PASSWORD = os.getenv("TWITTER_EMAIL_PASSWORD", "")
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
        set_log_level("DEBUG")  # Changé en DEBUG pour plus d'informations
        
        logger.info("twscrape API initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize twscrape API: {e}")
        return False

def validate_credentials() -> bool:
    """Valide que les credentials nécessaires sont présents"""
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        logger.error("TWITTER_USERNAME et TWITTER_PASSWORD sont requis dans le fichier .env")
        return False
    
    if not TWITTER_EMAIL:
        logger.warning("TWITTER_EMAIL manquant - peut causer des problèmes de vérification")
    
    return True

async def reset_account_if_needed(username: str) -> bool:
    """Reset un compte s'il est dans un état invalide"""
    try:
        # Supprimer le compte existant s'il pose problème
        await api.pool.delete_accounts(username)
        logger.info(f"Compte {username} supprimé pour reset")
        return True
    except Exception as e:
        logger.warning(f"Impossible de supprimer le compte {username}: {e}")
        return False

async def add_account_with_retry(max_retries: int = 3) -> bool:
    """Ajoute un compte avec retry logic"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentative {attempt + 1}/{max_retries} d'ajout du compte")
            
            if TWITTER_COOKIES:
                # Méthode privilégiée avec cookies
                await api.pool.add_account(
                    username=TWITTER_USERNAME,
                    password=TWITTER_PASSWORD,
                    email=TWITTER_EMAIL,
                    email_password=TWITTER_EMAIL_PASSWORD,
                    cookies=TWITTER_COOKIES
                )
                logger.info("Compte ajouté avec cookies")
            else:
                # Méthode avec login/password
                await api.pool.add_account(
                    username=TWITTER_USERNAME,
                    password=TWITTER_PASSWORD,
                    email=TWITTER_EMAIL,
                    email_password=TWITTER_EMAIL_PASSWORD
                )
                logger.info("Compte ajouté avec credentials")
            
            return True
            
        except Exception as e:
            logger.error(f"Échec tentative {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(5)  # Attendre avant retry
                
    return False

async def login() -> bool:
    """Login function using twscrape account management."""
    global api
    
    if not validate_credentials():
        return False
        
    try:
        logger.info("Configuration du compte Twitter...")
        
        # Vérifier les comptes existants
        accounts = await api.pool.accounts_info()
        account_exists = False
        account_active = False
        
        for acc in accounts:
            acc_username = acc.get('username') if isinstance(acc, dict) else getattr(acc, 'username', None)
            acc_active = acc.get('active') if isinstance(acc, dict) else getattr(acc, 'active', False)
            acc_logged_in = acc.get('logged_in') if isinstance(acc, dict) else getattr(acc, 'logged_in', False)
            
            if acc_username == TWITTER_USERNAME:
                account_exists = True
                account_active = acc_active
                logger.info(f"Compte trouvé: {acc_username}, actif: {acc_active}, connecté: {acc_logged_in}")
                break
        
        # Si le compte n'existe pas, l'ajouter
        if not account_exists:
            logger.info(f"Ajout du nouveau compte: {TWITTER_USERNAME}")
            if not await add_account_with_retry():
                logger.error("Impossible d'ajouter le compte")
                return False
            # Vérifier à nouveau après ajout
            accounts = await api.pool.accounts_info()
            for acc in accounts:
                acc_username = acc.get('username') if isinstance(acc, dict) else getattr(acc, 'username', None)
                if acc_username == TWITTER_USERNAME:
                    account_active = acc.get('active') if isinstance(acc, dict) else getattr(acc, 'active', False)
                    break
        
        # Si le compte n'est pas actif, essayer de forcer la connexion
        if not account_active:
            logger.warning("Compte inactif, tentative de login forcé...")
            try:
                await api.pool.login_all()
                await asyncio.sleep(5)  # Attendre plus longtemps
            except Exception as e:
                logger.warning(f"Login forcé échoué: {e}")
        
        # Vérifier le statut final - accepter les comptes actifs même s'ils ne sont pas "logged_in"
        accounts = await api.pool.accounts_info()
        usable_accounts = []
        
        for acc in accounts:
            acc_username = acc.get('username') if isinstance(acc, dict) else getattr(acc, 'username', None)
            acc_active = acc.get('active') if isinstance(acc, dict) else getattr(acc, 'active', False)
            acc_logged_in = acc.get('logged_in') if isinstance(acc, dict) else getattr(acc, 'logged_in', False)
            
            # Accepter les comptes actifs (twscrape peut fonctionner avec des comptes "active" même s'ils ne sont pas "logged_in")
            if acc_active or acc_logged_in:
                usable_accounts.append(acc)
                logger.info(f"Compte utilisable: {acc_username} (actif: {acc_active}, connecté: {acc_logged_in})")
        
        if not usable_accounts:
            logger.error("Aucun compte utilisable trouvé")
            await print_troubleshooting_info()
            return False
            
        logger.info(f"Comptes utilisables trouvés: {len(usable_accounts)}")
        return True
                
    except Exception as e:
        logger.error(f"Échec de la connexion: {e}")
        await print_troubleshooting_info()
        return False

async def print_troubleshooting_info():
    """Affiche des informations de dépannage"""
    logger.info("\n=== INFORMATIONS DE DÉPANNAGE ===")
    logger.info("1. Vérifiez que vos credentials sont corrects dans .env:")
    logger.info(f"   - TWITTER_USERNAME défini: {'✓' if TWITTER_USERNAME else '✗'}")
    logger.info(f"   - TWITTER_PASSWORD défini: {'✓' if TWITTER_PASSWORD else '✗'}")
    logger.info(f"   - TWITTER_EMAIL défini: {'✓' if TWITTER_EMAIL else '✗'}")
    logger.info(f"   - TWITTER_COOKIES défini: {'✓' if TWITTER_COOKIES else '✗'}")
    
    if not TWITTER_COOKIES:
        logger.info("\n2. IMPORTANT: Twitter bloque souvent les connexions par mot de passe.")
        logger.info("   Récupérez vos cookies depuis votre navigateur:")
        logger.info("   - Connectez-vous à twitter.com dans votre navigateur")
        logger.info("   - F12 → Application/Storage → Cookies → twitter.com")
        logger.info("   - Copiez tous les cookies et ajoutez-les dans TWITTER_COOKIES")
    
    logger.info("\n3. Autres solutions:")
    logger.info("   - Supprimez accounts.db et relancez")
    logger.info("   - Utilisez un VPN si vous êtes bloqué")
    logger.info("   - Vérifiez que votre compte n'est pas suspendu")
    logger.info("================================\n")

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
        if hasattr(tweet, 'media') and tweet.media:
            for media_item in tweet.media:
                media_url = getattr(media_item, 'mediaUrl', None) or getattr(media_item, 'url', None)
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
    Fonction principale pour récupérer des tweets
    
    Args:
        source_type: "timeline", "user", ou "search"
        source: nom d'utilisateur (pour user) ou requête (pour search)
        limit: nombre maximum de tweets à récupérer
    
    Returns:
        Liste de dictionnaires de tweets
    """
    if source_type == "timeline":
        return await async_scrape_timeline_tweets(limit)
    elif source_type == "user":
        return await async_scrape_user_tweets(source, limit)
    elif source_type == "search":
        return await async_scrape_search_tweets(source, limit)
    else:
        logger.error(f"Type de source non supporté: {source_type}")
        return []

async def async_scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Scraper asynchrone pour les tweets d'un utilisateur."""
    global api
    
    # Nettoyer le nom d'utilisateur
    username = username.replace('@', '').strip()
    if not username:
        logger.error("Nom d'utilisateur invalide")
        return []
    
    try:
        logger.info(f"Récupération des tweets de @{username} (limite: {limit})")
        
        # Obtenir les infos utilisateur
        user_info = await api.user_by_login(username)
        if not user_info:
            logger.error(f"Utilisateur @{username} non trouvé")
            return []
        
        logger.info(f"Utilisateur trouvé: {user_info.displayname} (@{user_info.username})")
        
        # Récupérer les tweets
        tweets = await gather(api.user_tweets(user_info.id, limit=limit))
        
        tweets_data = []
        for tweet in tweets:
            if len(tweets_data) >= limit:
                break
                
            tweet_data = extract_tweet_data_bot_format(tweet)
            if tweet_data:
                tweets_data.append(tweet_data)
                logger.info(f"Tweet récupéré: {tweet_data['text'][:100]}...")

        # Sauvegarder dans Excel
        await save_tweets_to_excel(tweets_data, f"{username}_tweets.xlsx")
        
        logger.info(f"Récupération terminée: {len(tweets_data)} tweets")
        return tweets_data

    except Exception as e:
        logger.error(f"Erreur dans async_scrape_user_tweets: {e}")
        return []

async def async_scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Scraper asynchrone pour la recherche de tweets."""
    global api
    
    if not query.strip():
        logger.error("Requête de recherche invalide")
        return []
    
    try:
        logger.info(f"Recherche de tweets pour: '{query}' (limite: {limit})")
        
        # Rechercher des tweets
        tweets = await gather(api.search(query, limit=limit))
        
        tweets_data = []
        for tweet in tweets:
            if len(tweets_data) >= limit:
                break
                
            tweet_data = extract_tweet_data_bot_format(tweet)
            if tweet_data:
                tweets_data.append(tweet_data)
                logger.info(f"Tweet trouvé: {tweet_data['text'][:100]}...")

        # Sauvegarder dans Excel
        safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"search_{safe_query[:30]}_tweets.xlsx"
        await save_tweets_to_excel(tweets_data, filename)
        
        logger.info(f"Recherche terminée: {len(tweets_data)} tweets")
        return tweets_data

    except Exception as e:
        logger.error(f"Erreur dans async_scrape_search_tweets: {e}")
        return []

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

# Fonctions synchrones pour la compatibilité
def scrape_user_tweets(username: str, limit: int = 20) -> List[Dict]:
    """Version synchrone du scraping utilisateur."""
    try:
        if not setup_driver():
            logger.error("Impossible d'initialiser l'API twscrape")
            return []
        
        return asyncio.run(async_user_wrapper(username, limit))
    except Exception as e:
        logger.error(f"Erreur dans scrape_user_tweets: {e}")
        return []

def scrape_search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """Version synchrone du scraping de recherche."""
    try:
        if not setup_driver():
            logger.error("Impossible d'initialiser l'API twscrape")
            return []
        
        return asyncio.run(async_search_wrapper(query, limit))
    except Exception as e:
        logger.error(f"Erreur dans scrape_search_tweets: {e}")
        return []

async def async_user_wrapper(username: str, limit: int) -> List[Dict]:
    """Wrapper asynchrone pour le scraping utilisateur."""
    if not await login():
        logger.error("Échec de la connexion!")
        return []
    return await async_scrape_user_tweets(username, limit)

async def async_search_wrapper(query: str, limit: int) -> List[Dict]:
    """Wrapper asynchrone pour le scraping de recherche."""
    if not await login():
        logger.error("Échec de la connexion!")
        return []
    return await async_scrape_search_tweets(query, limit)

# Fonction de test spécifique pour diagnostiquer les cookies
async def test_cookies_format():
    """Teste le format des cookies"""
    if not TWITTER_COOKIES:
        logger.warning("Aucun cookie défini")
        return False
    
    try:
        # Vérifier le format basique
        if 'auth_token=' not in TWITTER_COOKIES:
            logger.error("Cookie auth_token manquant - nécessaire pour l'authentification")
            return False
        
        if 'ct0=' not in TWITTER_COOKIES:
            logger.warning("Cookie ct0 manquant - peut causer des problèmes")
        
        logger.info("Format des cookies semble correct")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification des cookies: {e}")
        return False

# Fonction de test simple pour vérifier si l'API fonctionne
async def test_api_basic():
    """Test basique de l'API sans authentification complète"""
    try:
        logger.info("Test basique de l'API...")
        
        # Essayer une recherche simple (peut fonctionner sans authentification complète)
        try:
            tweets = await gather(api.search("python", limit=1))
            if tweets:
                logger.info("✓ API fonctionne - recherche basique réussie")
                return True
        except Exception as search_error:
            logger.warning(f"Recherche basique échouée: {search_error}")
        
        # Essayer d'obtenir des infos utilisateur
        try:
            user = await api.user_by_login("twitter")
            if user:
                logger.info("✓ API fonctionne - récupération utilisateur réussie")
                return True
        except Exception as user_error:
            logger.warning(f"Récupération utilisateur échouée: {user_error}")
        
        logger.error("✗ Toutes les tentatives de test API ont échoué")
        return False
        
    except Exception as e:
        logger.error(f"Erreur lors du test API: {e}")
        return False

# Fonction de diagnostic améliorée
async def diagnose_account_status():
    """Diagnostique le statut des comptes."""
    try:
        accounts = await api.pool.accounts_info()
        logger.info(f"Nombre total de comptes: {len(accounts)}")
        
        if not accounts:
            logger.warning("Aucun compte trouvé dans la base de données")
            return
        
        for i, acc in enumerate(accounts):
            if isinstance(acc, dict):
                logger.info(f"Compte {i+1}: {acc.get('username', 'N/A')} - "
                           f"Connecté: {acc.get('logged_in', False)} - "
                           f"Actif: {acc.get('active', 'N/A')} - "
                           f"Dernière utilisation: {acc.get('last_used', 'Jamais')}")
            else:
                logger.info(f"Compte {i+1}: {getattr(acc, 'username', 'N/A')} - "
                           f"Connecté: {getattr(acc, 'logged_in', False)} - "
                           f"Actif: {getattr(acc, 'active', False)}")
                
    except Exception as e:
        logger.error(f"Erreur lors du diagnostic: {e}")

def diagnose_account_status_sync():
    """Version synchrone du diagnostic."""
    if setup_driver():
        asyncio.run(diagnose_account_status())

# Script principal amélioré avec diagnostics approfondis
if __name__ == "__main__":
    print("=== Test du scraper Twitter avec twscrape (version améliorée) ===")
    
    # Test du format des cookies
    print("\n0. Test du format des cookies...")
    if setup_driver():
        asyncio.run(test_cookies_format())
    
    # Diagnostic des comptes
    print("\n1. Diagnostic des comptes...")
    diagnose_account_status_sync()
    
    # Test API basique
    print("\n2. Test API basique...")
    api_works = test_api_basic_sync()
    if not api_works:
        print("❌ L'API ne fonctionne pas correctement")
        print("   Vérifiez vos cookies ou credentials")
    else:
        print("✅ L'API semble fonctionner")
    
    # Test des tweets utilisateur (seulement si API fonctionne)
    if api_works:
        print("\n3. Test scraping utilisateur...")
        user_tweets = scrape_user_tweets("elonmusk", 2)
        print(f"Tweets utilisateur récupérés: {len(user_tweets)}")
        
        # Test de recherche
        print("\n4. Test scraping recherche...")
        search_tweets = scrape_search_tweets("python", 2)
        print(f"Tweets de recherche récupérés: {len(search_tweets)}")
    else:
        print("\n⚠️  Tests de scraping ignorés car l'API ne fonctionne pas")
    
    print("\n=== Fin des tests ===")
