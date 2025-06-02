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

1. **Automatic Proxy Fetching**: The bot automatically fetches fresh proxy lists from the Geonode API every hour
2. **Quality Filtering**: Proxies are filtered based on uptime (>70%), speed, and anonymity level
3. **Smart Rotation**: High-quality proxies are preferred with weighted random selection
4. **Fallback System**: Working proxies are saved locally as fallback in case the API is unavailable
5. **Retry Logic**: If a transcript fetch fails with a proxy, the bot will retry with different proxies

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