import os
import logging
from dotenv import load_dotenv 
from telegram.ext import Application, CommandHandler
# FIX: Import Update class for use with application.run_polling
from telegram import Update 

from Utilities.general import start_command
from Utilities.users import add_user_command, users_command
from Toggl.status import status_command
from Toggl.today import today_command
from Toggl.wake import wake
from Supabase.supabase_client import init_supabase, load_tokens_from_db

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)




def main() -> None:
    """Start the bot."""
    
    # 1. Load environment variables
    load_dotenv()
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set. Exiting.")
        return

    # 2. Initialize Supabase Client
    if not init_supabase():
        logger.error("Supabase client initialization failed. Bot cannot save or load tokens from DB.")
        # We allow the bot to run, but /add_user and /status based on DB will fail
        # You should fix your SUPABASE_URL/SUPABASE_KEY in .env
    
    # Build the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Initialize the token map in the bot's persistent data store
    toggl_token_map = {}
    
    # 3. Load tokens from Supabase (This needs init_supabase to have run successfully)
    db_tokens = load_tokens_from_db() 
    toggl_token_map.update(db_tokens)

    # Store the map where all handlers can access it
    application.bot_data['toggl_token_map'] = toggl_token_map
    logger.info(f"Bot initialized with {len(toggl_token_map)} users from Supabase.")

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("add_user", add_user_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("wake", wake))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
