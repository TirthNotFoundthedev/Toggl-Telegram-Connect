import os
import requests
import logging
from datetime import timedelta, datetime, timezone 
from dotenv import load_dotenv # Required for loading tokens from a .env file

from Toggl.general import format_duration, get_project_name
from Supabase.supabase_client import get_user_by_tele_id

# --- Telegram Bot Imports ---
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


TOGGL_CURRENT_ENTRY_URL = "https://api.track.toggl.com/api/v9/me/time_entries/current"

# Set up logging for the bot
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)


# ==============================================================================
# CORE TOGGL LOGIC
# ==============================================================================

def check_toggl_status(api_token: str):
    """Checks the Toggl Track API for a currently running time entry."""
    if not api_token:
        return {"error": "Toggl API token is missing."}

    try:
        response = requests.get(
            TOGGL_CURRENT_ENTRY_URL,
            auth=(api_token, 'api_token')
        )
        response.raise_for_status()

        if response.text and response.text != '{}':
            return response.json()
        else:
            return None
            
    except requests.exceptions.HTTPError as errh:
        if errh.response.status_code in [401, 403]:
             return {"error": "Authentication failed. Check if your Toggl API token is correct."}
        return {"error": f"HTTP Error: {errh}"}
    except requests.exceptions.RequestException as err:
        return {"error": f"Network Error: {err}"}


def generate_telegram_response(user_key: str, running_entry, api_token: str):
    """
    Formats the API response into a readable Markdown message for Telegram.
    Now includes the user_key for personalized messages and uses the requested emojis.
    """
    
    user_display_name = user_key.capitalize()

    if isinstance(running_entry, dict) and "error" in running_entry:
        return f"🚨 API Error for {user_display_name}: `{running_entry['error']}`"

    # Message if no timer is running
    if not running_entry:
        return f"🔴 *{user_display_name}* is currently *NOT* tracking time."
    
    start_time_str = running_entry.get('start')
    
    try:
        start_dt_utc = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        now_dt_utc = datetime.now(timezone.utc)
        time_diff = now_dt_utc - start_dt_utc
        duration_seconds = time_diff.total_seconds()
    except Exception as e:
        logging.error(f"Error calculating duration: {e}")
        return f"🚨 Error calculating duration from start time '{start_time_str}'. Details: {e}"

    formatted_time = format_duration(duration_seconds)
    description = running_entry.get('description', 'No description')
    
    project_id = running_entry.get('project_id')
    workspace_id = running_entry.get('workspace_id')
    
    # Default project line if no project ID is found
    project_info_line = "📂 *Project:* _No Project Assigned_" 

    if project_id and api_token and workspace_id:
        project_name = get_project_name(api_token, project_id, workspace_id)
        
        if not project_name.startswith("Error") and not project_name.startswith("Unknown"):
             # Format: 📂 *Project:* Chess
             project_info_line = f"📂 *Project:* {project_name}"
        elif project_name == "Inaccessible or Deleted Project":
             # Display the graceful message for 404/inaccessible projects
             project_info_line = f"📂 *Project:* `{project_name}` (ID: `{project_id}`)"
        else:
             # Display error/unknown with ID for debugging
             project_info_line = f"📂 *Project:* `{project_name}` (ID: `{project_id}`)"
    
    # Construct the final message using the requested format:
    # 🟢 Tirth is currently tracking time!
    # 📝 Task: 
    # ⏱ Duration: 0:05:11
    # 📂 Project: Chess
    response_message = (
        f"🟢 *{user_display_name}* is currently tracking time!\n" 
        f"📝 *Task:* {description}\n"                             
        f"⏱ *Duration:* `{formatted_time}`\n"                     
        f"{project_info_line}"                                    
    )
    
    return response_message

# ==============================================================================
# TELEGRAM BOT HANDLERS (UPDATED)
# ==============================================================================


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks the Toggl status for the specified user and sends the response back."""

    try:
    
        toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
        available_users = sorted(toggl_token_map.keys())

        if not toggl_token_map:
            await update.message.reply_text(
                "Configuration Error: No Toggl tokens are set up. Use the `/add_user` command to begin."
            )
            return

        if not context.args:
            # Build reply keyboard with only user display names and an 'All' button
            buttons = []
            row = []
            for idx, u in enumerate(available_users):
                # Show just the display name. We'll handle mapping taps to commands in a MessageHandler.
                row.append(KeyboardButton(u.capitalize()))
                # Limit row width to 3 buttons for readability
                if (idx + 1) % 3 == 0:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)

            # Add an 'All' button on its own row
            buttons.append([KeyboardButton("All")])

            # Add a Back button to return to the main menu
            buttons.append([KeyboardButton("Back")])

            kb = ReplyKeyboardMarkup(buttons, one_time_keyboard=False, resize_keyboard=True)
            await update.message.reply_text(
                "Select a user to check status:",
                reply_markup=kb
            )
            return
        
        user_key_input = context.args[0].lower()

        # Special-case: '/status all' -> show everyone's status except the invoking user
        if user_key_input == 'all':
            sender = update.effective_user
            sender_tele_id = None
            try:
                sender_tele_id = str(sender.id) if sender and sender.id else None
            except Exception:
                sender_tele_id = None

            # Try to resolve the invoking user's configured user_name (if any) from Supabase
            sender_user_name = None
            if sender_tele_id:
                try:
                    row = get_user_by_tele_id(sender_tele_id)
                    if row and row.get('user_name'):
                        sender_user_name = row.get('user_name')
                except Exception:
                    sender_user_name = None

            # Build combined responses for all users except the sender's configured user_name
            parts = []
            for user_key, token in sorted(toggl_token_map.items()):
                # Skip the invoking user if they have a configured user_name
                if sender_user_name and user_key.lower() == sender_user_name.lower():
                    continue

                try:
                    entry = check_toggl_status(token)
                    parts.append(generate_telegram_response(user_key, entry, token))
                except Exception as e:
                    parts.append(f"🚨 Error checking {user_key.capitalize()}: {e}")

            if not parts:
                await update.message.reply_text("No other configured users found to show status for.")
                return

            # Send as a single message separated by double newlines to keep it readable
            await update.message.reply_text("\n\n".join(parts), parse_mode='Markdown')
            return

        toggl_api_token = toggl_token_map.get(user_key_input)
        
        if not toggl_api_token:
            user_list = ", ".join([u.capitalize() for u in available_users])
            await update.message.reply_text(
                f"User key '*`{context.args[0]}`*' not found. Available users: *{user_list}*",
                parse_mode='Markdown'
            )
            return

        await update.message.reply_text(f"Checking Toggl status for *{user_key_input.capitalize()}* now...", parse_mode='Markdown')

        entry_data = check_toggl_status(toggl_api_token)
        # UPDATED: Pass the user key to generate_telegram_response
        response_text = generate_telegram_response(user_key_input, entry_data, toggl_api_token) 
        
        await update.message.reply_text(response_text, parse_mode='Markdown')


    except:
        await update.message.reply_text("Whoops, IDK what went wrong, but somethind did! Sorry 😔. Contact @TNF2008.")


async def status_name_tap_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles taps on the reply keyboard which show only names (or 'All').

    Maps the tapped text to the appropriate `/status <user>` or `/status all` invocation
    by reusing `status_command` logic via a synthetic args list.
    """
    text = (update.message.text or "").strip()
    if not text:
        return

    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    available_users = sorted(toggl_token_map.keys())
    # Track which menu was shown last for this user (may be set by other handlers)
    last_menu = None
    try:
        last_menu = context.user_data.get('last_menu')
    except Exception:
        last_menu = None

    # Handle Back/Menu to return to the general start menu
    if text.lower() in ('back', 'menu'):
        # Delegate to the main start_command which will show the general keyboard
        try:
            from Utilities.general import start_command
            context.args = []
            await start_command(update, context)
        except Exception:
            # Fall back to a simple message if something goes wrong
            await update.message.reply_text("Returning to main menu... (but the menu could not be displayed)")
        return

    # If user tapped 'All' (case-insensitive), delegate based on which menu was last shown
    if text.lower() == 'all':
        if last_menu == 'today':
            try:
                from Toggl.today import today_command
                context.args = ['all']
                await today_command(update, context)
                try:
                    context.user_data.pop('last_menu', None)
                except Exception:
                    pass
            except Exception:
                # fallback to status behavior
                context.args = ['all']
                await status_command(update, context)
            return
        else:
            # default to status behavior
            context.args = ['all']
            await status_command(update, context)
            return

    # Match tapped display name to a configured user key (case-insensitive)
    for user_key in available_users:
        if text.lower() == user_key.lower() or text.lower() == user_key.capitalize().lower():
            if last_menu == 'today':
                try:
                    from Toggl.today import today_command
                    context.args = [user_key]
                    await today_command(update, context)
                    try:
                        context.user_data.pop('last_menu', None)
                    except Exception:
                        pass
                except Exception:
                    # fallback
                    context.args = [user_key]
                    await status_command(update, context)
                return
            else:
                context.args = [user_key]
                await status_command(update, context)
                return

    # If no match, ignore (or optionally inform the user)
    await update.message.reply_text("Selected name not recognized. Try /status <name> or /status all.")


    