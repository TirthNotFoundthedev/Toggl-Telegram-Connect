
from telegram import Update
from telegram.ext import ContextTypes
from Utilities.command_logging import log_command_usage


@log_command_usage('start')
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    
    message = (
        'Welcome! I am the Toggl Status Bot. Here are the available commands:\n\n'
        '1. `/add_user <name> <token>`: Add a user\'s token.\n'
        '2. `/status <name>`: Check the live Toggl timer.\n'
        '3. `/users`: List all configured user names.\n'
        '4. `/today <name> <date (optional)>`: Shows Today\'s (or any day\'s) report.'
    )

    await update.message.reply_text(
        message,
        parse_mode='Markdown',
    )
