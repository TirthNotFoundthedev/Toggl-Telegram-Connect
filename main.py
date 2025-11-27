import os
import logging
from dotenv import load_dotenv 
from telegram.ext import Application, CommandHandler
# FIX: Import Update class for use with application.run_polling
from telegram import Update 
from telegram.ext import MessageHandler, filters

from Utilities.general import start_command
from Utilities.users import add_user_command, users_command
from Toggl.status import status_command
from Toggl.today import today_command
from Toggl.wake import wake
from Toggl.leaderboard import leaderboard_command
from Supabase.supabase_client import init_supabase, load_tokens_from_db
from Supabase.supabase_client import get_all_users_with_tele_id, get_wake_cooldown
from Utilities.admin import view_wake_cooldowns, reset_wake_cooldown
from Toggl.fnr import fnr_command

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
    application.bot_data['wake_message_lookup'] = {} # Maps message_id to wake data
    application.bot_data['user_active_wake'] = {} # Maps target_user_id to the message_id of their active wake
    logger.info(f"Bot initialized with {len(toggl_token_map)} users from Supabase.")

    # Preload wake cooldowns for configured users (small userbase; safe to preload)
    try:
        wake_map = application.bot_data.setdefault('wake_map', {})
        users_with_tele = get_all_users_with_tele_id() or []
        for row in users_with_tele:
            tele = row.get('tele_id')
            if not tele:
                continue
            wc = get_wake_cooldown(str(tele)) or {}
            wake_map[str(tele)] = wc
        logger.info(f"Preloaded wake_cooldown for {len(wake_map)} users.")
    except Exception:
        logger.exception("Failed to preload wake_cooldown values from Supabase")

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    # Register command handlers
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("today", today_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("lb", leaderboard_command))
    application.add_handler(CommandHandler("add_user", add_user_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("wake", wake))
    application.add_handler(CommandHandler("fnr", fnr_command))
    # Admin commands
    application.add_handler(CommandHandler("wake_cooldowns", view_wake_cooldowns))
    application.add_handler(CommandHandler("wake_cooldown_reset", reset_wake_cooldown))

    # Handler for replies to wake messages
    from Utilities.reply_handler import handle_wake_reply
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wake_reply), group=0)

    # Run the bot until the user presses Ctrl-C
    # Check for Webhook configuration
    webhook_url = os.getenv("WEBHOOK_URL")
    
    if webhook_url:
        port = int(os.getenv("PORT", 8000))
        secret_token = os.getenv("WEBHOOK_SECRET")
        logger.info(f"Starting bot in WEBHOOK mode. Listening on port {port}...")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="telegram-webhook",
            webhook_url=f"{webhook_url}/telegram-webhook",
            secret_token=secret_token
        )
    else:
        logger.info("WEBHOOK_URL not found. Starting bot in POLLING mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
