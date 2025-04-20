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

# Define data directory
DATA_DIR = '/data'

class YouTubeSummaryBot:
    def __init__(self):
        # Initialize API clients
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.telegram_bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Load channel mappings
        self.channel_mappings = self.load_channel_mappings()
        
        # Initialize processed videos tracking for each channel
        self.processed_videos = {}
        for mapping in self.channel_mappings:
            youtube_channel_id = mapping['youtube_channel_id']
            self.processed_videos[youtube_channel_id] = self.load_processed_videos(youtube_channel_id)

    def load_channel_mappings(self) -> List[Dict]:
        """Load channel mappings from JSON file."""
        try:
            with open(os.path.join(DATA_DIR, 'channel_mappings.json'), 'r') as f:
                config = json.load(f)
                return config['channel_mappings']
        except FileNotFoundError:
            logger.error("channel_mappings.json file not found")
            return []
        except json.JSONDecodeError:
            logger.error("Invalid JSON format in channel_mappings.json")
            return []

    def load_processed_videos(self, youtube_channel_id: str) -> set:
        """Load processed videos from JSON file for a specific channel."""
        filename = os.path.join(DATA_DIR, f'processed_videos_{youtube_channel_id}.json')
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                return set(data.get('processed_videos', []))
        except FileNotFoundError:
            return set()
        except json.JSONDecodeError:
            logger.error(f"Error reading {filename}, starting with empty set")
            return set()

    def save_processed_videos(self, youtube_channel_id: str):
        """Save processed videos to JSON file for a specific channel."""
        filename = os.path.join(DATA_DIR, f'processed_videos_{youtube_channel_id}.json')
        try:
            with open(filename, 'w') as f:
                json.dump({'processed_videos': list(self.processed_videos[youtube_channel_id])}, f)
        except Exception as e:
            logger.error(f"Error saving processed videos for channel {youtube_channel_id}: {e}")

    def get_channel_uploads(self, youtube_channel_id: str) -> List[Dict]:
        """Fetch recent uploads from a YouTube channel."""
        try:
            # Get channel's uploads playlist ID
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=youtube_channel_id
            ).execute()
            
            # Check if the response contains items
            if 'items' not in channel_response or not channel_response['items']:
                logger.error(f"No channel found for ID: {youtube_channel_id}")
                return []
                
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get recent videos from uploads playlist
            playlist_response = self.youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=5
            ).execute()
            
            # Check if the response contains items
            if 'items' not in playlist_response:
                logger.error(f"No videos found in playlist: {uploads_playlist_id}")
                return []
                
            return playlist_response['items']
        except Exception as e:
            logger.error(f"Error fetching channel uploads for {youtube_channel_id}: {e}")
            return []

    def is_short(self, video_id: str) -> bool:
        """Check if a video is a YouTube Short using the URL format."""
        try:
            # Check if the video URL contains "/shorts/"
            # This is the most reliable way to identify Shorts
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            return "/shorts/" in video_url
        except Exception as e:
            logger.error(f"Error checking if video {video_id} is a Short: {e}")
            return False

    def get_video_transcript(self, video_id: str) -> str:
        """Fetch transcript for a YouTube video."""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return ' '.join([entry['text'] for entry in transcript_list])
        except Exception as e:
            logger.error(f"Error fetching transcript: {e}")
            return ""

    def generate_summary(self, transcript: str, prompt: Dict) -> str:
        """Generate a summary using OpenAI's API."""
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"].format(transcript=transcript)}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            raise

    @backoff.on_exception(
        backoff.expo,
        (Exception),
        max_tries=5,  # Increased from 3 to 5
        max_time=120  # Increased from 60 to 120 seconds
    )
    async def send_telegram_message(self, video_title: str, summary: str, video_url: str, thumbnail_url: str, telegram_channel_id: str) -> None:
        """Send summary to Telegram channel with retry logic."""
        try:
            # Telegram caption limit is 1024 characters
            # Reserve space for formatting
            caption_limit = 900  # 1024 - ~124 (for formatting)
            
            def split_at_word_boundary(text: str, max_length: int) -> tuple[str, str]:
                """Split text at the last complete word before max_length."""
                if len(text) <= max_length:
                    return text, ""
                
                # Find the last space before max_length
                split_index = text.rfind(' ', 0, max_length)
                if split_index == -1:  # No space found, force split at max_length
                    split_index = max_length
                
                return text[:split_index].strip(), text[split_index:].strip()
            
            # First message with thumbnail and beginning of summary
            first_message, remaining_summary = split_at_word_boundary(summary, caption_limit)
            caption = first_message
            
            # Add continuation indicator to the first message if there's more content
            if remaining_summary:
                caption += " ⬇️"
            
            # Send the first message with the thumbnail
            # Set a longer timeout for the API call
            sent_message = await asyncio.wait_for(
                self.telegram_bot.send_photo(
                    chat_id=telegram_channel_id,
                    photo=thumbnail_url,
                    caption=caption,
                    parse_mode='Markdown'
                ),
                timeout=30  # 30 second timeout
            )
            
            # If summary is longer than the caption limit, send the rest as separate messages
            if remaining_summary:
                # Keep track of the last message to add the source to it
                last_message = None
                message_count = 1
                
                while remaining_summary:
                    chunk, remaining_summary = split_at_word_boundary(remaining_summary, 4000)  # Telegram message limit is 4096
                    message_count += 1
                    # Add continuation indicator if there's more content coming
                    if remaining_summary:
                        chunk += " ⬇️"
                    
                    # Set a longer timeout for the API call
                    last_message = await asyncio.wait_for(
                        self.telegram_bot.send_message(
                            chat_id=telegram_channel_id,
                            text=chunk,
                            parse_mode='Markdown',
                            reply_to_message_id=sent_message.message_id,
                            disable_web_page_preview=True
                        ),
                        timeout=30  # 30 second timeout
                    )
                
                # Add source information to the last message
                if last_message:
                    source_info = f"\n\nSource: [{video_title}]({video_url})"
                    # Check if adding source info would exceed message limit
                    if len(chunk) + len(source_info) <= 4000:
                        # Set a longer timeout for the API call
                        await asyncio.wait_for(
                            self.telegram_bot.edit_message_text(
                                chat_id=telegram_channel_id,
                                message_id=last_message.message_id,
                                text=chunk + source_info,
                                parse_mode='Markdown',
                                disable_web_page_preview=True
                            ),
                            timeout=30  # 30 second timeout
                        )
                    else:
                        # Send source info as a separate message if it would exceed limit
                        # Set a longer timeout for the API call
                        await asyncio.wait_for(
                            self.telegram_bot.send_message(
                                chat_id=telegram_channel_id,
                                text=source_info,
                                parse_mode='Markdown',
                                reply_to_message_id=sent_message.message_id,
                                disable_web_page_preview=True
                            ),
                            timeout=30  # 30 second timeout
                        )
            else:
                # If summary fits in one message, add source info to it
                source_info = f"\n\nSource: [{video_title}]({video_url})"
                # Check if adding source info would exceed caption limit
                if len(caption) + len(source_info) <= caption_limit:
                    # Set a longer timeout for the API call
                    await asyncio.wait_for(
                        self.telegram_bot.edit_message_caption(
                            chat_id=telegram_channel_id,
                            message_id=sent_message.message_id,
                            caption=caption + source_info,
                            parse_mode='Markdown'
                        ),
                        timeout=30  # 30 second timeout
                    )
                else:
                    # Send source info as a separate message if it would exceed limit
                    # Set a longer timeout for the API call
                    await asyncio.wait_for(
                        self.telegram_bot.send_message(
                            chat_id=telegram_channel_id,
                            text=source_info,
                            parse_mode='Markdown',
                            reply_to_message_id=sent_message.message_id,
                            disable_web_page_preview=True
                        ),
                        timeout=30  # 30 second timeout
                    )
            
            logger.info(f"Successfully sent message for video: {video_title}")
        except Exception as e:
            logger.error(f"Error sending Telegram message for video {video_title}: {str(e)}")
            raise

    async def check_new_videos(self):
        """Check for new videos from all monitored channels."""
        for mapping in self.channel_mappings:
            youtube_channel_id = mapping['youtube_channel_id']
            telegram_channel_id = mapping['telegram_channel_id']
            prompt = mapping['prompt']
            
            logger.info(f"Checking for new videos for channel {youtube_channel_id}...")
            
            videos = self.get_channel_uploads(youtube_channel_id)
            
            for video in videos:
                video_id = video['snippet']['resourceId']['videoId']
                
                # Skip if already processed
                if video_id in self.processed_videos[youtube_channel_id]:
                    continue
                    
                # Skip if it's a Short
                if self.is_short(video_id):
                    logger.info(f"Skipping Short: {video['snippet']['title']}")
                    # Mark as processed to avoid checking it again
                    self.processed_videos[youtube_channel_id].add(video_id)
                    self.save_processed_videos(youtube_channel_id)
                    continue
                    
                logger.info(f"Processing new video: {video['snippet']['title']}")
                
                # Get transcript and generate summary
                transcript = self.get_video_transcript(video_id)
                if transcript:
                    try:
                        summary = self.generate_summary(transcript, prompt)
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        
                        # Get the highest quality thumbnail available
                        thumbnails = video['snippet']['thumbnails']
                        # YouTube provides different sizes: default, medium, high, standard, maxres
                        # Try to get the highest quality available
                        if 'maxres' in thumbnails:
                            thumbnail_url = thumbnails['maxres']['url']
                        elif 'standard' in thumbnails:
                            thumbnail_url = thumbnails['standard']['url']
                        elif 'high' in thumbnails:
                            thumbnail_url = thumbnails['high']['url']
                        elif 'medium' in thumbnails:
                            thumbnail_url = thumbnails['medium']['url']
                        else:
                            thumbnail_url = thumbnails['default']['url']
                        
                        # Send to Telegram
                        await self.send_telegram_message(
                            video['snippet']['title'], 
                            summary, 
                            video_url, 
                            thumbnail_url,
                            telegram_channel_id
                        )
                        
                        # Mark as processed and save
                        self.processed_videos[youtube_channel_id].add(video_id)
                        self.save_processed_videos(youtube_channel_id)
                    except Exception as e:
                        logger.error(f"Failed to process video {video_id}: {e}")
                        # Don't mark as processed so we can try again later
                    
                    # Sleep to avoid rate limits
                    time.sleep(2)

    async def run(self):
        """Run the bot instance."""
        logger.info("Starting YouTube Summary Bot...")
        
        while True:
            await self.check_new_videos()
            await asyncio.sleep(3600)  # Sleep for 1 hour

async def main():
    """Main function to run the bot."""
    bot = YouTubeSummaryBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())