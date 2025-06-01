# TubeDigest - Digital Ocean App Platform Deployment Guide

## Overview
TubeDigest is a YouTube video summarization bot that monitors specified YouTube channels for new videos, generates AI-powered summaries using OpenAI, and posts them to Telegram channels.

## Deployment Files Created

### 1. `runtime.txt`
Specifies Python 3.11.7 runtime for Digital Ocean App Platform.

### 2. `Procfile`
Defines how to run the application:
```
web: python youtube_summary_bot.py
```

### 3. `app.yaml`
Digital Ocean App Platform configuration file with:
- Service configuration
- Environment variables
- Health checks
- Scaling settings
- GitHub integration

### 4. `.dockerignore`
Excludes unnecessary files from the Docker build process.

## Required Environment Variables

Set these in your Digital Ocean App Platform dashboard:

- `YOUTUBE_API_KEY`: Your YouTube Data API v3 key
- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
- `TELEGRAM_CHANNEL_ID`: Default Telegram channel ID (optional if using channel mappings)
- `OPENAI_API_KEY`: Your OpenAI API key
- `YOUTUBE_CHANNEL_IDS`: Comma-separated list of YouTube channel IDs to monitor (optional if using channel mappings)

## Configuration

### Channel Mappings
The bot uses `data/channel_mappings.json` to define:
- YouTube channels to monitor
- Telegram channels to post to
- Custom prompts for each channel

Example structure:
```json
{
  "channel_mappings": [
    {
      "channel_name": "Channel Name",
      "youtube_channel_id": "UC...",
      "telegram_channel_id": "-100...",
      "prompt": {
        "system": "System prompt for AI",
        "user": "User prompt template with {transcript} placeholder"
      }
    }
  ]
}
```

## Health Check
The application includes a health check endpoint at `/` and `/health` that returns "TubeDigest Bot is running!" when the service is operational.

## Deployment Steps

1. **Update app.yaml**: Replace `YOUR_GITHUB_USERNAME/TubeDigest` with your actual GitHub repository path.

2. **Push to GitHub**: Ensure all files are committed and pushed to your main branch.

3. **Create App on Digital Ocean**:
   - Go to Digital Ocean App Platform
   - Create new app from GitHub repository
   - Select your repository and main branch
   - Use the app.yaml configuration

4. **Set Environment Variables**:
   - In the app settings, add all required environment variables as secrets

5. **Deploy**: The app will automatically deploy when you push to the main branch.

## Application Behavior

- The bot runs continuously, checking for new videos every hour
- It skips YouTube Shorts automatically
- Videos are tracked to avoid duplicate processing
- Summaries are posted with video thumbnails
- Long summaries are split across multiple messages
- The health check server runs on port 8080 (configurable via PORT env var)

## Troubleshooting

- Check app logs in Digital Ocean dashboard for any errors
- Ensure all environment variables are set correctly
- Verify API keys have proper permissions
- Check that Telegram bot has permission to post to specified channels
- Ensure YouTube channels in configuration are public and have uploads

## Cost Considerations

- Uses `basic-xxs` instance (lowest cost)
- API costs from OpenAI for summaries
- YouTube API quota limits (free tier available)
- Telegram API is free 