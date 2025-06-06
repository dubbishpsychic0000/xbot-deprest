
# External Monitoring Setup Guide

## Overview
This guide shows you how to set up external monitoring services to automatically trigger your Twitter bot every 30 minutes using the Flask web server.

## Step 1: Deploy Your Flask Server on Replit

1. **Deploy the application:**
   - Click the "Deploy" button in Replit
   - Choose "Autoscale" deployment
   - Use the configuration that's already set up
   - Your app will get a URL like: `https://your-repl-name.username.repl.co`

2. **Test your endpoints:**
   - Health check: `GET https://your-app-url.repl.co/health`
   - Bot status: `GET https://your-app-url.repl.co/status`
   - Trigger bot: `POST https://your-app-url.repl.co/run-task`

## Step 2: Set Up External Monitoring

### Option A: UptimeRobot (Recommended)

1. **Sign up at:** https://uptimerobot.com (Free plan available)

2. **Create a new monitor:**
   - Monitor Type: HTTP(s)
   - Friendly Name: "Twitter Bot Trigger"
   - URL: `https://your-app-url.repl.co/run-task`
   - Monitoring Interval: 30 minutes
   - HTTP Method: POST
   - HTTP Headers: `Content-Type: application/json`

3. **Create a health monitor (optional):**
   - Monitor Type: HTTP(s)
   - Friendly Name: "Twitter Bot Health"
   - URL: `https://your-app-url.repl.co/health`
   - Monitoring Interval: 5 minutes
   - HTTP Method: GET

### Option B: cron-job.org

1. **Sign up at:** https://cron-job.org (Free plan available)

2. **Create a new cron job:**
   - Title: "Twitter Bot Trigger"
   - URL: `https://your-app-url.repl.co/run-task`
   - Schedule: `*/30 * * * *` (every 30 minutes)
   - Request method: POST
   - Request body: `{}` (empty JSON)
   - Request headers: `Content-Type: application/json`

### Option C: Pingdom

1. **Sign up at:** https://www.pingdom.com

2. **Create uptime check:**
   - URL: `https://your-app-url.repl.co/run-task`
   - Check interval: 30 minutes
   - Request type: POST

## Step 3: Monitor Your Bot

### Available Endpoints:

- **`GET /`** - Home page with bot information
- **`POST /run-task`** - Trigger bot execution (use this for automation)
- **`GET /status`** - Current bot status and statistics
- **`GET /health`** - Health check (returns 200 if working)
- **`GET /logs`** - Recent bot logs

### Example Monitoring URLs:
Replace `your-app-url.repl.co` with your actual Replit deployment URL.

- Bot trigger: `https://your-app-url.repl.co/run-task`
- Health check: `https://your-app-url.repl.co/health`
- Status page: `https://your-app-url.repl.co/status`

## Step 4: Verify Everything is Working

1. **Test manually:**
   ```bash
   curl -X POST https://your-app-url.repl.co/run-task
   ```

2. **Check status:**
   ```bash
   curl https://your-app-url.repl.co/status
   ```

3. **Monitor logs:**
   - Check the `/logs` endpoint or your Replit console
   - Look for "Flask endpoint triggered bot execution" messages

## Troubleshooting

### Common Issues:

1. **Bot not running:** Check the `/status` endpoint to see the last run time
2. **Server not responding:** Verify your Replit deployment is active
3. **Authentication errors:** Check your environment variables in Replit secrets
4. **Rate limiting:** The bot has built-in rate limiting, so multiple rapid requests won't cause issues

### Monitoring Best Practices:

- Use 30-minute intervals (not shorter) to respect Twitter's rate limits
- Set up health checks every 5 minutes to keep your app warm
- Monitor the `/logs` endpoint to track bot activity
- Use the `/status` endpoint to verify the bot is working correctly

## Security Notes

- The `/run-task` endpoint doesn't require authentication by design for external monitoring
- All sensitive data (API keys) should be stored in Replit Secrets
- The Flask server only exposes read-only information and bot triggers
- Consider adding basic authentication if you want extra security

## Cost Considerations

- **Replit Autoscale:** Charges based on usage
- **UptimeRobot:** Free plan supports up to 50 monitors
- **cron-job.org:** Free plan supports unlimited jobs
- **Total cost:** Primarily just your Replit deployment costs
