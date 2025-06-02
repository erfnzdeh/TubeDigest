# YouTube Summary-to-Telegram Bot

This bot automatically monitors specified YouTube channels, generates summaries of new videos using GPT-4, and posts them to a Telegram channel.

## Features

- Monitors multiple YouTube channels for new uploads
- Automatically fetches video transcripts
- Generates concise summaries using GPT-4
- Posts summaries to a Telegram channel
- Runs continuously with hourly checks
- Handles rate limits and errors gracefully

## Prerequisites

- Python 3.8 or higher
- YouTube Data API key
- Telegram Bot Token
- OpenAI API key
- Telegram Channel ID

## Setup

1. Clone this repository:
```bash
git clone https://github.com/yourusername/youtube-summary-bot.git
cd youtube-summary-bot
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Fill in your API keys and configuration in the `.env` file:
- Get a YouTube API key from [Google Cloud Console](https://console.cloud.google.com/)
- Create a Telegram bot using [@BotFather](https://t.me/botfather)
- Get your OpenAI API key from [OpenAI Platform](https://platform.openai.com/)
- Add your Telegram channel ID
- Add YouTube channel IDs to monitor (comma-separated)

## Usage

Run the bot:
```bash
python youtube_summary_bot.py
```

The bot will:
1. Check for new videos every hour
2. Generate summaries for new videos
3. Post summaries to your Telegram channel

## Configuration

- Modify the check interval in `youtube_summary_bot.py` (default: 1 hour)
- Adjust the summary length in the `generate_summary` function
- Change the number of recent videos to check in `get_channel_uploads`

## Error Handling

The bot includes comprehensive error handling for:
- API rate limits
- Missing transcripts
- Network issues
- Invalid API keys

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Proxy Support

The bot now includes automatic proxy rotation for YouTube transcript API calls to help avoid rate limiting and potential IP blocks.

### How it works:

1. **Automatic Proxy Fetching**: The bot automatically fetches 25 fresh proxies from the Geonode API every hour
2. **Sequential Rotation**: Proxies are used in order based on their API ranking (typically sorted by ping/response time)
3. **No Quality Filtering**: All fetched proxies are used to maximize availability and rotation
4. **Automatic Failover**: If a proxy fails, the bot immediately tries the next one in the sequence
5. **Retry Logic**: Uses up to 5 different proxies before falling back to direct connection

### Proxy Rotation Logic:

- **Order**: Proxies are used in the order received from the API (pre-sorted by ping/response time)
- **Iteration**: Sequential iteration through the proxy list (proxy 1, 2, 3... 25, then back to 1)
- **Retry Strategy**: Each failed request tries the next proxy in sequence
- **Fallback**: Last attempt always uses direct connection if all proxies fail

### Testing the Proxy System:

Run the test script to verify proxy functionality:

```bash
python test_proxy.py
```

This will:
- Fetch proxies from the Geonode API
- Test proxy filtering and quality assessment
- Test actual proxy connections
- Demonstrate proxy rotation
- Test the YouTube transcript API with proxies

### Configuration:

No additional configuration is needed. The proxy system works automatically and falls back to direct connections if no proxies are available.

The proxy manager:
- Updates proxy lists every hour
- Stores working proxies in `data/fallback_proxies.json`
- Prefers proxies with high uptime and good anonymity
- Uses the format expected by `YouTubeTranscriptApi.get_transcript(video_id, proxies={"https": "https://ip:port"})`

### Troubleshooting Proxy Issues:

If you encounter proxy-related issues:

1. **Disable proxies entirely** (if needed):
   ```bash
   # Add to your .env file
   USE_PROXIES=false
   ```

2. **Clean up bad fallback proxies**:
   ```bash
   python -c "import os; f='data/fallback_proxies.json'; os.remove(f) if os.path.exists(f) else None; print('Cleaned')"
   ```

3. **Test proxy connectivity**:
   ```bash
   python test_proxy_offline.py  # Test proxy functionality without external calls
   ```

4. **Network connectivity issues**: If the Geonode API is blocked by your network/firewall, the bot will automatically fall back to direct connections after a few minutes.

The proxy system is designed to be resilient - it will automatically disable problematic proxies and fall back to direct connections when needed. 