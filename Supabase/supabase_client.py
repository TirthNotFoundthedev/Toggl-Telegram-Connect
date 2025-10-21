import os
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Supabase configuration (loaded from environment variables in main.py)
# NOTE: This file assumes the environment variables are loaded in main.py BEFORE this file is used.
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE_NAME = "Users"  # Assuming your table is named 'Users'

# Initialize Supabase client globally
supabase: Client = None

def init_supabase() -> bool:
    """Initializes the Supabase client."""
    global supabase
    # Fetch environment variables again to ensure we get the values loaded by dotenv in main.py.
    local_url = os.getenv("SUPABASE_URL")
    local_key = os.getenv("SUPABASE_KEY")
    
    if not local_url or not local_key:
        logger.error("Supabase credentials (SUPABASE_URL and SUPABASE_KEY) are not set.")
        return False
    
    try:
        supabase = create_client(local_url, local_key)
        logger.info(f"Supabase client initialized for table '{TABLE_NAME}'.")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return False

def load_tokens_from_db() -> dict:
    """Loads all user tokens from the Supabase Users table.
    
    Uses the table columns: 'user_name' and 'toggl_token'.
    """
    if not supabase:
        logger.error("Supabase client not initialized.")
        return {}

    try:
        # Fetching 'user_name' (for lookup) and 'toggl_token' (the value)
        response = supabase.table(TABLE_NAME).select("user_name, toggl_token").execute()
        
        # Structure data into the required dictionary format: {'user_name': 'toggl_token'}
        token_map = {
            record['user_name']: record['toggl_token'] 
            for record in response.data
        }
        logger.info(f"Successfully loaded {len(token_map)} tokens from Supabase.")
        return token_map
    except Exception as e:
        logger.error(f"Error loading tokens from Supabase: {e}. Check that the 'user_name' column exists.")
        return {}


def save_token_to_db(user_name: str, toggl_token: str, tele_id=None):
    """Inserts a new user's token into the Supabase Users table only if the user_name does not exist.

    tele_id is required (cannot be None). Additionally, tele_id must be unique across rows
    (one Telegram account -> one user). The function returns a tuple: (success: bool, message: str).
    """
    if not supabase:
        logger.error("Supabase client not initialized.")
        return (False, "Supabase client not initialized")

    if tele_id is None:
        logger.error("tele_id is required and cannot be None when saving a token.")
        return (False, "tele_id is required")

    try:
        # 1. Check if the user_name already exists (to prevent duplicates)
        count_response = supabase.table(TABLE_NAME).select(
            "user_name",
            count="exact"
        ).eq('user_name', user_name).execute()

        if getattr(count_response, 'count', 0) > 0:
            logger.error(f"User '{user_name}' already exists. Cannot add duplicate name.")
            return (False, "user_name already exists")

        # 2. Check that the provided telegram id is not already associated with another user
        tele_check = supabase.table(TABLE_NAME).select("tele_id", count="exact").eq('tele_id', str(tele_id)).execute()
        if getattr(tele_check, 'count', 0) > 0:
            logger.error(f"Telegram ID '{tele_id}' is already associated with another user.")
            return (False, "tele_id already in use")

        # 2. If no conflict, perform the insert
        data_to_save = {
            'user_name': user_name,
            'toggl_token': toggl_token,
            'tele_id': str(tele_id)
        }

        response = supabase.table(TABLE_NAME).insert(
            data_to_save
        ).execute()

        logger.info(f"New token saved for user: {user_name}. Response data: {response.data}")
        return (True, "inserted")
    except Exception as e:
        # This catch-all handles network errors or unexpected DB issues during insert
        logger.error(f"Error saving token for {user_name} to Supabase: {e}")
        return (False, str(e))


def get_user_by_name(user_name: str):
    """Fetch a user row by user_name from the Users table.

    Returns the row dict (may include 'tele_id', 'toggl_token', etc.) or None if not found.
    """
    if not supabase:
        logger.error("Supabase client not initialized.")
        return None

    try:
        response = supabase.table(TABLE_NAME).select("user_name, tele_id, toggl_token").eq('user_name', user_name).limit(1).execute()
        if getattr(response, 'data', None):
            if len(response.data) > 0:
                return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error querying user by name '{user_name}': {e}")
        return None


def get_tele_id_for_user(user_name: str):
    """Convenience: return the tele_id (string) for a given user_name, or None if not found."""
    row = get_user_by_name(user_name)
    if not row:
        return None
    return row.get('tele_id')


def get_user_by_tele_id(tele_id: str):
    """Fetch a user row by tele_id from the Users table.

    Returns the row dict (may include 'user_name', 'toggl_token') or None if not found.
    """
    if not supabase:
        logger.error("Supabase client not initialized.")
        return None

    try:
        response = supabase.table(TABLE_NAME).select("user_name, tele_id, toggl_token").eq('tele_id', str(tele_id)).limit(1).execute()
        if getattr(response, 'data', None):
            if len(response.data) > 0:
                return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error querying user by tele_id '{tele_id}': {e}")
        return None


def get_wake_cooldown(tele_id: str):
    """Return the wake_cooldown JSON stored for the user with given tele_id.

    Returns a dict (may be empty) or None if user/DB not found.
    """
    if not supabase:
        logger.error("Supabase client not initialized.")
        return None

    try:
        response = supabase.table(TABLE_NAME).select("wake_cooldown").eq('tele_id', str(tele_id)).limit(1).execute()
        if getattr(response, 'data', None) and len(response.data) > 0:
            row = response.data[0]
            wc = row.get('wake_cooldown')
            # Ensure we return a dict
            if wc is None:
                return {}
            return wc
        return None
    except Exception as e:
        logger.error(f"Error fetching wake_cooldown for tele_id '{tele_id}': {e}")
        return None


def set_wake_cooldown(tele_id: str, wake_cooldown: dict) -> bool:
    """Update the wake_cooldown JSONB column for the given tele_id.

    Returns True on success, False otherwise.
    """
    if not supabase:
        logger.error("Supabase client not initialized.")
        return False

    try:
        response = supabase.table(TABLE_NAME).update({
            'wake_cooldown': wake_cooldown
        }).eq('tele_id', str(tele_id)).execute()
        # response.error may exist depending on client; assume success if no exception
        return True
    except Exception as e:
        logger.error(f"Error updating wake_cooldown for tele_id '{tele_id}': {e}")
        return False


def get_all_users_with_tele_id():
    """Return a list of all user rows that have a tele_id configured.

    Each returned row is a dict and should include at least the keys:
      - 'user_name'
      - 'tele_id'
      - 'toggl_token'

    This is used by other code (e.g., `Toggl.wake`) which expects to iterate
    the returned rows and call `row.get('tele_id')` and `row.get('toggl_token')`.
    """
    if not supabase:
        logger.error("Supabase client not initialized.")
        return []

    try:
        # Select rows where tele_id is not null/empty
        response = supabase.table(TABLE_NAME).select("user_name, tele_id, toggl_token").neq('tele_id', None).execute()
        if getattr(response, 'data', None):
            # Filter out rows with empty tele_id values just in case
            rows = [r for r in response.data if r.get('tele_id')]
            return rows
        return []
    except Exception as e:
        logger.error(f"Error fetching users with tele_id: {e}")
        return []


def log_command(user_name: str, command: str, response_success: bool) -> bool:
    """Insert a row into the `Command Logs` table recording a command usage.

    user_name may be None or a string. Returns True on success.
    """
    if not supabase:
        logger.error("Supabase client not initialized. Cannot log command.")
        return False

    try:
        data = {
            'user_name': user_name,
            'command': command,
            'response_success': bool(response_success),
        }
        # Insert into table named exactly 'Command Logs'
        supabase.table('Command Logs').insert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to log command to Supabase: {e}")
        return False
