
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
from youtube_transcript_api.proxies import WebshareProxyConfig
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
DATA_DIR = 'data'

class YouTubeSummaryBot:
    def __init__(self):
        # Initialize API clients
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.telegram_bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize YouTube Transcript API with proxy
        self.ytt_api = YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=os.getenv('WEBSHARE_PROXY_USERNAME'),
                proxy_password=os.getenv('WEBSHARE_PROXY_PASSWORD')
            )
        )
        
        # Load channel mappings
        self.channel_mappings = self.load_channel_mappings()

    def load_channel_mappings(self) -> List[Dict]:
        """Load channel mappings from JSON file."""
        try:
            with open(os.path.join(DATA_DIR, 'data.json'), 'r') as f:
                config = json.load(f)
                return config['channel_mappings']
        except FileNotFoundError:
            logger.error("data.json file not found")
            return []
        except json.JSONDecodeError:
            logger.error("Invalid JSON format in data.json")
            return []

    def save_channel_mappings(self):
        """Save channel mappings to JSON file."""
        try:
            with open(os.path.join(DATA_DIR, 'data.json'), 'w') as f:
                json.dump({'channel_mappings': self.channel_mappings}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving channel mappings: {e}")

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
                logger.error(f"❌ No channel: {youtube_channel_id}")
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
                logger.error(f"❌ No videos in playlist: {uploads_playlist_id}")
                return []
                
            return playlist_response['items']
        except Exception as e:
            logger.error(f"❌ Channel fetch failed {youtube_channel_id}: {str(e)}")
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
        """Fetch transcript for a YouTube video using proxy."""
        try:
            transcript_list = self.ytt_api.get_transcript(video_id)
            transcript = ' '.join([entry['text'] for entry in transcript_list])
            if transcript:
                logger.info(f"📝 Got transcript: {video_id}")
            return transcript
        except Exception as e:
            logger.error(f"❌ Transcript fetch failed: {str(e)}")
            return ""

    def generate_summary(self, transcript: str, prompt: Dict) -> str:
        """Generate a summary using OpenAI's API."""
        try:
            logger.info("🤖 Generating GPT summary...")
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"].format(transcript=transcript)}
                ]
            )
            logger.info("✨ Summary generated")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"❌ Summary generation failed: {str(e)}")
            raise

    @backoff.on_exception(
        backoff.expo,
        (Exception),
        max_tries=5,
        max_time=120
    )
    async def send_telegram_message(self, video_title: str, summary: str, video_url: str, thumbnail_url: str, telegram_channel_id: str) -> None:
        """Send summary to Telegram channel with retry logic."""
        try:
            logger.info("📤 Preparing Telegram message...")
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
            
            logger.info(f"✅ Sent: {video_title[:50]}...")
        except Exception as e:
            logger.error(f"❌ Telegram send failed: {str(e)}")
            raise

    async def check_and_add_new_videos(self):
        """Check for new videos and add them to the unprocessed queue."""
        for mapping in self.channel_mappings:
            youtube_channel_id = mapping['youtube_channel_id']
            
            logger.info(f"🔍 Checking: {youtube_channel_id}")
            
            videos = self.get_channel_uploads(youtube_channel_id)
            
            for video in videos:
                video_id = video['snippet']['resourceId']['videoId']
                
                # Skip if already processed or in queue
                if video_id in mapping['processed_videos'] or video_id in mapping['unprocessed_videos']:
                    continue
                    
                # Skip if it's a Short
                if self.is_short(video_id):
                    logger.info(f"⏭️ Skip Short: {video['snippet']['title'][:50]}...")
                    mapping['processed_videos'].append(video_id)
                    self.save_channel_mappings()
                    continue
                    
                logger.info(f"➕ Queue: {video['snippet']['title'][:50]}...")
                
                # Add to unprocessed queue
                mapping['unprocessed_videos'].append(video_id)
                self.save_channel_mappings()

    async def process_pending_videos(self):
        """Process one video from the unprocessed queue (earliest one added)."""
        earliest_video = None
        earliest_mapping = None
        earliest_add_time = None

        # Find the earliest unprocessed video across all channels
        for mapping in self.channel_mappings:
            if mapping['unprocessed_videos']:
                video_id = mapping['unprocessed_videos'][0]
                
                try:
                    video_response = self.youtube.videos().list(
                        part='snippet',
                        id=video_id
                    ).execute()
                    
                    if video_response.get('items'):
                        video = video_response['items'][0]
                        publish_time = video['snippet']['publishedAt']
                        publish_datetime = datetime.strptime(publish_time, '%Y-%m-%dT%H:%M:%SZ')
                        
                        if earliest_add_time is None or publish_datetime < earliest_add_time:
                            earliest_video = video
                            earliest_mapping = mapping
                            earliest_add_time = publish_datetime
                except Exception as e:
                    logger.error(f"❌ Video fetch failed {video_id}: {str(e)}")
                    continue

        if earliest_video and earliest_mapping:
            video_id = earliest_video['id']
            telegram_channel_id = earliest_mapping['telegram_channel_id']
            prompt = earliest_mapping['prompt']
            
            logger.info(f"🎬 Processing: {earliest_video['snippet']['title'][:50]}...")
            
            transcript = self.get_video_transcript(video_id)
            if transcript:
                try:
                    summary = self.generate_summary(transcript, prompt)
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    thumbnails = earliest_video['snippet']['thumbnails']
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
                    
                    await self.send_telegram_message(
                        earliest_video['snippet']['title'], 
                        summary, 
                        video_url, 
                        thumbnail_url,
                        telegram_channel_id
                    )
                    
                    earliest_mapping['unprocessed_videos'].remove(video_id)
                    earliest_mapping['processed_videos'].append(video_id)
                    self.save_channel_mappings()
                except Exception as e:
                    logger.error(f"❌ Processing failed {video_id}: {str(e)}")

    async def run_check_new_videos(self):
        """Run the check for new videos loop."""
        while True:
            try:
                await self.check_and_add_new_videos()
            except Exception as e:
                logger.error(f"❌ Check loop failed: {str(e)}")
            await asyncio.sleep(1800)  # Run every 30 minutes

    async def run_process_videos(self):
        """Run the video processing loop."""
        while True:
            try:
                await self.process_pending_videos()
            except Exception as e:
                logger.error(f"❌ Process loop failed: {str(e)}")
            await asyncio.sleep(300)  # Run every 5 minutes

    async def run(self):
        """Run the bot instance."""
        logger.info("🚀 Starting YouTube Summary Bot...")
        
        check_task = asyncio.create_task(self.run_check_new_videos())
        process_task = asyncio.create_task(self.run_process_videos())
        
        try:
            await asyncio.gather(check_task, process_task)
        except Exception as e:
            logger.error(f"❌ Critical error: {str(e)}")
            check_task.cancel()
            process_task.cancel()
            raise

async def main():
    """Main function to run the bot."""
    bot = YouTubeSummaryBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())