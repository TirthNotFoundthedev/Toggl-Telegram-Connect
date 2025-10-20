import logging
import re
from telegram import Update
from telegram.ext import ContextTypes

# --- CRITICAL CHANGE: Import Supabase functions from the correct local file ---
from Supabase.supabase_client import save_token_to_db 
# Note: load_tokens_from_db is now only called in main.py during startup

logger = logging.getLogger(__name__)

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Implements /add_user <name> <token>. Adds a token for any user, persisting to Supabase.
    """
    # Check if we have two arguments: name and token
    if not context.args or len(context.args) != 2:
        await update.message.reply_text(
            "Usage: `/add_user <name> <token>`\n\n"
            "Example: `/add_user Alice 1234567890abcdef`\n"
            "The name must be a single word without spaces.",
            parse_mode='Markdown'
        )
        return
        
    user_key = context.args[0].lower() # The name for the new user (e.g., 'alice')
    toggl_api_token = context.args[1]
    
    # Validation
    if ' ' in user_key or not re.match(r'^[a-z0-9_]+$', user_key):
        await update.message.reply_text(
            "🚨 Error: The user name must be a single word, containing only letters, numbers, or underscores.",
            parse_mode='Markdown'
        )
        return

    # Get Telegram user id of the command sender and require it (cannot be None)
    try:
        telegram_id = update.effective_user.id
    except Exception:
        telegram_id = None

    if telegram_id is None:
        await update.message.reply_text(
            "❌ Error: Your Telegram ID could not be determined. This command requires a valid Telegram account id to be linked.",
            parse_mode='Markdown'
        )
        return

    # 1. Persist the change to Supabase (tele_id is mandatory)
    success, msg = save_token_to_db(user_key, toggl_api_token, tele_id=telegram_id)
    if success:
        
        # 2. Update the in-memory map stored in bot_data
        # This ensures the new token is immediately available for /status checks
        toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
        toggl_token_map[user_key] = toggl_api_token
        
        await update.message.reply_text(
            f"✅ Success! Token for *`{user_key.capitalize()}`* has been added to Database.\n"
            f"You can now check your status with: `/status {user_key}`",
            parse_mode='Markdown'
        )
    else:
        # Provide a helpful error message to the command user
        if msg == 'user_name already exists':
            await update.message.reply_text(
                "❌ Error: A user with that name already exists. Choose a different name.",
                parse_mode='Markdown'
            )
        elif msg == 'tele_id already in use':
            await update.message.reply_text(
                "❌ Error: This Telegram account is already linked to another user. Each Telegram ID may only be linked to one user.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ Error: Could not save token to Supabase. ({msg})",
                parse_mode='Markdown'
            )
        


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all currently configured user keys from the in-memory map."""
    # We rely on the map being updated after successful /add_user or on startup.
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    available_users = sorted(toggl_token_map.keys())

    if not available_users:
        await update.message.reply_text(
            "No users are currently configured. Use `/add_user <name> <token>` to add one.",
            parse_mode='Markdown'
        )
    else:
        user_list_text = "\n".join([f"- {u.capitalize()}" for u in available_users])
        await update.message.reply_text(
            f"👥 *Configured Users: ({len(available_users)})*\n\n{user_list_text}",
            parse_mode='Markdown'
        )
