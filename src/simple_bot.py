import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    logger.info(f"User {user.id} started the bot")
    
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    user = update.effective_user
    logger.info(f"User {user.id} requested help")
    
    help_text = (
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
    
    await update.message.reply_text(help_text)
    logger.info(f"Sent help message to user {user.id}")

async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a YouTube channel to monitor."""
    user = update.effective_user
    channel_id = context.args[0] if context.args else None
    logger.info(f"User {user.id} attempted to add channel {channel_id}")
    
    if not channel_id:
        await update.message.reply_text("Please provide a YouTube channel ID. Usage: /add_channel <channel_id>")
        logger.warning(f"User {user.id} tried to add channel without providing channel ID")
        return
    
    # For now, just acknowledge the command
    await update.message.reply_text(f"Channel {channel_id} will be added to monitoring (not implemented yet)")
    logger.info(f"Acknowledged add channel request for user {user.id}")

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List monitored channels."""
    user = update.effective_user
    logger.info(f"User {user.id} requested list of monitored channels")
    
    # For now, just return a placeholder message
    await update.message.reply_text("You're not monitoring any channels yet. Use /add_channel to add one!")
    logger.info(f"Sent placeholder message for list_channels to user {user.id}")

async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a YouTube channel from monitoring."""
    user = update.effective_user
    channel_id = context.args[0] if context.args else None
    logger.info(f"User {user.id} attempted to remove channel {channel_id}")
    
    if not channel_id:
        await update.message.reply_text("Please provide a YouTube channel ID. Usage: /remove_channel <channel_id>")
        logger.warning(f"User {user.id} tried to remove channel without providing channel ID")
        return
    
    # For now, just acknowledge the command
    await update.message.reply_text(f"Channel {channel_id} will be removed from monitoring (not implemented yet)")
    logger.info(f"Acknowledged remove channel request for user {user.id}")

def main():
    """Start the bot."""
    # Create the Application and pass it your bot's token
    application = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_channel", add_channel))
    application.add_handler(CommandHandler("list_channels", list_channels))
    application.add_handler(CommandHandler("remove_channel", remove_channel))

    # Start the Bot
    logger.info("Starting bot...")
    application.run_polling(drop_pending_updates=True)
    logger.info("Bot stopped")

if __name__ == '__main__':
    main() 