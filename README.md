# YouTube Summary-to-Telegram Bot

This bot automatically monitors specified YouTube channels, generates summaries of new videos using GPT-3.5-turbo, and posts them to users via Telegram.

## Features

- User-specific YouTube channel monitoring
- Automatically fetches video transcripts
- Generates concise summaries using GPT-3.5-turbo
- Sends summaries directly to users via Telegram
- Runs continuously with hourly checks
- Handles rate limits and errors gracefully
- MySQL database for persistent storage

## Prerequisites

- Python 3.8 or higher
- YouTube Data API key
- Telegram Bot Token
- OpenAI API key
- Docker and Docker Compose (for MySQL)

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
- Set MySQL credentials (or use defaults)

5. Start the MySQL container:
```bash
docker-compose up -d
```

## Usage

Run the bot:
```bash
python src/bot.py
```

The bot will:
1. Connect to the MySQL database
2. Start listening for Telegram commands
3. Check for new videos every hour
4. Generate summaries for new videos
5. Send summaries to users

## Bot Commands

- `/start` - Start the bot and get welcome message
- `/add_channel <channel_id>` - Add a YouTube channel to monitor
- `/list_channels` - List your monitored channels
- `/remove_channel <channel_id>` - Remove a channel from monitoring
- `/help` - Show help message

## Database

The bot uses MySQL for data storage. The database is run in a Docker container with the following default settings:
- Database name: tubedigest
- Username: tubedigest
- Password: (set in .env file)
- Host: localhost
- Port: 3306

## Configuration

- Modify the check interval in `src/bot.py` (default: 1 hour)
- Adjust the summary length in the `generate_summary` function
- Change the number of recent videos to check in `get_channel_uploads`

## Error Handling

The bot includes comprehensive error handling for:
- API rate limits
- Missing transcripts
- Network issues
- Invalid API keys
- Database connection issues

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details. 