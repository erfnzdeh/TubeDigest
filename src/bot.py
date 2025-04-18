import os
import asyncio
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler as TelegramCommandHandler
from telegram import Update

from src.database.connection import get_db, engine
from src.models.user import User
from src.models.channel import Channel
from src.models.video import Video
from src.services.youtube_service import YouTubeService
from src.services.openai_service import OpenAIService
from src.handlers.command_handler import CommandHandler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TubeDigestBot:
    def __init__(self):
        self.youtube_service = YouTubeService()
        self.openai_service = OpenAIService()
        self.db = next(get_db())
        self.command_handler = CommandHandler(self.db, self.youtube_service)
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.bot_id = int(self.bot_token.split(':')[0]) if self.bot_token else None
        self.application = None

    async def check_new_videos(self):
        """Check for new videos from monitored channels"""
        logger.info("Starting periodic video check")
        try:
            # Get all monitored channels
            channels = self.db.query(Channel).all()
            logger.info(f"Found {len(channels)} monitored channels")

            for channel in channels:
                logger.info(f"Checking videos for channel: {channel.title} ({channel.youtube_id})")
                try:
                    # Get latest videos
                    videos = self.youtube_service.get_latest_videos(channel.youtube_id)
                    logger.info(f"Found {len(videos)} videos for channel {channel.title}")

                    for video in videos:
                        # Check if video already processed
                        existing_video = self.db.query(Video).filter(
                            Video.youtube_id == video['id']
                        ).first()

                        if not existing_video:
                            logger.info(f"Processing new video: {video['title']}")
                            # Generate summary
                            summary = self.openai_service.generate_summary(video['description'])
                            
                            # Save video to database
                            new_video = Video(
                                youtube_id=video['id'],
                                title=video['title'],
                                description=video['description'],
                                summary=summary,
                                channel_id=channel.id,
                                published_at=video['published_at']
                            )
                            self.db.add(new_video)
                            self.db.commit()
                            logger.info(f"Saved new video to database: {video['title']}")

                            # Send summary to user
                            message = (
                                f"📺 New video from {channel.title}!\n\n"
                                f"Title: {video['title']}\n\n"
                                f"Summary:\n{summary}\n\n"
                                f"Watch here: https://youtube.com/watch?v={video['id']}"
                            )
                            
                            # Get user's chat ID from channel
                            user = self.db.query(User).filter(User.id == channel.user_id).first()
                            if user and user.telegram_id and user.telegram_id != self.bot_id:
                                try:
                                    await self.application.bot.send_message(
                                        chat_id=user.telegram_id,
                                        text=message
                                    )
                                    logger.info(f"Sent video summary to user {user.telegram_id}")
                                except Exception as e:
                                    logger.error(f"Failed to send message to user {user.telegram_id}: {str(e)}")
                            else:
                                logger.warning(f"Could not find valid user for channel {channel.title}")

                except Exception as e:
                    logger.error(f"Error processing channel {channel.title}: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"Error in check_new_videos: {str(e)}")
        finally:
            logger.info("Completed periodic video check")

    async def start(self):
        """Start the bot"""
        logger.info("Starting TubeDigest bot")
        try:
            # Initialize bot
            self.application = Application.builder().token(self.bot_token).build()
            
            # Add command handlers
            self.application.add_handler(TelegramCommandHandler("start", self.command_handler.start))
            self.application.add_handler(TelegramCommandHandler("add_channel", self.command_handler.add_channel))
            self.application.add_handler(TelegramCommandHandler("list_channels", self.command_handler.list_channels))
            self.application.add_handler(TelegramCommandHandler("remove_channel", self.command_handler.remove_channel))
            self.application.add_handler(TelegramCommandHandler("help", self.command_handler.help))
            
            # Start the bot
            logger.info("Starting bot polling...")
            
            # Run the bot
            await self.application.run_polling(drop_pending_updates=True)
                
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}")
            if self.application:
                await self.application.stop()
        finally:
            logger.info("Bot stopped")

def main():
    """Main function to run the bot"""
    bot = TubeDigestBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}")

if __name__ == '__main__':
    main() 