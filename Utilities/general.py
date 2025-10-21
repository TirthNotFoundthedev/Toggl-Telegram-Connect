
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes


async def start_button_tap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Map plain-text start keyboard taps to command handlers.

    Recognized labels: 'Status', 'Today', 'Add user', 'Users'
    This sets `context.args` appropriately and delegates to existing handlers.
    """
    text = (update.message.text or "").strip()
    if not text:
        return

    # Map taps to behavior
    if text.lower() == 'status':
        # Show the status selection keyboard by calling status_command with no args
        context.args = []
        from Toggl.status import status_command
        await status_command(update, context)
        return

    if text.lower() == 'today':
        # Call today_command with no args so it will show usage / prompt
        context.args = []
        from Toggl.today import today_command
        await today_command(update, context)
        return

    if text.lower() == 'add user':
        # Forward to add_user_command (will prompt usage)
        context.args = []
        from Utilities.users import add_user_command
        await add_user_command(update, context)
        return

    if text.lower() == 'users':
        context.args = []
        from Utilities.users import users_command
        await users_command(update, context)
        return

    # Unknown tap -> ignore silently
    return


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
