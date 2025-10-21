from typing import Optional
import html
from telegram import Update, Chat, User
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from Utilities.command_logging import log_command_usage
from datetime import datetime, timezone, timedelta
import logging

# Supabase helper to resolve configured users to their telegram id
from Supabase.supabase_client import (
    get_tele_id_for_user,
    get_user_by_tele_id,
    get_all_users_with_tele_id,
    get_wake_cooldown,
    set_wake_cooldown,
)
from Toggl.status import check_toggl_status





async def _mention_html(user: User) -> str:
    name = html.escape(user.full_name or user.first_name or "User")
    return f'<a href="tg://user?id={user.id}">{name}</a>'

@log_command_usage('wake')
async def wake(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Command handler to "wake" a user.
    Finds the target user by:
      - reply (highest priority),
      - @username (bot.get_chat('@username')),
      - numeric user id,
      - attempt to match among chat administrators by name.
    Sends a private message to the target: "Start studying" plus mention of the sender.
    Replies in the origin chat confirming success or reporting an error.
    """
    if update.effective_message is None:
        return
    sender = update.effective_user
    chat = update.effective_chat
    bot = context.bot

    # Build a sender mention and a default private message used for the "wake all" path.
    # This avoids NameError when sending inside the loop and allows informative logging.
    sender_mention = await _mention_html(sender)
    private_text_all = (
        f"⏰ Hey!\n\n"
        f"It's time to start studying — you were woken up by {sender_mention}.\n\n"
        f"Get going and good luck!"
    )

    # Determine target
    # Determine target
    target_user_id: Optional[int] = None
    target_name_display: str = ""
    target_user_obj: Optional[User] = None

    # 1) If command is a reply, use the replied-to user
    if update.effective_message.reply_to_message and update.effective_message.reply_to_message.from_user:
        target_user_obj = update.effective_message.reply_to_message.from_user
        target_user_id = target_user_obj.id
        target_name_display = target_user_obj.full_name or target_user_obj.first_name

    else:
        args = context.args or []
        if not args:
            # Show centralized wake menu
            try:
                from Utilities.button_handlers import show_wake_menu
                await show_wake_menu(update, context)
            except Exception:
                await update.effective_message.reply_text("Who would you like to wake?")
            return

        name = args[0].strip()

        # Special case: wake all configured users (except the sender)
        if name.lower() == 'all':
            users = get_all_users_with_tele_id()
            if not users:
                await update.effective_message.reply_text("No configured users with Telegram IDs found.")
                return

            summary = {
                'sent': 0,
                'skipped_self': 0,
                'already_studying': 0,
                'rate_limited': 0,
                'failed': 0,
            }

            for row in users:
                try:
                    tele = row.get('tele_id')
                    if not tele:
                        continue
                    # Skip sender
                    try:
                        if int(tele) == sender.id:
                            summary['skipped_self'] += 1
                            continue
                    except Exception:
                        if str(tele) == str(sender.id):
                            summary['skipped_self'] += 1
                            continue

                    # Check if already studying
                    try:
                        toggl_token = row.get('toggl_token')
                        if toggl_token:
                            entry = check_toggl_status(toggl_token)
                            if entry and not (isinstance(entry, dict) and 'error' in entry):
                                summary['already_studying'] += 1
                                continue
                    except Exception:
                        pass

                    # Rate limit per sender->target. Persisted per-target in Supabase
                    try:
                        wake_map = context.application.bot_data.setdefault('wake_map', {})
                    except Exception:
                        wake_map = {}

                    # Ensure we have a per-target dict cached
                    tele_key = str(tele)
                    if tele_key not in wake_map:
                        try:
                            db_wc = get_wake_cooldown(tele_key)
                        except Exception:
                            db_wc = None
                        wake_map[tele_key] = db_wc or {}

                    last_iso = wake_map[tele_key].get(str(sender.id))
                    rate_limited = False
                    if last_iso:
                        try:
                            last_dt = datetime.fromisoformat(last_iso)
                            elapsed = datetime.now(timezone.utc) - last_dt
                            if elapsed.total_seconds() < 3600:
                                rate_limited = True
                        except Exception:
                            # If parsing fails, do not rate-limit this send
                            rate_limited = False

                    if rate_limited:
                        summary['rate_limited'] += 1
                        continue

                    # Attempt send
                    try:
                        await bot.send_message(chat_id=int(tele), text=private_text_all, parse_mode=ParseMode.HTML)
                        summary['sent'] += 1
                        # Update rate limiter timestamp (in-memory + persist)
                        try:
                            wake_map.setdefault(tele_key, {})[str(sender.id)] = datetime.now(timezone.utc).isoformat()
                            try:
                                set_wake_cooldown(tele_key, wake_map[tele_key])
                            except Exception:
                                logging.exception("Failed to persist wake_cooldown for tele_id=%s", tele_key)
                        except Exception:
                            pass
                    except Exception:
                        # Log the exception (with traceback) so you can see why sending failed
                        logging.exception("Failed to send wake message to tele_id=%s (row=%s)", tele, row)
                        summary['failed'] += 1
                        continue

                except Exception:
                    summary['failed'] += 1
                    continue

            await update.effective_message.reply_text(
                f"Wake-all completed. Sent: {summary['sent']}. Already studying: {summary['already_studying']}. Rate-limited: {summary['rate_limited']}. Skipped self: {summary['skipped_self']}. Failed: {summary['failed']}"
            )
            return

        # 2) If mentions a username like @username, try to resolve to a chat (works if bot can access the user)
        if name.startswith("@"):
            try:
                target_chat: Chat = await bot.get_chat(name)
                target_user_id = target_chat.id
                target_name_display = getattr(target_chat, "first_name", None) or getattr(target_chat, "title", name)
            except Exception:
                # fall through to other methods
                target_user_id = None

        # 3) If numeric id provided
        if target_user_id is None and name.isdigit():
            target_user_id = int(name)
            target_name_display = name

        # 4) If argument is not numeric and not a username starting with @, try resolving as a configured user key
        if target_user_id is None and not name.startswith("@"):
            # Try to find a tele_id stored in Supabase for this user key
            try:
                tele = get_tele_id_for_user(name.lower())
                if tele:
                    # tele is stored as string in Supabase; convert to int when possible
                    try:
                        target_user_id = int(tele)
                    except Exception:
                        # If it can't be parsed, keep as string id (Telegram accepts numeric ids)
                        target_user_id = tele
                    target_name_display = name
            except Exception:
                pass

        # 4) Try to match among chat administrators by name substring (best-effort)
        if target_user_id is None and chat is not None:
            try:
                admins = await bot.get_chat_administrators(chat.id)
                lowered = name.lstrip("@").lower()
                for member in admins:
                    u = member.user
                    if lowered in (u.username or "").lower() or lowered in (u.full_name or "").lower() or lowered in (u.first_name or "").lower():
                        target_user_obj = u
                        target_user_id = u.id
                        target_name_display = u.full_name or u.first_name
                        break
            except Exception:
                pass  # ignore admin lookup failures

    if target_user_id is None:
        await update.effective_message.reply_text("Could not resolve the target user. Try using @username, numeric id, or reply to the user.")
        return

    # Build messages
    sender_mention = await _mention_html(sender)
    if target_user_obj:
        target_mention_for_chat = await _mention_html(target_user_obj)
        target_display_safe = html.escape(target_user_obj.full_name or target_user_obj.first_name or str(target_user_id))
    else:
        # We only have id/display string; create a generic mention for the confirmation in the group (no clickable user)
        target_mention_for_chat = html.escape(target_name_display or str(target_user_id))
        target_display_safe = html.escape(target_name_display or str(target_user_id))

    private_text = (
        f"⏰ Hey!\n\n"
        f"It's time to start studying — you were woken up by {sender_mention}.\n\n"
        f"Get going and good luck!"
    )

    # Attempt sending private message
    try:
        # Before sending, check if the target (if configured in Supabase) is already studying
        try:
            # We may have target_user_obj (a User) or only a numeric id; convert to string
            lookup_id = str(target_user_obj.id) if target_user_obj else str(target_user_id)
            db_row = get_user_by_tele_id(lookup_id)
            if db_row and db_row.get('toggl_token'):
                toggl_token = db_row.get('toggl_token')
                entry = check_toggl_status(toggl_token)
                # If entry is not None and not an error, someone is currently tracking
                if entry and not (isinstance(entry, dict) and 'error' in entry):
                    await update.effective_message.reply_text("The person is already studying")
                    return
        except Exception:
            # If anything fails during the check, fall back to sending the message as normal
            pass
        # Rate limit: a sender cannot wake the same target more than once per hour
        try:
            wake_map = context.application.bot_data.setdefault('wake_map', {})
        except Exception:
            # Fallback if application or bot_data isn't available
            wake_map = {}

        tele_key = str(target_user_id)
        if tele_key not in wake_map:
            try:
                db_wc = get_wake_cooldown(tele_key)
            except Exception:
                db_wc = None
            wake_map[tele_key] = db_wc or {}

        last_iso = wake_map[tele_key].get(str(sender.id))
        if last_iso:
            try:
                last_dt = datetime.fromisoformat(last_iso)
            except Exception:
                last_dt = None
        else:
            last_dt = None

        if last_dt is not None:
            elapsed = datetime.now(timezone.utc) - last_dt
            if elapsed.total_seconds() < 3600:
                remaining = timedelta(seconds=3600) - elapsed
                mins = int(remaining.total_seconds() // 60) + (1 if remaining.total_seconds() % 60 else 0)
                await update.effective_message.reply_text(
                    f"⏱ You can only wake the same person once per hour. Try again in about {mins} minute(s)."
                )
                return

        await bot.send_message(
            chat_id=target_user_id,
            text=private_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
    except Exception as e:
        # Common reason: bot can't message the user (privacy settings) or blocked
        await update.effective_message.reply_text(
            f"Could not send a private message to {target_display_safe}. They may not have started the bot or blocked it.\nError: {e}"
        )
        return

    # Confirm back in chat
    await update.effective_message.reply_text(
        f"Sent a wake-up message to {target_mention_for_chat} (from {sender_mention}).",
        parse_mode=ParseMode.HTML,
    )
    # Update rate limiter timestamp for this sender->target pair (persisted)
    try:
        wake_map = context.application.bot_data.setdefault('wake_map', {})
        tele_key = str(target_user_id)
        wake_map.setdefault(tele_key, {})[str(sender.id)] = datetime.now(timezone.utc).isoformat()
        try:
            set_wake_cooldown(tele_key, wake_map[tele_key])
        except Exception:
            logging.exception("Failed to persist wake_cooldown for tele_id=%s", tele_key)
    except Exception:
        pass
