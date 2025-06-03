#!/usr/bin/env python3
import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

from config import logger, validate_config
from ai_generator import generate_ai_content
from poster import post_content
from twscrape_client import fetch_tweets

class PersistentScheduler:
    """Gestionnaire d'état persistant pour le timing du bot"""
    
    def __init__(self, state_file: str = "bot_state.json"):
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Charge l'état depuis le fichier"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Erreur lors du chargement de l'état: {e}")
        
        # État par défaut
        return {
            "last_tweet_times": [],
            "last_thread_time": None,
            "last_engagement_times": [],
            "daily_tweet_count": 0,
            "last_reset_date": datetime.now().isoformat()[:10]
        }
    
    def _save_state(self):
        """Sauvegarde l'état dans le fichier"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'état: {e}")
    
    def should_post_tweet(self) -> bool:
        """Détermine s'il faut poster un tweet"""
        current_date = datetime.now().date().isoformat()
        
        # Reset quotidien
        if self.state["last_reset_date"] != current_date:
            self.state["daily_tweet_count"] = 0
            self.state["last_tweet_times"] = []
            self.state["last_reset_date"] = current_date
        
        # Limite de 4 tweets par jour
        if self.state["daily_tweet_count"] >= 4:
            logger.info("Limite quotidienne de tweets atteinte (4/4)")
            return False
        
        # Vérifier l'espacement minimum (2 heures)
        if self.state["last_tweet_times"]:
            last_tweet = datetime.fromisoformat(self.state["last_tweet_times"][-1])
            if datetime.now() - last_tweet < timedelta(hours=2):
                logger.info("Espacement minimum non respecté entre les tweets")
                return False
        
        return True
    
    def should_post_thread(self) -> bool:
        """Détermine s'il faut poster un thread (une fois par jour à 15h)"""
        current_hour = datetime.now().hour
        current_date = datetime.now().date().isoformat()
        
        # Vérifier si c'est l'heure (15h ± 30 minutes)
        if not (14.5 <= current_hour <= 15.5):
            return False
        
        # Vérifier si déjà posté aujourd'hui
        if self.state["last_thread_time"]:
            last_thread_date = datetime.fromisoformat(self.state["last_thread_time"]).date().isoformat()
            if last_thread_date == current_date:
                logger.info("Thread déjà posté aujourd'hui")
                return False
        
        return True
    
    def should_engage(self) -> bool:
        """Détermine s'il faut faire de l'engagement"""
        current_hour = datetime.now().hour
        target_hours = [9, 10, 11, 12, 18, 21]
        
        if current_hour not in target_hours:
            return False
        
        # Vérifier si déjà fait cette heure
        current_datetime = datetime.now()
        current_hour_start = current_datetime.replace(minute=0, second=0, microsecond=0)
        
        for engagement_time in self.state["last_engagement_times"]:
            eng_time = datetime.fromisoformat(engagement_time)
            eng_hour_start = eng_time.replace(minute=0, second=0, microsecond=0)
            if eng_hour_start == current_hour_start:
                logger.info(f"Engagement déjà effectué à {current_hour}h")
                return False
        
        return True
    
    def record_tweet(self):
        """Enregistre qu'un tweet a été posté"""
        now = datetime.now().isoformat()
        self.state["last_tweet_times"].append(now)
        self.state["daily_tweet_count"] += 1
        self._save_state()
        logger.info(f"Tweet enregistré ({self.state['daily_tweet_count']}/4)")
    
    def record_thread(self):
        """Enregistre qu'un thread a été posté"""
        self.state["last_thread_time"] = datetime.now().isoformat()
        self._save_state()
        logger.info("Thread enregistré")
    
    def record_engagement(self):
        """Enregistre qu'un engagement a été effectué"""
        now = datetime.now().isoformat()
        self.state["last_engagement_times"].append(now)
        
        # Garder seulement les 24 dernières heures
        cutoff = datetime.now() - timedelta(hours=24)
        self.state["last_engagement_times"] = [
            t for t in self.state["last_engagement_times"]
            if datetime.fromisoformat(t) > cutoff
        ]
        
        self._save_state()
        logger.info("Engagement enregistré")


class AdvancedTwitterBot:
    def __init__(self):
        self.scheduler = PersistentScheduler()
        
    async def execute_random_delay(self, min_minutes: int = 5, max_minutes: int = 30):
        """Ajoute un délai aléatoire pour simuler un comportement humain"""
        delay_minutes = random.uniform(min_minutes, max_minutes)
        delay_seconds = delay_minutes * 60
        logger.info(f"Délai aléatoire de {delay_minutes:.1f} minutes...")
        await asyncio.sleep(delay_seconds)
    
    async def post_standalone_tweet(self, topic: str = None) -> Optional[str]:
        """Poste un tweet autonome avec vérifications"""
        try:
            if not self.scheduler.should_post_tweet():
                return None
            
            # Délai aléatoire pour paraître plus naturel
            await self.execute_random_delay(1, 15)
            
            if not topic:
                topics = [
                    "Intelligence artificielle et apprentissage automatique",
                    "Tendances technologiques émergentes",
                    "L'avenir de l'IA et son impact",
                    "Éthique et responsabilité en IA",
                    "Applications pratiques du machine learning",
                    "Innovation et transformation digitale",
                    "Data science et analyse prédictive",
                    "Automatisation intelligente"
                ]
                topic = random.choice(topics)
            
            logger.info(f"Génération d'un tweet sur: {topic}")
            content = await generate_ai_content("standalone", topic)
            
            if content:
                tweet_id = post_content("tweet", content)
                if tweet_id:
                    self.scheduler.record_tweet()
                    logger.info(f"Tweet posté avec succès: {tweet_id}")
                    return tweet_id
                else:
                    logger.error("Échec de publication du tweet")
            else:
                logger.error("Échec de génération du contenu du tweet")
                
        except Exception as e:
            logger.error(f"Erreur dans post_standalone_tweet: {e}")
        
        return None
    
    async def post_daily_thread(self, topic: str = None) -> Optional[List[str]]:
        """Poste un thread quotidien à 15h"""
        try:
            if not self.scheduler.should_post_thread():
                return None
            
            # Délai aléatoire léger
            await self.execute_random_delay(0, 10)
            
            if not topic:
                thread_topics = [
                    "L'évolution de l'IA dans la dernière décennie",
                    "Comprendre les réseaux de neurones et l'apprentissage profond",
                    "Éthique de l'IA et développement responsable",
                    "L'avenir de la collaboration humain-IA",
                    "Applications du machine learning dans la vie quotidienne",
                    "Percées en recherche IA et leurs implications",
                    "Impact de l'IA sur différents secteurs industriels",
                    "Construction de systèmes IA dignes de confiance"
                ]
                topic = random.choice(thread_topics)
            
            logger.info(f"Génération d'un thread sur: {topic}")
            thread_tweets = await generate_ai_content("thread", topic, num_tweets=4)
            
            if thread_tweets and isinstance(thread_tweets, list) and len(thread_tweets) > 0:
                posted_ids = post_content("thread", thread_tweets)
                if posted_ids and len(posted_ids) > 0:
                    self.scheduler.record_thread()
                    logger.info(f"Thread posté avec {len(posted_ids)} tweets: {posted_ids}")
                    return posted_ids
                else:
                    logger.error("Échec de publication du thread")
            else:
                logger.error("Échec de génération du contenu du thread")
                
        except Exception as e:
            logger.error(f"Erreur dans post_daily_thread: {e}")
        
        return None
    
    async def scheduled_engagement(self) -> bool:
        """Effectue l'engagement programmé (2 réponses + 1 citation)"""
        try:
            if not self.scheduler.should_engage():
                return False
            
            # Délai aléatoire
            await self.execute_random_delay(2, 20)
            
            logger.info("Récupération des tweets pour engagement...")
            tweets = await fetch_tweets("timeline", "", limit=15)
            
            if not tweets:
                logger.warning("Aucun tweet récupéré pour l'engagement")
                return False
            
            # Filtrer les tweets appropriés
            suitable_tweets = [
                tweet for tweet in tweets
                if (tweet.get('text', '').strip() and 
                    len(tweet.get('text', '')) > 30 and
                    not tweet.get('text', '').startswith('RT @') and
                    'http' not in tweet.get('text', '').lower())
            ]
            
            if len(suitable_tweets) < 3:
                logger.warning(f"Seulement {len(suitable_tweets)} tweets appropriés trouvés")
                suitable_tweets = tweets[:3] if len(tweets) >= 3 else tweets
            
            if not suitable_tweets:
                logger.warning("Aucun tweet approprié trouvé")
                return False
            
            # Sélectionner aléatoirement 3 tweets
            selected_tweets = random.sample(suitable_tweets, min(3, len(suitable_tweets)))
            
            replies_posted = 0
            quotes_posted = 0
            
            for tweet in selected_tweets:
                try:
                    if replies_posted < 2:
                        # Poster une réponse
                        logger.info(f"Génération d'une réponse au tweet: {tweet['id']}")
                        reply_content = await generate_ai_content(
                            "reply", 
                            tweet['text'],
                            context=f"Tweet de @{tweet.get('author', 'utilisateur')}"
                        )
                        
                        if reply_content:
                            reply_id = post_content("reply", reply_content, reply_to_id=tweet['id'])
                            if reply_id:
                                replies_posted += 1
                                logger.info(f"Réponse postée ({replies_posted}/2): {reply_id}")
                            
                        # Délai entre les actions
                        await asyncio.sleep(random.uniform(30, 90))
                    
                    elif quotes_posted < 1:
                        # Poster une citation
                        logger.info(f"Génération d'une citation pour: {tweet['id']}")
                        quote_content = await generate_ai_content(
                            "quote",
                            tweet['text'],
                            context=f"Tweet de @{tweet.get('author', 'utilisateur')}"
                        )
                        
                        if quote_content:
                            quote_id = post_content("quote", quote_content, quoted_tweet_id=tweet['id'])
                            if quote_id:
                                quotes_posted += 1
                                logger.info(f"Citation postée ({quotes_posted}/1): {quote_id}")
                
                except Exception as e:
                    logger.error(f"Erreur lors de l'engagement avec le tweet {tweet.get('id')}: {e}")
                    continue
            
            if replies_posted > 0 or quotes_posted > 0:
                self.scheduler.record_engagement()
                logger.info(f"Engagement terminé: {replies_posted} réponses, {quotes_posted} citations")
                return True
            else:
                logger.warning("Aucun engagement réussi")
                return False
                
        except Exception as e:
            logger.error(f"Erreur dans scheduled_engagement: {e}")
            return False


def main():
    """Fonction principale avec gestion intelligente des actions"""
    parser = argparse.ArgumentParser(description='Bot Twitter Avancé')
    parser.add_argument('action', nargs='?', default='auto',
                       choices=['auto', 'standalone', 'thread', 'engage', 'test'],
                       help='Action à exécuter')
    parser.add_argument('--topic', help='Sujet spécifique pour le contenu')
    parser.add_argument('--force', action='store_true', 
                       help='Forcer l\'exécution même si les conditions temporelles ne sont pas remplies')
    
    args = parser.parse_args()
    
    try:
        validate_config()
        logger.info("Démarrage du bot Twitter avancé...")
        
        bot = AdvancedTwitterBot()
        
        async def run_bot():
            if args.action == 'auto':
                # Mode automatique - détermine quoi faire basé sur l'heure et l'état
                logger.info("Mode automatique - analyse des conditions...")
                
                actions_performed = []
                
                # Vérifier les threads
                if bot.scheduler.should_post_thread() or args.force:
                    result = await bot.post_daily_thread(args.topic)
                    if result:
                        actions_performed.append(f"Thread posté ({len(result)} tweets)")
                
                # Vérifier l'engagement
                if bot.scheduler.should_engage() or args.force:
                    result = await bot.scheduled_engagement()
                    if result:
                        actions_performed.append("Engagement effectué")
                
                # Vérifier les tweets autonomes
                if bot.scheduler.should_post_tweet() or args.force:
                    result = await bot.post_standalone_tweet(args.topic)
                    if result:
                        actions_performed.append("Tweet autonome posté")
                
                if actions_performed:
                    logger.info(f"Actions effectuées: {', '.join(actions_performed)}")
                else:
                    logger.info("Aucune action nécessaire pour le moment")
            
            elif args.action == 'standalone':
                await bot.post_standalone_tweet(args.topic)
            
            elif args.action == 'thread':
                await bot.post_daily_thread(args.topic)
            
            elif args.action == 'engage':
                await bot.scheduled_engagement()
            
            elif args.action == 'test':
                logger.info("Mode test - exécution de toutes les fonctions...")
                await bot.post_standalone_tweet("Test - Sujet IA")
                await asyncio.sleep(10)
                await bot.scheduled_engagement()
        
        asyncio.run(run_bot())
        
    except KeyboardInterrupt:
        logger.info("Bot arrêté par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        exit(1)

if __name__ == "__main__":
    main()
