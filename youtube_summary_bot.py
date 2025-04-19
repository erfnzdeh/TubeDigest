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
        self.processed_videos = self.load_processed_videos()
        
        # Initialize API clients
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.telegram_bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def load_processed_videos(self) -> set:
        """Load processed videos from JSON file."""
        try:
            with open('processed_videos.json', 'r') as f:
                data = json.load(f)
                return set(data.get('processed_videos', []))
        except FileNotFoundError:
            return set()
        except json.JSONDecodeError:
            logger.error("Error reading processed_videos.json, starting with empty set")
            return set()

    def save_processed_videos(self):
        """Save processed videos to JSON file."""
        try:
            with open('processed_videos.json', 'w') as f:
                json.dump({'processed_videos': list(self.processed_videos)}, f)
        except Exception as e:
            logger.error(f"Error saving processed videos: {e}")

    def get_channel_uploads(self) -> List[Dict]:
        """Fetch recent uploads from a YouTube channel."""
        try:
            # Get channel's uploads playlist ID
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=self.youtube_channel_id
            ).execute()
            
            # Check if the response contains items
            if 'items' not in channel_response or not channel_response['items']:
                logger.error(f"No channel found for ID: {self.youtube_channel_id}")
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
            logger.error(f"Error fetching channel uploads: {e}")
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
            raise

    @backoff.on_exception(
        backoff.expo,
        (Exception),
        max_tries=3,
        max_time=60  # Increased timeout from 30 to 60 seconds
    )
    async def send_telegram_message(self, video_title: str, summary: str, video_url: str, thumbnail_url: str) -> None:
        """Send summary to Telegram channel with retry logic."""
        try:
            # Sanitize the text to prevent Markdown parsing errors
            def sanitize_markdown(text):
                # Escape special Markdown characters that might cause parsing errors
                special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                for char in special_chars:
                    text = text.replace(char, '\\' + char)
                return text
            
            # Telegram caption limit is 1024 characters
            # Reserve space for formatting
            caption_limit = 900  # 1024 - ~124 (for formatting)
            
            # First message with thumbnail and beginning of summary
            first_message = summary[:caption_limit] if len(summary) > caption_limit else summary
            caption = first_message
            
            # Add continuation indicator to the first message if there's more content
            if len(summary) > caption_limit:
                caption += "\n\n_continues in next message_"
            
            # Send the first message with the thumbnail
            try:
                sent_message = await self.telegram_bot.send_photo(
                    chat_id=self.telegram_channel_id,
                    photo=thumbnail_url,
                    caption=caption,
                    parse_mode='Markdown'
                )
            except Exception as e:
                # If Markdown parsing fails, try again without Markdown
                logger.warning(f"Markdown parsing failed, retrying without Markdown: {e}")
                sent_message = await self.telegram_bot.send_photo(
                    chat_id=self.telegram_channel_id,
                    photo=thumbnail_url,
                    caption=sanitize_markdown(caption),
                    parse_mode=None
                )
            
            # If summary is longer than the caption limit, send the rest as separate messages
            if len(summary) > caption_limit:
                remaining_summary = summary[caption_limit:]
                # Split the remaining summary into chunks that fit within Telegram's message limit
                # Keep track of the last message to add the source to it
                last_message = None
                message_count = 1
                
                while remaining_summary:
                    chunk = remaining_summary[:4000]  # Telegram message limit is 4096
                    message_count += 1
                    # Add continuation indicator if there's more content coming
                    if remaining_summary[4000:]:
                        chunk += "\n\n_continues in next message_"
                    
                    try:
                        last_message = await self.telegram_bot.send_message(
                            chat_id=self.telegram_channel_id,
                            text=chunk,
                            parse_mode='Markdown',
                            reply_to_message_id=sent_message.message_id,
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        # If Markdown parsing fails, try again without Markdown
                        logger.warning(f"Markdown parsing failed for chunk, retrying without Markdown: {e}")
                        last_message = await self.telegram_bot.send_message(
                            chat_id=self.telegram_channel_id,
                            text=sanitize_markdown(chunk),
                            parse_mode=None,
                            reply_to_message_id=sent_message.message_id,
                            disable_web_page_preview=True
                        )
                    
                    remaining_summary = remaining_summary[4000:]
                
                # Add source information to the last message
                if last_message:
                    source_info = f"\n\nSource: [{video_title}]({video_url})"
                    # Check if adding source info would exceed message limit
                    if len(chunk) + len(source_info) <= 4000:
                        try:
                            # Edit the last message to add source info
                            await self.telegram_bot.edit_message_text(
                                chat_id=self.telegram_channel_id,
                                message_id=last_message.message_id,
                                text=chunk + source_info,
                                parse_mode='Markdown',
                                disable_web_page_preview=True
                            )
                        except Exception as e:
                            # If Markdown parsing fails, try again without Markdown
                            logger.warning(f"Markdown parsing failed for edited message, retrying without Markdown: {e}")
                            await self.telegram_bot.edit_message_text(
                                chat_id=self.telegram_channel_id,
                                message_id=last_message.message_id,
                                text=sanitize_markdown(chunk + source_info),
                                parse_mode=None,
                                disable_web_page_preview=True
                            )
                    else:
                        # Send source info as a separate message if it would exceed limit
                        try:
                            await self.telegram_bot.send_message(
                                chat_id=self.telegram_channel_id,
                                text=source_info,
                                parse_mode='Markdown',
                                reply_to_message_id=sent_message.message_id,
                                disable_web_page_preview=True
                            )
                        except Exception as e:
                            # If Markdown parsing fails, try again without Markdown
                            logger.warning(f"Markdown parsing failed for source info, retrying without Markdown: {e}")
                            await self.telegram_bot.send_message(
                                chat_id=self.telegram_channel_id,
                                text=sanitize_markdown(source_info),
                                parse_mode=None,
                                reply_to_message_id=sent_message.message_id,
                                disable_web_page_preview=True
                            )
            else:
                # If summary fits in one message, add source info to it
                source_info = f"\n\nSource: {video_title} - {video_url}"
                # Check if adding source info would exceed caption limit
                if len(caption) + len(source_info) <= caption_limit:
                    try:
                        # Edit the message to add source info
                        await self.telegram_bot.edit_message_caption(
                            chat_id=self.telegram_channel_id,
                            message_id=sent_message.message_id,
                            caption=caption + source_info,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        # If Markdown parsing fails, try again without Markdown
                        logger.warning(f"Markdown parsing failed for caption edit, retrying without Markdown: {e}")
                        await self.telegram_bot.edit_message_caption(
                            chat_id=self.telegram_channel_id,
                            message_id=sent_message.message_id,
                            caption=sanitize_markdown(caption + source_info),
                            parse_mode=None
                        )
                else:
                    # Send source info as a separate message if it would exceed limit
                    try:
                        await self.telegram_bot.send_message(
                            chat_id=self.telegram_channel_id,
                            text=source_info,
                            parse_mode='Markdown',
                            reply_to_message_id=sent_message.message_id,
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        # If Markdown parsing fails, try again without Markdown
                        logger.warning(f"Markdown parsing failed for source info, retrying without Markdown: {e}")
                        await self.telegram_bot.send_message(
                            chat_id=self.telegram_channel_id,
                            text=sanitize_markdown(source_info),
                            parse_mode=None,
                            reply_to_message_id=sent_message.message_id,
                            disable_web_page_preview=True
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
                
            # Skip if it's a Short
            if self.is_short(video_id):
                logger.info(f"Skipping Short: {video['snippet']['title']}")
                # Mark as processed to avoid checking it again
                self.processed_videos.add(video_id)
                self.save_processed_videos()
                continue
                
            logger.info(f"Processing new video: {video['snippet']['title']}")
            
            # Get transcript and generate summary
            transcript = self.get_video_transcript(video_id)
            if transcript:
                try:
                    summary = self.generate_summary(transcript)
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
                    await self.send_telegram_message(video['snippet']['title'], summary, video_url, thumbnail_url)
                    
                    # Mark as processed and save
                    self.processed_videos.add(video_id)
                    self.save_processed_videos()
                except Exception as e:
                    logger.error(f"Failed to process video {video_id}: {e}")
                    # Don't mark as processed so we can try again later
                
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