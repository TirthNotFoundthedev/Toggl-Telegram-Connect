from typing import List
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ContextTypes


def _build_user_keyboard(user_keys: List[str], include_all: bool = True, include_back: bool = True):
    buttons = []
    row = []
    for idx, u in enumerate(user_keys):
        row.append(KeyboardButton(u.capitalize()))
        if (idx + 1) % 3 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    if include_all:
        buttons.append([KeyboardButton('All')])
    if include_back:
        buttons.append([KeyboardButton('Back')])

    return ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)


async def show_status_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    user_keys = sorted(toggl_token_map.keys())
    kb = _build_user_keyboard(user_keys)
    try:
        context.user_data['last_menu'] = 'status'
    except Exception:
        pass
    await update.message.reply_text('Select a user to check status:', reply_markup=kb)


async def show_today_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    user_keys = sorted(toggl_token_map.keys())
    kb = _build_user_keyboard(user_keys)
    try:
        context.user_data['last_menu'] = 'today'
    except Exception:
        pass
    await update.message.reply_text("Select a user to view today's totals:", reply_markup=kb)


async def show_wake_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Use the list of configured users from bot_data (keeps UI consistent)
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    user_keys = sorted(toggl_token_map.keys())
    kb = _build_user_keyboard(user_keys)
    try:
        context.user_data['last_menu'] = 'wake'
    except Exception:
        pass
    # send via effective_message if available
    if update.effective_message:
        await update.effective_message.reply_text('Who would you like to wake?', reply_markup=kb)
    else:
        await update.message.reply_text('Who would you like to wake?', reply_markup=kb)


async def show_start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # The start menu labels are simple static choices
    reply_keyboard = [
        [KeyboardButton('Status'), KeyboardButton('Today')],
        [KeyboardButton('Wake'), KeyboardButton('Leaderboard')],
        [KeyboardButton("Focus-Noise-Ratio")]
        [KeyboardButton('Users'), KeyboardButton('Add user')]
    ]
    kb = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    # mark the last menu as 'home' so taps know the user is on the start/home menu
    try:
        context.user_data['last_menu'] = 'home'
    except Exception:
        pass
    await update.message.reply_text(
        'Welcome! Use the buttons below or the commands shown for advanced options.\n\nUse "Wake" to send a wake-up message to a user or everyone.',
        reply_markup=kb,
    )


async def show_leaderboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_keyboard = [
        [KeyboardButton('Daily'), KeyboardButton('Weekly')],
        [KeyboardButton('Back')]
    ]
    try:
        context.user_data['last_menu'] = 'leaderboard'
    except Exception:
        pass
    kb = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.effective_message.reply_text('Choose leaderboard period:', reply_markup=kb)


async def button_tap_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Central router for plain-text keyboard taps.

    Routes taps based on context.user_data['last_menu'] or on start-menu labels.
    """
    text = (update.message.text or '').strip()
    if not text:
        return

    last_menu = None
    try:
        last_menu = context.user_data.get('last_menu')
    except Exception:
        last_menu = None

    # Back/Menu always returns to start menu
    if text.lower() in ('back', 'menu'):
        await show_start_menu(update, context)
        return

    # If last_menu is set, route accordingly
    if last_menu == 'status':
        # delegate to Toggl.status.status_command
        try:
            from Toggl.status import status_command
            if text.lower() == 'all':
                context.args = ['all']
            else:
                context.args = [text.lower()]
            await status_command(update, context)
        except Exception:
            await update.message.reply_text('Could not handle status selection.')
        return

    if last_menu == 'today':
        try:
            from Toggl.today import today_command
            if text.lower() == 'all':
                context.args = ['all']
            else:
                context.args = [text.lower()]
            await today_command(update, context)
        except Exception:
            await update.message.reply_text('Could not handle today selection.')
        finally:
            try:
                context.user_data.pop('last_menu', None)
            except Exception:
                pass
        return

    if last_menu == 'wake':
        try:
            from Toggl.wake import wake
            if text.lower() == 'all':
                context.args = ['all']
            else:
                context.args = [text.lower()]
            await wake(update, context)
        except Exception:
            await update.message.reply_text('Could not handle wake selection.')
        finally:
            try:
                context.user_data.pop('last_menu', None)
            except Exception:
                pass
        return

    if last_menu == 'leaderboard':
        try:
            from Toggl.leaderboard import leaderboard_command
            if text.lower() in ('daily', 'day'):
                context.args = ['daily']
            elif text.lower() in ('weekly', 'week'):
                context.args = ['weekly']
            else:
                context.args = []
            await leaderboard_command(update, context)
        except Exception:
            await update.message.reply_text('Could not handle leaderboard selection.')
        finally:
            try:
                context.user_data.pop('last_menu', None)
            except Exception:
                pass
        return

    # No last_menu: treat as start menu labels
    if text.lower() == 'status':
        await show_status_menu(update, context)
        return
    if text.lower() == 'today':
        await show_today_menu(update, context)
        return
    if text.lower() == 'wake':
        await show_wake_menu(update, context)
        return
    if text.lower() == 'leaderboard' or text.lower() == 'lb':
        await show_leaderboard_menu(update, context)
        return
    if text.lower() == 'add user':
        try:
            from Utilities.users import add_user_command
            context.args = []
            await add_user_command(update, context)
        except Exception:
            await update.message.reply_text('Could not open add-user flow.')
        return
    if text.lower() == 'users':
        try:
            from Utilities.users import users_command
            context.args = []
            await users_command(update, context)
        except Exception:
            await update.message.reply_text('Could not list users.')
        return

    # Unrecognized tap
    await update.message.reply_text('Selection not recognized. Use the menu buttons or commands.')
