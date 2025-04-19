import os
import time
import logging
import asyncio
import json
from datetime import datetime, timedelta, UTC
from typing import List, Dict
import backoff

import schedule
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from telegram import Bot
from openai import OpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class YouTubeSummaryBot:
    def __init__(self, youtube_channel_id: str, telegram_channel_id: str, prompt: Dict):
        self.youtube_channel_id = youtube_channel_id
        self.telegram_channel_id = telegram_channel_id
        self.prompt = prompt
        self.processed_videos = set()
        
        # Initialize API clients
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.telegram_bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def get_channel_uploads(self) -> List[Dict]:
        """Fetch recent uploads from a YouTube channel."""
        try:
            # Get channel's uploads playlist ID
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=self.youtube_channel_id
            ).execute()
            
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get recent videos from uploads playlist
            playlist_response = self.youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=5
            ).execute()
            
            return playlist_response['items']
        except Exception as e:
            logger.error(f"Error fetching channel uploads: {e}")
            return []

    def get_video_transcript(self, video_id: str) -> str:
        """Fetch transcript for a YouTube video."""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return ' '.join([entry['text'] for entry in transcript_list])
        except Exception as e:
            logger.error(f"Error fetching transcript: {e}")
            return ""

    def generate_summary(self, transcript: str) -> str:
        """Generate a summary using OpenAI's API."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.prompt["system"]},
                    {"role": "user", "content": self.prompt["user"].format(transcript=transcript)}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Error generating summary"

    @backoff.on_exception(
        backoff.expo,
        (Exception),
        max_tries=3,
        max_time=30
    )
    async def send_telegram_message(self, video_title: str, summary: str, video_url: str) -> None:
        """Send summary to Telegram channel with retry logic."""
        try:
            message = f"{summary}\n\nSource: [{video_title}]({video_url})"
            await self.telegram_bot.send_message(
                chat_id=self.telegram_channel_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Successfully sent message for video: {video_title}")
        except Exception as e:
            logger.error(f"Error sending Telegram message for video {video_title}: {str(e)}")
            raise

    async def check_new_videos(self):
        """Check for new videos from monitored channel."""
        logger.info(f"Checking for new videos for channel {self.youtube_channel_id}...")
        
        videos = self.get_channel_uploads()
        
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            
            # Skip if already processed
            if video_id in self.processed_videos:
                continue
                
            logger.info(f"Processing new video: {video['snippet']['title']}")
            
            # Get transcript and generate summary
            transcript = self.get_video_transcript(video_id)
            if transcript:
                summary = self.generate_summary(transcript)
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Send to Telegram
                await self.send_telegram_message(video['snippet']['title'], summary, video_url)
                
                # Mark as processed
                self.processed_videos.add(video_id)
                
                # Sleep to avoid rate limits
                time.sleep(2)

    async def run(self):
        """Run the bot instance."""
        logger.info(f"Starting YouTube Summary Bot for channel {self.youtube_channel_id}...")
        
        while True:
            await self.check_new_videos()
            await asyncio.sleep(3600)  # Sleep for 1 hour

async def main():
    """Main function to run multiple bot instances."""
    # Load channel mappings from JSON file
    try:
        with open('channel_mappings.json', 'r') as f:
            config = json.load(f)
            channel_mappings = config['channel_mappings']
    except FileNotFoundError:
        logger.error("channel_mappings.json file not found")
        return
    except json.JSONDecodeError:
        logger.error("Invalid JSON format in channel_mappings.json")
        return
    
    bots = [YouTubeSummaryBot(
        mapping['youtube_channel_id'], 
        mapping['telegram_channel_id'],
        mapping['prompt']
    ) for mapping in channel_mappings]
    
    # Run all bots concurrently
    await asyncio.gather(*(bot.run() for bot in bots))

if __name__ == "__main__":
    asyncio.run(main())