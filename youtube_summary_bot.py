import os
import time
import logging
import asyncio
import json
import requests
import random
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Optional
import backoff
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

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
DATA_DIR = 'data'

class ProxyManager:
    """Manages proxy list fetching and rotation for YouTube API calls."""
    
    def __init__(self):
        self.proxies = []
        self.current_proxy_index = 0  # Track current position in proxy list
        self.last_updated = None
        self.update_interval = 3600  # Update proxies every hour
        self.api_url = "https://proxylist.geonode.com/api/proxy-list"
        self.session = requests.Session()
        # Set a reasonable user agent to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Clean up any invalid fallback proxies on startup
        self.clean_fallback_proxies()
        
    def fetch_proxies_from_geonode(self) -> List[Dict]:
        """Fetch proxy list from geonode.com API."""
        try:
            logger.info("Fetching proxy list from geonode.com API...")
            
            all_proxies = []
            max_proxies_needed = 25
            page = 1
            
            # Fetch multiple pages to get enough proxies
            while len(all_proxies) < max_proxies_needed and page <= 3:  # Max 3 pages
                # API parameters
                params = {
                    'limit': 500,
                    'page': page,
                    'sort_by': 'lastChecked',
                    'sort_type': 'desc',
                    'protocols': 'http,https'  # Only get HTTP/HTTPS proxies
                }
                
                # Make request to geonode API
                response = self.session.get(self.api_url, params=params, timeout=30)
                response.raise_for_status()
                
                # Parse JSON response
                data = response.json()
                
                if 'data' not in data or not data['data']:
                    logger.info(f"No more proxies available on page {page}")
                    break
                
                page_proxies = []
                for proxy_data in data['data']:
                    # Extract proxy information
                    ip = proxy_data.get('ip')
                    port = proxy_data.get('port')
                    protocols = proxy_data.get('protocols', [])
                    
                    if ip and port and protocols:
                        # Add proxy for each supported protocol
                        for protocol in protocols:
                            if protocol.lower() in ['http', 'https']:
                                page_proxies.append({
                                    'ip': ip,
                                    'port': int(port),
                                    'protocol': protocol.lower(),
                                    'country': proxy_data.get('country', ''),
                                    'speed': proxy_data.get('speed', 0),
                                    'uptime': proxy_data.get('upTime', 0),
                                    'anonymity': proxy_data.get('anonymityLevel', ''),
                                    'last_checked': proxy_data.get('lastChecked', '')
                                })
                
                all_proxies.extend(page_proxies)
                logger.info(f"Page {page}: Got {len(page_proxies)} proxies (total: {len(all_proxies)})")
                
                # If we have enough, stop
                if len(all_proxies) >= max_proxies_needed:
                    break
                    
                page += 1
            
            # Take only what we need
            final_proxies = all_proxies[:max_proxies_needed]
            logger.info(f"Successfully fetched {len(final_proxies)} proxies from geonode.com API")
            return final_proxies
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching proxies from geonode.com API: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from geonode.com API: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching proxies from geonode.com API: {e}")
            return []
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            
            # Check each octet
            for part in parts:
                num = int(part)
                if not (0 <= num <= 255):
                    return False
            
            # Check if it's a public IP (not private/local)
            first_octet = int(parts[0])
            second_octet = int(parts[1])
            
            # Filter out private IP ranges
            if (first_octet == 10 or  # 10.0.0.0/8
                (first_octet == 172 and 16 <= second_octet <= 31) or  # 172.16.0.0/12
                (first_octet == 192 and second_octet == 168) or  # 192.168.0.0/16
                first_octet == 127 or  # 127.0.0.0/8 (localhost)
                first_octet == 0 or  # 0.0.0.0/8
                first_octet >= 224):  # Multicast and reserved ranges
                return False
                
            return True
        except (ValueError, AttributeError):
            return False
    
    def _is_valid_port(self, port: str) -> bool:
        """Validate port number."""
        try:
            port_num = int(port)
            return 1 <= port_num <= 65535
        except (ValueError, TypeError):
            return False
    
    def load_fallback_proxies(self) -> List[Dict]:
        """Load fallback proxies from file if geonode.com is unavailable."""
        try:
            filename = os.path.join(DATA_DIR, 'fallback_proxies.json')
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    data = json.load(f)
                    proxies = data.get('proxies', [])
                    
                    # Filter out invalid proxies (like test data with private IPs)
                    valid_proxies = []
                    for proxy in proxies:
                        if (self._is_valid_ip(proxy.get('ip', '')) and 
                            self._is_valid_port(str(proxy.get('port', '')))):
                            valid_proxies.append(proxy)
                    
                    if len(valid_proxies) != len(proxies):
                        logger.info(f"Filtered fallback proxies from {len(proxies)} to {len(valid_proxies)} valid proxies")
                        # Save the cleaned list back
                        if valid_proxies:
                            self.save_fallback_proxies(valid_proxies)
                        else:
                            # If no valid proxies, remove the file
                            os.remove(filename)
                            logger.info("Removed invalid fallback proxy file")
                    
                    return valid_proxies
        except Exception as e:
            logger.error(f"Error loading fallback proxies: {e}")
        return []
    
    def save_fallback_proxies(self, proxies: List[Dict]):
        """Save working proxies as fallback."""
        try:
            filename = os.path.join(DATA_DIR, 'fallback_proxies.json')
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(filename, 'w') as f:
                json.dump({'proxies': proxies, 'updated': datetime.now().isoformat()}, f)
        except Exception as e:
            logger.error(f"Error saving fallback proxies: {e}")
    
    def test_proxy(self, proxy: Dict) -> bool:
        """Test if a proxy is working."""
        try:
            proxy_url = f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
            test_proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
            
            # Test with a simple request
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=test_proxies,
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def filter_proxies(self, proxies: List[Dict]) -> List[Dict]:
        """Keep proxies in original order (sorted by API response)."""
        if not proxies:
            return []
        
        # Keep original order - API already sorts by lastChecked/ping
        logger.info(f"Keeping {len(proxies)} proxies in original order for sequential rotation")
        return proxies
    
    def update_proxies(self):
        """Update the proxy list."""
        current_time = time.time()
        
        if (self.last_updated is None or 
            current_time - self.last_updated > self.update_interval):
            
            logger.info("Updating proxy list...")
            new_proxies = self.fetch_proxies_from_geonode()
            
            if new_proxies:
                # Keep proxies in original order
                ordered_proxies = self.filter_proxies(new_proxies)
                self.proxies = ordered_proxies
                self.current_proxy_index = 0  # Reset to start of new list
                
                # Test a few proxies to save some working ones as fallback
                working_proxies = []
                sample_size = min(5, len(self.proxies))  # Test 5 proxies max
                sample_proxies = self.proxies[:sample_size]  # Take first 5 instead of random
                
                for proxy in sample_proxies:
                    if self.test_proxy(proxy):
                        working_proxies.append(proxy)
                
                if working_proxies:
                    self.save_fallback_proxies(working_proxies)
                    logger.info(f"Updated proxy list with {len(self.proxies)} proxies ({len(working_proxies)} tested working)")
                else:
                    logger.info(f"Updated proxy list with {len(self.proxies)} proxies (none tested yet)")
                    
                self.last_updated = current_time
                    
            else:
                logger.warning("Failed to fetch new proxies, using fallback proxies")
                fallback_proxies = self.load_fallback_proxies()
                if fallback_proxies:
                    # Keep fallback proxies in order too
                    self.proxies = self.filter_proxies(fallback_proxies)
                    self.current_proxy_index = 0  # Reset index
                    logger.info(f"Loaded {len(self.proxies)} fallback proxies in order")
                else:
                    logger.warning("No fallback proxies available")
                
                # Set last_updated to avoid immediate retry on network issues
                # but with shorter interval (15 minutes instead of 1 hour)
                self.last_updated = current_time - self.update_interval + 900
    
    def get_next_proxy(self) -> Optional[Dict]:
        """Get the next proxy in sequence from the list."""
        self.update_proxies()
        
        if not self.proxies:
            logger.warning("No proxies available")
            return None
        
        # Get next proxy in sequence
        proxy = self.proxies[self.current_proxy_index]
        proxy_url = f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
        
        # Move to next proxy for next call
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def clean_fallback_proxies(self):
        """Clean up invalid fallback proxies."""
        try:
            filename = os.path.join(DATA_DIR, 'fallback_proxies.json')
            if os.path.exists(filename):
                valid_proxies = self.load_fallback_proxies()
                if not valid_proxies:
                    os.remove(filename)
                    logger.info("Removed empty fallback proxy file")
        except Exception as e:
            logger.error(f"Error cleaning fallback proxies: {e}")

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for health checks."""
    
    def do_GET(self):
        if self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'TubeDigest Bot is running!')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress HTTP server logs to avoid clutter
        pass

def start_health_server():
    """Start a simple HTTP server for health checks."""
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server starting on port {port}")
    server.serve_forever()

class YouTubeSummaryBot:
    def __init__(self):
        # Initialize API clients
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.telegram_bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Initialize proxy manager
        self.proxy_manager = ProxyManager()
        
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
        """Fetch transcript for a YouTube video using sequential proxy rotation."""
        max_retries = 5  # Increased retries since we have more proxies
        use_proxies = os.getenv('USE_PROXIES', 'true').lower() == 'true'
        
        # Get available proxies for sequential rotation
        if use_proxies:
            self.proxy_manager.update_proxies()
            available_proxies = self.proxy_manager.proxies.copy()  # Keep original order
        else:
            available_proxies = []
        
        for attempt in range(max_retries):
            try:
                # Try with proxy for first attempts (if available and enabled)
                if attempt < max_retries - 1 and use_proxies and available_proxies:
                    # Get next proxy in sequence
                    proxy_index = attempt % len(available_proxies)
                    proxy_data = available_proxies[proxy_index]
                    
                    proxy_url = f"{proxy_data['protocol']}://{proxy_data['ip']}:{proxy_data['port']}"
                    proxy = {
                        'http': proxy_url,
                        'https': proxy_url
                    }
                    
                    logger.info(f"Attempting to fetch transcript for {video_id} using proxy {proxy_index + 1}/{len(available_proxies)}: {proxy_data['ip']}:{proxy_data['port']} (attempt {attempt + 1})")
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=proxy)
                    return ' '.join([entry['text'] for entry in transcript_list])
                
                # Last attempt or no proxies available - try direct connection
                logger.info(f"Attempting to fetch transcript for {video_id} without proxy (attempt {attempt + 1})")
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                return ' '.join([entry['text'] for entry in transcript_list])
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for video {video_id}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Short wait between retries
                else:
                    logger.error(f"All {max_retries} attempts failed for video {video_id}")
                    return ""
        
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
    # Start health check server in a separate thread
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Create and run the bot
    bot = YouTubeSummaryBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())