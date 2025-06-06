
#!/usr/bin/env python3
import os
import sys
import asyncio
import threading
from datetime import datetime, timezone
from flask import Flask, jsonify, request
import logging

# Add the current directory to the path so we can import our bot modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import AdvancedTwitterBot
from config import validate_config, logger

app = Flask(__name__)

# Configure Flask logging
logging.basicConfig(level=logging.INFO)
flask_logger = logging.getLogger('werkzeug')
flask_logger.setLevel(logging.WARNING)

# Global variables to track bot status
last_run_time = None
is_running = False
run_count = 0

def run_bot_async():
    """Run the bot in async context"""
    global last_run_time, is_running, run_count
    
    try:
        is_running = True
        logger.info("Flask endpoint triggered bot execution")
        
        # Validate configuration
        validate_config()
        
        # Create and run bot
        bot = AdvancedTwitterBot()
        
        async def execute_bot():
            actions_performed = []
            
            # Check and execute thread posting
            if bot.scheduler.should_post_thread():
                logger.info("Executing thread posting...")
                result = await bot.post_daily_thread()
                if result:
                    actions_performed.append(f"Thread posted ({len(result)} tweets)")
            
            # Check and execute engagement
            if bot.scheduler.should_engage():
                logger.info("Executing engagement...")
                result = await bot.scheduled_engagement()
                if result:
                    actions_performed.append("Engagement completed")
            
            # Check and execute standalone tweet
            if bot.scheduler.should_post_tweet():
                logger.info("Executing standalone tweet...")
                result = await bot.post_standalone_tweet()
                if result:
                    actions_performed.append("Standalone tweet posted")
            
            return actions_performed
        
        # Run the bot
        actions = asyncio.run(execute_bot())
        
        last_run_time = datetime.now(timezone.utc)
        run_count += 1
        
        return {
            'success': True,
            'actions': actions,
            'timestamp': last_run_time.isoformat(),
            'run_count': run_count
        }
        
    except Exception as e:
        logger.error(f"Error in bot execution: {e}")
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    finally:
        is_running = False

@app.route('/')
def home():
    """Home page with bot status"""
    return jsonify({
        'status': 'Twitter Bot Flask Server',
        'version': '1.0',
        'last_run': last_run_time.isoformat() if last_run_time else None,
        'currently_running': is_running,
        'total_runs': run_count,
        'endpoints': {
            '/run-task': 'POST - Trigger bot execution',
            '/status': 'GET - Get bot status',
            '/health': 'GET - Health check'
        }
    })

@app.route('/run-task', methods=['POST', 'GET'])
def run_task():
    """Endpoint to trigger bot execution"""
    global is_running
    
    # Prevent concurrent executions
    if is_running:
        return jsonify({
            'status': 'already_running',
            'message': 'Bot is currently running, please wait',
            'last_run': last_run_time.isoformat() if last_run_time else None
        }), 429
    
    # Run bot in background thread to avoid blocking Flask
    def run_in_thread():
        return run_bot_async()
    
    thread = threading.Thread(target=run_in_thread)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'status': 'started',
        'message': 'Bot execution started',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'run_count': run_count + 1
    })

@app.route('/status')
def status():
    """Get current bot status"""
    return jsonify({
        'currently_running': is_running,
        'last_run_time': last_run_time.isoformat() if last_run_time else None,
        'total_runs': run_count,
        'server_time': datetime.now(timezone.utc).isoformat(),
        'status': 'healthy'
    })

@app.route('/health')
def health():
    """Health check endpoint for monitoring services"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'service': 'twitter-bot'
    })

@app.route('/logs')
def logs():
    """Get recent bot logs"""
    try:
        log_file = 'bot.log'
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Return last 50 lines
                recent_logs = lines[-50:] if len(lines) > 50 else lines
                return jsonify({
                    'logs': recent_logs,
                    'total_lines': len(lines),
                    'showing_last': len(recent_logs)
                })
        else:
            return jsonify({'logs': [], 'message': 'No log file found'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Twitter Bot Flask Server...")
    print("📍 Endpoints available:")
    print("   - GET  /           - Home page with status")
    print("   - POST /run-task   - Trigger bot execution")
    print("   - GET  /status     - Bot status")
    print("   - GET  /health     - Health check")
    print("   - GET  /logs       - Recent logs")
    print("\n🔗 For external monitoring:")
    print("   - Use POST requests to /run-task every 30 minutes")
    print("   - Use GET requests to /health for uptime monitoring")
    
    # Run Flask server
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
