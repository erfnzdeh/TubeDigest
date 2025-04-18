import logging
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from src.models.user import User
from src.models.channel import Channel
from src.services.youtube_service import YouTubeService

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, db: Session, youtube_service: YouTubeService):
        self.db = db
        self.youtube_service = youtube_service

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started the bot")
        
        db_user = self.db.query(User).filter(User.telegram_id == user.id).first()
        
        if not db_user:
            logger.info(f"Creating new user record for {user.id}")
            db_user = User(telegram_id=user.id, username=user.username)
            self.db.add(db_user)
            self.db.commit()
        
        welcome_message = (
            f"👋 Hello {user.first_name}!\n\n"
            "I'm TubeDigest, your YouTube summary bot. I can help you monitor YouTube channels "
            "and send you summaries of new videos.\n\n"
            "Available commands:\n"
            "/add_channel <channel_id> - Add a YouTube channel to monitor\n"
            "/list_channels - List your monitored channels\n"
            "/remove_channel <channel_id> - Remove a channel from monitoring\n"
            "/help - Show this help message"
        )
        
        await update.message.reply_text(welcome_message)
        logger.info(f"Sent welcome message to user {user.id}")

    async def add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /add_channel command."""
        user = update.effective_user
        channel_id = context.args[0] if context.args else None
        logger.info(f"User {user.id} attempted to add channel {channel_id}")
        
        if not channel_id:
            await update.message.reply_text("Please provide a YouTube channel ID. Usage: /add_channel <channel_id>")
            logger.warning(f"User {user.id} tried to add channel without providing channel ID")
            return
        
        try:
            # Verify channel exists
            channel_info = self.youtube_service.get_channel_info(channel_id)
            if not channel_info:
                await update.message.reply_text("Channel not found. Please check the channel ID.")
                logger.warning(f"User {user.id} tried to add non-existent channel {channel_id}")
                return
        except Exception as e:
            logger.error(f"Error verifying channel: {str(e)}")
            await update.message.reply_text(f"Error verifying channel: {str(e)}")
            return
        
        # Check if channel is already monitored
        existing_channel = self.db.query(Channel).filter(
            Channel.youtube_id == channel_id,
            Channel.user_id == user.id
        ).first()
        
        if existing_channel:
            await update.message.reply_text("You're already monitoring this channel.")
            logger.info(f"User {user.id} tried to add already monitored channel {channel_id}")
            return
        
        # Add channel to database
        channel = Channel(
            youtube_id=channel_id,
            title=channel_info['title'],
            user_id=user.id
        )
        self.db.add(channel)
        self.db.commit()
        
        await update.message.reply_text(f"Added channel: {channel_info['title']}")
        logger.info(f"User {user.id} successfully added channel {channel_id} ({channel_info['title']})")

    async def list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /list_channels command."""
        user = update.effective_user
        logger.info(f"User {user.id} requested list of monitored channels")
        
        channels = self.db.query(Channel).filter(Channel.user_id == user.id).all()
        
        if not channels:
            await update.message.reply_text("You're not monitoring any channels yet.")
            logger.info(f"User {user.id} has no monitored channels")
            return
        
        message = "Your monitored channels:\n\n"
        for channel in channels:
            message += f"• {channel.title} (ID: {channel.youtube_id})\n"
        
        await update.message.reply_text(message)
        logger.info(f"Sent list of {len(channels)} channels to user {user.id}")

    async def remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /remove_channel command."""
        user = update.effective_user
        channel_id = context.args[0] if context.args else None
        logger.info(f"User {user.id} attempted to remove channel {channel_id}")
        
        if not channel_id:
            await update.message.reply_text("Please provide a YouTube channel ID. Usage: /remove_channel <channel_id>")
            logger.warning(f"User {user.id} tried to remove channel without providing channel ID")
            return
        
        channel = self.db.query(Channel).filter(
            Channel.youtube_id == channel_id,
            Channel.user_id == user.id
        ).first()
        
        if not channel:
            await update.message.reply_text("Channel not found in your monitored list.")
            logger.warning(f"User {user.id} tried to remove non-monitored channel {channel_id}")
            return
        
        self.db.delete(channel)
        self.db.commit()
        
        await update.message.reply_text(f"Removed channel: {channel.title}")
        logger.info(f"User {user.id} successfully removed channel {channel_id} ({channel.title})")

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command."""
        user = update.effective_user
        logger.info(f"User {user.id} requested help")
        
        help_message = (
            "🤖 TubeDigest Bot Help\n\n"
            "I can help you monitor YouTube channels and send you summaries of new videos.\n\n"
            "Commands:\n"
            "/start - Start the bot\n"
            "/add_channel <channel_id> - Add a YouTube channel to monitor\n"
            "/list_channels - List your monitored channels\n"
            "/remove_channel <channel_id> - Remove a channel from monitoring\n"
            "/help - Show this help message\n\n"
            "To get a YouTube channel ID:\n"
            "1. Go to the channel's page\n"
            "2. The channel ID is in the URL: youtube.com/channel/CHANNEL_ID\n"
            "   or youtube.com/c/CHANNEL_NAME"
        )
        
        await update.message.reply_text(help_message)
        logger.info(f"Sent help message to user {user.id}") 