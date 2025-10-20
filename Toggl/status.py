import os
import requests
import logging
from datetime import timedelta, datetime, timezone 
from dotenv import load_dotenv # Required for loading tokens from a .env file

from Toggl.general import format_duration, get_project_name

# --- Telegram Bot Imports ---
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


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
            user_list = ", ".join([u.capitalize() for u in available_users])
            await update.message.reply_text(
                f"Please specify a user key. Example: `/status {available_users[0].capitalize() if available_users else 'Name'}`\n"
                f"Available users: *{user_list}*",
                parse_mode='Markdown'
            )
            return
        
        user_key_input = context.args[0].lower()
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


    