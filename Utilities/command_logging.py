from functools import wraps
from typing import Callable
from telegram import Update
from telegram.ext import ContextTypes
from Supabase.supabase_client import log_command, get_user_by_tele_id
import logging

logger = logging.getLogger(__name__)


def log_command_usage(command_name: str):
    """Decorator for async command handlers to log usage to Supabase.

    It will call log_command(user_name, command_name, success_bool) after the
    handler completes (or when it raises), attempting best-effort to resolve
    a configured user_name from the invoking Telegram id.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_name = None
            try:
                # Try to resolve a mapped user_name for the invoking tele id
                try:
                    tele_id = None
                    if update and update.effective_user and update.effective_user.id:
                        tele_id = str(update.effective_user.id)
                    if tele_id:
                        row = get_user_by_tele_id(tele_id)
                        if row and row.get('user_name'):
                            user_name = row.get('user_name')
                except Exception:
                    user_name = None

                # Construct full command string to log. Prefer context.user_data['last_menu'] when present
                try:
                    last_menu = None
                    if context:
                        last_menu = getattr(context, 'user_data', {}).get('last_menu') if getattr(context, 'user_data', None) is not None else None
                except Exception:
                    last_menu = None

                # Base name to use (prefer last_menu so button taps are recorded as e.g. /status all)
                base_cmd = last_menu or command_name
                full_cmd = f"/{base_cmd}"
                try:
                    if context and getattr(context, 'args', None):
                        if isinstance(context.args, (list, tuple)) and len(context.args) > 0:
                            full_cmd = full_cmd + ' ' + ' '.join([str(a) for a in context.args])
                    else:
                        # fallback to message text if args not present
                        if update and update.effective_message and getattr(update.effective_message, 'text', None):
                            text = update.effective_message.text.strip()
                            if text.startswith('/'):
                                # use first token (command + args)
                                full_cmd = text.split('\n', 1)[0]
                except Exception:
                    pass

                # Execute the original handler
                result = await func(update, context, *args, **kwargs)

                # Success - log it with the full command text
                try:
                    log_command(user_name, full_cmd, True)
                except Exception:
                    logger.exception('Failed to log command success')

                return result
            except Exception as e:
                # Handler raised - log failure
                try:
                    log_command(user_name, command_name, False)
                except Exception:
                    logger.exception('Failed to log command failure')
                # Re-raise so normal error handling can continue (or swallow?)
                raise

        return wrapper
    return decorator
