
from telegram import Update
from telegram.ext import ContextTypes


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    available_users = ", ".join(sorted([u.capitalize() for u in toggl_token_map.keys()]))
    
    await update.message.reply_text(
        'Welcome! I am the Toggl Status Bot. Here are the available commands:\n\n'
        '1. `/add_user <name> <token>`: Add a user\'s token (for yourself or others).\n'
        '2. `/status <name>`: Check the live Toggl timer for a configured user.\n'
        '3. `/users`: List all currently configured user names.\n\n'
        '4. `/today`: Shows Today\'s (or any day\'s) report. Use: /today <name> <date (optional)',
        parse_mode='Markdown'
    )
