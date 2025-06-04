#!/usr/bin/env python3
import asyncio
import random
import json
import os
from datetime import datetime, timedelta, timezone
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
            "last_reset_date": datetime.now(timezone.utc).isoformat()[:10],
            "daily_engagement_count": 0,
            "last_engagement_date": None
        }
    
    def _save_state(self):
        """Sauvegarde l'état dans le fichier"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'état: {e}")
    
    def _get_current_utc_time(self):
        """Retourne l'heure UTC actuelle"""
        return datetime.now(timezone.utc)
    
    def should_post_tweet(self) -> bool:
        """Détermine s'il faut poster un tweet"""
        current_time = self._get_current_utc_time()
        current_date = current_time.date().isoformat()
        
        # Reset quotidien
        if self.state["last_reset_date"] != current_date:
            self.state["daily_tweet_count"] = 0
            self.state["last_tweet_times"] = []
            self.state["last_reset_date"] = current_date
            self.state["daily_engagement_count"] = 0
            logger.info("Reset quotidien effectué")
        
        # Limite de 4 tweets par jour
        if self.state["daily_tweet_count"] >= 4:
            logger.info("Limite quotidienne de tweets atteinte (4/4)")
            return False
        
        # Vérifier l'espacement minimum (2 heures)
        if self.state["last_tweet_times"]:
            try:
                last_tweet = datetime.fromisoformat(self.state["last_tweet_times"][-1])
                if not last_tweet.tzinfo:
                    last_tweet = last_tweet.replace(tzinfo=timezone.utc)
                if current_time - last_tweet < timedelta(hours=2):
                    logger.info("Espacement minimum non respecté entre les tweets")
                    return False
            except Exception as e:
                logger.warning(f"Erreur lors de la vérification du dernier tweet: {e}")
        
        return True
    
    def should_post_thread(self) -> bool:
        """Détermine s'il faut poster un thread (une fois par jour à 15h UTC)"""
        current_time = self._get_current_utc_time()
        current_hour = current_time.hour
        current_date = current_time.date().isoformat()
        
        # Vérifier si c'est l'heure (15h UTC ± 30 minutes)
        if not (14.5 <= current_hour <= 15.5):
            logger.debug(f"Pas l'heure pour un thread (heure actuelle: {current_hour}h UTC)")
            return False
        
        # Vérifier si déjà posté aujourd'hui
        if self.state["last_thread_time"]:
            try:
                last_thread_time = datetime.fromisoformat(self.state["last_thread_time"])
                if not last_thread_time.tzinfo:
                    last_thread_time = last_thread_time.replace(tzinfo=timezone.utc)
                last_thread_date = last_thread_time.date().isoformat()
                if last_thread_date == current_date:
                    logger.info("Thread déjà posté aujourd'hui")
                    return False
            except Exception as e:
                logger.warning(f"Erreur lors de la vérification du dernier thread: {e}")
        
        return True
    
    def should_engage(self) -> bool:
        """Détermine s'il faut faire de l'engagement"""
        current_time = self._get_current_utc_time()
        current_hour = current_time.hour
        current_date = current_time.date().isoformat()
        target_hours = [9, 10, 11, 12, 18, 21]  # UTC
        
        # Reset quotidien pour l'engagement
        if self.state.get("last_engagement_date") != current_date:
            self.state["daily_engagement_count"] = 0
            self.state["last_engagement_date"] = current_date
            self.state["last_engagement_times"] = []
            logger.info("Reset quotidien de l'engagement effectué")
        
        if current_hour not in target_hours:
            logger.debug(f"Pas l'heure pour engagement (heure actuelle: {current_hour}h UTC)")
            return False
        
        # Limite de 6 engagements par jour
        if self.state["daily_engagement_count"] >= 6:
            logger.info("Limite quotidienne d'engagement atteinte (6/6)")
            return False
        
        # Vérifier si déjà fait cette heure
        current_hour_start = current_time.replace(minute=0, second=0, microsecond=0)
        
        for engagement_time_str in self.state["last_engagement_times"]:
            try:
                eng_time = datetime.fromisoformat(engagement_time_str)
                if not eng_time.tzinfo:
                    eng_time = eng_time.replace(tzinfo=timezone.utc)
                eng_hour_start = eng_time.replace(minute=0, second=0, microsecond=0)
                if eng_hour_start == current_hour_start:
                    logger.info(f"Engagement déjà effectué à {current_hour}h UTC")
                    return False
            except Exception as e:
                logger.warning(f"Erreur lors de la vérification d'engagement: {e}")
                continue
        
        return True
    
    def record_tweet(self):
        """Enregistre qu'un tweet a été posté"""
        now = self._get_current_utc_time().isoformat()
        self.state["last_tweet_times"].append(now)
        self.state["daily_tweet_count"] += 1
        self._save_state()
        logger.info(f"Tweet enregistré ({self.state['daily_tweet_count']}/4)")
    
    def record_thread(self):
        """Enregistre qu'un thread a été posté"""
        self.state["last_thread_time"] = self._get_current_utc_time().isoformat()
        self._save_state()
        logger.info("Thread enregistré")
    
    def record_engagement(self):
        """Enregistre qu'un engagement a été effectué"""
        now = self._get_current_utc_time()
        now_str = now.isoformat()
        self.state["last_engagement_times"].append(now_str)
        self.state["daily_engagement_count"] += 1
        
        # Garder seulement les 24 dernières heures
        cutoff = now - timedelta(hours=24)
        self.state["last_engagement_times"] = [
            t for t in self.state["last_engagement_times"]
            if datetime.fromisoformat(t.replace('Z', '+00:00') if t.endswith('Z') else t) > cutoff
        ]
        
        self._save_state()
        logger.info(f"Engagement enregistré ({self.state['daily_engagement_count']}/6)")


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
                logger.info("Tweet autonome non nécessaire selon les conditions")
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
        """Poste un thread quotidien à 15h UTC"""
        try:
            if not self.scheduler.should_post_thread():
                logger.info("Thread non nécessaire selon les conditions")
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
        """Effectue l'engagement programmé (2 réponses + 1 citation) - VERSION CORRIGÉE"""
        try:
            if not self.scheduler.should_engage():
                logger.info("Engagement non nécessaire selon les conditions")
                return False
            
            # Délai aléatoire
            await self.execute_random_delay(2, 20)
            
            logger.info("Récupération des tweets pour engagement...")
            tweets = await fetch_tweets("timeline", "", limit=20)
            
            if not tweets or len(tweets) == 0:
                logger.warning("Aucun tweet récupéré pour l'engagement")
                return False
            
            logger.info(f"Tweets récupérés: {len(tweets)}")
            
            # Filtrer les tweets appropriés avec critères moins restrictifs
            suitable_tweets = []
            for tweet in tweets:
                tweet_text = tweet.get('text', '').strip()
                tweet_author = tweet.get('author', '')
                
                # Critères de filtrage améliorés
                if (tweet_text and 
                    len(tweet_text) > 20 and  # Réduit de 30 à 20
                    not tweet_text.startswith('RT @') and
                    not tweet_text.startswith('@') and  # Éviter les mentions pures
                    tweet_author and tweet_author != 'unknown' and
                    'http' not in tweet_text.lower()[:50]):  # Vérifier seulement le début
                    suitable_tweets.append(tweet)
            
            logger.info(f"Tweets appropriés trouvés: {len(suitable_tweets)}")
            
            if len(suitable_tweets) < 2:
                logger.warning(f"Pas assez de tweets appropriés ({len(suitable_tweets)}), utilisation de tous les tweets disponibles")
                suitable_tweets = tweets[:min(3, len(tweets))]
            
            if not suitable_tweets:
                logger.error("Aucun tweet disponible pour l'engagement")
                return False
            
            # Sélectionner aléatoirement jusqu'à 3 tweets
            num_to_select = min(3, len(suitable_tweets))
            selected_tweets = random.sample(suitable_tweets, num_to_select)
            
            logger.info(f"Tweets sélectionnés pour engagement: {len(selected_tweets)}")
            
            replies_posted = 0
            quotes_posted = 0
            engagement_successful = False
            
            for i, tweet in enumerate(selected_tweets):
                try:
                    tweet_id = tweet.get('id')
                    tweet_text = tweet.get('text', '')
                    tweet_author = tweet.get('author', 'utilisateur')
                    
                    logger.info(f"Traitement du tweet {i+1}/{len(selected_tweets)}: {tweet_id}")
                    logger.info(f"Texte: {tweet_text[:100]}...")
                    
                    # Essayer d'abord les réponses (2 maximum)
                    if replies_posted < 2:
                        logger.info(f"Génération d'une réponse au tweet de @{tweet_author}")
                        try:
                            reply_content = await generate_ai_content(
                                "reply", 
                                tweet_text,
                                context=f"Tweet de @{tweet_author}"
                            )
                            
                            if reply_content and reply_content.strip():
                                logger.info(f"Contenu de réponse généré: {reply_content[:100]}...")
                                reply_id = post_content("reply", reply_content, reply_to_id=tweet_id)
                                if reply_id:
                                    replies_posted += 1
                                    engagement_successful = True
                                    logger.info(f"✅ Réponse postée ({replies_posted}/2): {reply_id}")
                                else:
                                    logger.error("❌ Échec de publication de la réponse")
                            else:
                                logger.warning("Contenu de réponse vide ou invalide")
                                
                        except Exception as reply_error:
                            logger.error(f"Erreur lors de la génération/publication de réponse: {reply_error}")
                        
                        # Délai entre les actions
                        await asyncio.sleep(random.uniform(30, 90))
                    
                    # Essayer ensuite les citations (1 maximum)
                    elif quotes_posted < 1:
                        logger.info(f"Génération d'une citation pour le tweet de @{tweet_author}")
                        try:
                            quote_content = await generate_ai_content(
                                "quote",
                                tweet_text,
                                context=f"Tweet de @{tweet_author}"
                            )
                            
                            if quote_content and quote_content.strip():
                                logger.info(f"Contenu de citation généré: {quote_content[:100]}...")
                                quote_id = post_content("quote", quote_content, quoted_tweet_id=tweet_id)
                                if quote_id:
                                    quotes_posted += 1
                                    engagement_successful = True
                                    logger.info(f"✅ Citation postée ({quotes_posted}/1): {quote_id}")
                                else:
                                    logger.error("❌ Échec de publication de la citation")
                            else:
                                logger.warning("Contenu de citation vide ou invalide")
                                
                        except Exception as quote_error:
                            logger.error(f"Erreur lors de la génération/publication de citation: {quote_error}")
                    
                    # Sortir si on a atteint nos objectifs
                    if replies_posted >= 2 and quotes_posted >= 1:
                        logger.info("Objectifs d'engagement atteints")
                        break
                
                except Exception as tweet_error:
                    logger.error(f"Erreur lors du traitement du tweet {tweet.get('id', 'unknown')}: {tweet_error}")
                    continue
            
            # Enregistrer l'engagement même si partiellement réussi
            if engagement_successful:
                self.scheduler.record_engagement()
                logger.info(f"✅ Engagement terminé avec succès: {replies_posted} réponses, {quotes_posted} citations")
                return True
            else:
                logger.warning("❌ Aucun engagement réussi")
                return False
                
        except Exception as e:
            logger.error(f"Erreur critique dans scheduled_engagement: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False


def main():
    """Fonction principale avec gestion intelligente des actions - VERSION CORRIGÉE"""
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
        current_time_utc = datetime.now(timezone.utc)
        logger.info(f"Démarrage du bot Twitter avancé... (Heure UTC: {current_time_utc.strftime('%Y-%m-%d %H:%M:%S')})")
        
        bot = AdvancedTwitterBot()
        
        async def run_bot():
            if args.action == 'auto':
                # Mode automatique - détermine quoi faire basé sur l'heure et l'état
                logger.info("Mode automatique - analyse des conditions...")
                
                actions_performed = []
                
                # Vérifier les threads en premier (priorité)
                if bot.scheduler.should_post_thread() or (args.force and 'thread' not in args.action):
                    logger.info("Conditions remplies pour un thread")
                    result = await bot.post_daily_thread(args.topic)
                    if result:
                        actions_performed.append(f"Thread posté ({len(result)} tweets)")
                    else:
                        logger.warning("Échec du thread")
                
                # Vérifier l'engagement
                if bot.scheduler.should_engage() or (args.force and 'engage' not in args.action):
                    logger.info("Conditions remplies pour l'engagement")
                    result = await bot.scheduled_engagement()
                    if result:
                        actions_performed.append("Engagement effectué")
                    else:
                        logger.warning("Échec de l'engagement")
                
                # Vérifier les tweets autonomes
                if bot.scheduler.should_post_tweet() or (args.force and 'standalone' not in args.action):
                    logger.info("Conditions remplies pour un tweet autonome")
                    result = await bot.post_standalone_tweet(args.topic)
                    if result:
                        actions_performed.append("Tweet autonome posté")
                    else:
                        logger.warning("Échec du tweet autonome")
                
                if actions_performed:
                    logger.info(f"✅ Actions effectuées: {', '.join(actions_performed)}")
                else:
                    logger.info("ℹ️  Aucune action nécessaire pour le moment")
            
            elif args.action == 'standalone':
                logger.info("Mode manuel: Tweet autonome")
                result = await bot.post_standalone_tweet(args.topic)
                if result:
                    logger.info(f"✅ Tweet autonome posté: {result}")
                else:
                    logger.error("❌ Échec du tweet autonome")
            
            elif args.action == 'thread':
                logger.info("Mode manuel: Thread")
                result = await bot.post_daily_thread(args.topic)
                if result:
                    logger.info(f"✅ Thread posté: {result}")
                else:
                    logger.error("❌ Échec du thread")
            
            elif args.action == 'engage':
                logger.info("Mode manuel: Engagement")
                result = await bot.scheduled_engagement()
                if result:
                    logger.info("✅ Engagement effectué avec succès")
                else:
                    logger.error("❌ Échec de l'engagement")
            
            elif args.action == 'test':
                logger.info("Mode test - exécution de toutes les fonctions...")
                await bot.post_standalone_tweet("Test - Sujet IA")
                await asyncio.sleep(10)
                engagement_result = await bot.scheduled_engagement()
                logger.info(f"Test terminé - Engagement: {engagement_result}")
        
        asyncio.run(run_bot())
        
    except KeyboardInterrupt:
        logger.info("Bot arrêté par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        logger.error(f"Traceback complet: {traceback.format_exc()}")
        exit(1)

if __name__ == "__main__":
    main()
