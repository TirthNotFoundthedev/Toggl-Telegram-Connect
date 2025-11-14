from datetime import datetime, timedelta, timezone
import requests

from Toggl.general import format_duration
from Supabase.supabase_client import get_user_by_tele_id

from telegram import Update
from telegram.ext import ContextTypes
from Utilities.button_handlers import show_leaderboard_menu
from Utilities.command_logging import log_command_usage


ENTRIES_URL = "https://api.track.toggl.com/api/v9/me/time_entries"


@log_command_usage('leaderboard')
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show leaderboard of total tracked time across configured users.

    Usage:
      /leaderboard           (or /lb) -> shows daily leaderboard (default)
      /leaderboard weekly    -> shows current week's leaderboard
    """
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    if not toggl_token_map:
        await update.message.reply_text(
            "Configuration Error: No Toggl tokens are set up. Use the `/add_user` command to begin.",
            parse_mode='Markdown'
        )
        return

    # Determine period and target_date
    local_tz = datetime.now().astimezone().tzinfo
    now_local = datetime.now().astimezone()
    target_date = now_local.date() # Default to today
    period = 'daily' # Default period

    args = context.args or []
    original_args = list(args) # Keep original args for menu check

    # Check for /lb alias with no arguments
    if not args:
        raw = None
        if update and update.effective_message and getattr(update.effective_message, 'text', None):
            raw = update.effective_message.text.strip()
        first = raw.split()[0].lower() if raw else ''
        if first.startswith('/lb') and (first == '/lb' or first.startswith('/lb@')):
            # If it's just /lb, force daily behavior
            pass # period is already 'daily', target_date is 'today'
        else:
            # If it's /leaderboard with no args, show menu
            try:
                await show_leaderboard_menu(update, context)
                return
            except Exception:
                pass # Fallback to daily if menu fails

    # Try to parse date argument first if present
    date_parsed = False
    if args:
        arg_val = args[0].lower()
        if arg_val == '-1':
            target_date = now_local.date() - timedelta(days=1)
            args.pop(0) # Consume the argument
            date_parsed = True
        else:
            try:
                parsed_date = datetime.strptime(arg_val, '%d/%m/%y').date()
                target_date = parsed_date
                args.pop(0) # Consume the argument
                date_parsed = True
            except ValueError:
                pass # Not a date, continue to period parsing

    # Now parse period if any arguments remain and no date was explicitly set
    if args:
        a = args[0].lower()
        if a in ('weekly', 'week'):
            period = 'weekly'
            args.pop(0) # Consume the argument
        elif a in ('daily', 'day'):
            period = 'daily'
            args.pop(0) # Consume the argument
        else:
            # If it's not a recognized period, and not a date, show menu
            # This case should only happen if there's an unrecognized argument after a date, or as the first arg
            if not date_parsed and not original_args[0].lower() in ('weekly', 'week', 'daily', 'day'):
                try:
                    await show_leaderboard_menu(update, context)
                    return
                except Exception:
                    pass # Fallback to daily if menu fails

    # Compute time window based on period and target_date
    if period == 'daily':
        start_local = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=local_tz)
        end_local = start_local + timedelta(days=1)
        title_period = f"Daily leaderboard for {target_date.strftime('%d/%m/%y')}"
    else: # weekly
        # For weekly, target_date is ignored, always use current week
        today = now_local.date()
        monday = today - timedelta(days=today.weekday())
        start_local = datetime.combine(monday, datetime.min.time()).replace(tzinfo=local_tz)
        end_local = now_local
        title_period = f"Weekly leaderboard (since {start_local.date().strftime('%d/%m/%y')})"

    start_iso = start_local.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    end_iso = end_local.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    totals = []
    for user_key, token in sorted(toggl_token_map.items()):
        try:
            resp = requests.get(
                ENTRIES_URL,
                auth=(token, 'api_token'),
                params={'start': start_iso, 'end': end_iso},
                timeout=10
            )
            resp.raise_for_status()
            entries = resp.json()
        except requests.exceptions.HTTPError as errh:
            if errh.response.status_code in [401, 403]:
                totals.append((user_key, None, 'auth'))
                continue
            totals.append((user_key, None, f'http:{errh}'))
            continue
        except requests.exceptions.RequestException as err:
            totals.append((user_key, None, f'net:{err}'))
            continue
        except Exception as e:
            totals.append((user_key, None, str(e)))
            continue

        # Sum durations for entries whose start is within local-day/week bounds
        def safe_start_dt(e):
            s = e.get('start')
            if not s:
                return None
            try:
                return datetime.fromisoformat(s.replace('Z', '+00:00'))
            except Exception:
                return None

        total_seconds = 0
        for e in entries:
            sdt = safe_start_dt(e)
            if not sdt:
                continue
            if not (start_local.astimezone(timezone.utc) <= sdt < end_local.astimezone(timezone.utc)):
                continue

            duration_val = e.get('duration')
            if isinstance(duration_val, int) and duration_val >= 0:
                total_seconds += int(duration_val)
            else:
                try:
                    start_s = e.get('start')
                    stop_s = e.get('stop')
                    start_dt = datetime.fromisoformat(start_s.replace('Z', '+00:00'))
                    stop_dt = datetime.fromisoformat(stop_s.replace('Z', '+00:00')) if stop_s else datetime.now(timezone.utc)
                    total_seconds += int((stop_dt - start_dt).total_seconds())
                except Exception:
                    pass

        totals.append((user_key, total_seconds, None))

    # Sort by total_seconds descending, handle errors to bottom
    successful = [(u, s) for (u, s, e) in totals if e is None]
    successful.sort(key=lambda x: x[1] or 0, reverse=True)

    lines = [f"📊 *{title_period}*\n"]
    if not successful:
        lines.append("No totals available.")
    else:
        for idx, (u, secs) in enumerate(successful, start=1):
            display = u.capitalize()
            formatted = format_duration(secs or 0)
            if idx == 1:
                # make first person stand out
                lines.append(f"1. 🏆 *{display}*: `{formatted}`")
            else:
                lines.append(f"{idx}. {display}: `{formatted}`")

    # Append error lines if any
    for (u, s, err) in totals:
        if err:
            lines.append(f"- {u.capitalize()}: 🚨 {err}")

    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
