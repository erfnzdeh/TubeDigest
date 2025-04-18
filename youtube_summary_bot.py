import os
import time
import logging
import asyncio
from datetime import datetime, timedelta, UTC
from typing import List, Dict

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

# Initialize API clients
youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
telegram_bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Global variable to store processed video IDs
processed_videos = set()

def get_channel_uploads(channel_id: str) -> List[Dict]:
    """Fetch recent uploads from a YouTube channel."""
    try:
        # Get channel's uploads playlist ID
        channel_response = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        ).execute()
        
        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Get recent videos from uploads playlist
        playlist_response = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=5
        ).execute()
        
        return playlist_response['items']
    except Exception as e:
        logger.error(f"Error fetching channel uploads: {e}")
        return []

def get_video_transcript(video_id: str) -> str:
    """Fetch transcript for a YouTube video."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([entry['text'] for entry in transcript_list])
    except Exception as e:
        logger.error(f"Error fetching transcript: {e}")
        return ""

def generate_summary(transcript: str) -> str:
    """Generate a summary using OpenAI's API."""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates concise, informative summaries of YouTube video transcripts."},
                {"role": "user", "content": f"Please summarize the following transcript in 3-4 paragraphs, highlighting the main points and key takeaways:\n\n{transcript}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return "Error generating summary"

async def send_telegram_message(video_title: str, summary: str, video_url: str) -> None:
    """Send summary to Telegram channel."""
    try:
        message = f"🎥 *{video_title}*\n\n{summary}\n\n🔗 Watch the video: {video_url}"
        await telegram_bot.send_message(
            chat_id=os.getenv('TELEGRAM_CHANNEL_ID'),
            text=message,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")

async def check_new_videos():
    """Check for new videos from monitored channels."""
    channel_ids = os.getenv('YOUTUBE_CHANNEL_IDS').split(',')
    
    for channel_id in channel_ids:
        videos = get_channel_uploads(channel_id)
        
        for video in videos:
            video_id = video['snippet']['resourceId']['videoId']
            
            # Skip if already processed
            if video_id in processed_videos:
                continue
                
            # Check if video is recent (within last 24 hours)
            published_at = datetime.strptime(video['snippet']['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
            if datetime.now(UTC) - published_at > timedelta(hours=24):
                continue
                
            logger.info(f"Processing new video: {video['snippet']['title']}")
            
            # Get transcript and generate summary
            transcript = get_video_transcript(video_id)
            if transcript:
                summary = generate_summary(transcript)
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Send to Telegram
                await send_telegram_message(video['snippet']['title'], summary, video_url)
                
                # Mark as processed
                processed_videos.add(video_id)
                
                # Sleep to avoid rate limits
                time.sleep(2)

async def main():
    """Main function to run the bot."""
    logger.info("Starting YouTube Summary Bot...")
    
    # Run immediately on startup
    await check_new_videos()
    
    # Schedule the check_new_videos function to run every hour
    while True:
        await check_new_videos()
        await asyncio.sleep(3600)  # Sleep for 1 hour

if __name__ == "__main__":
    asyncio.run(main()) 