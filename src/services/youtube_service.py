import os
from typing import List, Dict
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import datetime, timedelta, UTC

class YouTubeService:
    def __init__(self):
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))

    def get_channel_uploads(self, channel_id: str) -> List[Dict]:
        """Fetch recent uploads from a YouTube channel."""
        try:
            # Get channel's uploads playlist ID
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=channel_id
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
            print(f"Error fetching channel uploads: {e}")
            return []

    def get_video_transcript(self, video_id: str) -> str:
        """Fetch transcript for a YouTube video."""
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            return ' '.join([entry['text'] for entry in transcript_list])
        except Exception as e:
            print(f"Error fetching transcript: {e}")
            return ""

    def is_recent_video(self, published_at: str) -> bool:
        """Check if a video was published within the last 24 hours."""
        try:
            published_datetime = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
            return datetime.now(UTC) - published_datetime <= timedelta(hours=24)
        except Exception:
            return False 