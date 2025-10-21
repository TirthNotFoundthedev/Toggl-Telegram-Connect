from telegram import Update
from telegram.ext import ContextTypes
from Supabase.supabase_client import get_all_users_with_tele_id, get_wake_cooldown, set_wake_cooldown
from Utilities.command_logging import log_command_usage
import html

# Admin identity - allow Tirth (by username). You can expand to include numeric IDs.
ADMINS_USERNAMES = {"tirth", "Tirth"}


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    if not user:
        return False
    # Check username
    if user.username and user.username in ADMINS_USERNAMES:
        return True
    # Allow match by full name as fallback
    if (user.full_name or "").split()[0] in ADMINS_USERNAMES:
        return True
    return False


@log_command_usage('wake_cooldowns')
async def view_wake_cooldowns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: show persisted wake cooldowns for all configured users."""
    if not _is_admin(update):
        await update.effective_message.reply_text("You are not authorized to run this command.")
        return

    users = get_all_users_with_tele_id() or []
    if not users:
        await update.effective_message.reply_text("No configured users found.")
        return

    lines = []
    for row in users:
        tele = row.get("tele_id")
        name = row.get("user_name") or "(unknown)"
        wc = get_wake_cooldown(str(tele)) or {}
        # Format a summary per user
        if not wc:
            lines.append(f"{html.escape(name)} ({tele}): <i>no cooldowns</i>")
        else:
            inner = []
            for sender_id, iso in wc.items():
                inner.append(f"from {html.escape(str(sender_id))}: {html.escape(str(iso))}")
            lines.append(f"{html.escape(name)} ({tele}): " + "; ".join(inner))

    text = "\n".join(lines)
    await update.effective_message.reply_text(text, parse_mode="HTML")


@log_command_usage('wake_cooldown_reset')
async def reset_wake_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command: reset wake cooldown for a specific tele_id or all users.

    Usage:
      /wake_cooldown_reset <tele_id>    - resets for that tele_id
      /wake_cooldown_reset all           - resets for all configured users
    """
    if not _is_admin(update):
        await update.effective_message.reply_text("You are not authorized to run this command.")
        return

    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /wake_cooldown_reset <tele_id|all>")
        return

    target = args[0].strip().lower()
    users = get_all_users_with_tele_id() or []

    if target == 'all':
        count = 0
        for row in users:
            tele = row.get('tele_id')
            if not tele:
                continue
            set_wake_cooldown(str(tele), {})
            # Update in-memory cache if present
            try:
                context.application.bot_data.setdefault('wake_map', {})[str(tele)] = {}
            except Exception:
                pass
            count += 1
        await update.effective_message.reply_text(f"Reset wake_cooldown for {count} users.")
        return

    # reset a specific tele_id
    try:
        set_wake_cooldown(str(target), {})
        try:
            context.application.bot_data.setdefault('wake_map', {})[str(target)] = {}
        except Exception:
            pass
        await update.effective_message.reply_text(f"Reset wake_cooldown for {target}.")
    except Exception as e:
        await update.effective_message.reply_text(f"Failed to reset wake_cooldown for {target}: {e}")
