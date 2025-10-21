
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from Utilities.command_logging import log_command_usage


@log_command_usage('start')
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    available_users = ", ".join(sorted([u.capitalize() for u in toggl_token_map.keys()]))

    reply_keyboard = [
        [KeyboardButton("Status"), KeyboardButton("Today")],
        [KeyboardButton("Add user")],
        [KeyboardButton("Users")]
    ]

    markup = ReplyKeyboardMarkup(
        reply_keyboard,
        resize_keyboard=True,  
        one_time_keyboard=False 
    )
    
    message = (
        'Welcome! I am the Toggl Status Bot. Use the buttons below to get started, or run the commands shown for advanced options.\n\n'
        '1. `/add_user <name> <token>`: Add a user\'s token.\n'
        '2. `/status <name>`: Check the live Toggl timer.\n'
        '3. `/users`: List all configured user names.\n'
        '4. `/today <name> <date (optional)>`: Shows Today\'s (or any day\'s) report.'
    )

    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        reply_markup=markup,
    )
