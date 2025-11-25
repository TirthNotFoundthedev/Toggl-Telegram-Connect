from datetime import datetime, timedelta, timezone
import requests

from Toggl.general import format_duration
from Supabase.supabase_client import get_user_by_tele_id

from telegram import Update
from telegram.ext import ContextTypes
from Utilities.command_logging import log_command_usage


ENTRIES_URL = "https://api.track.toggl.com/api/v9/me/time_entries"


@log_command_usage('leaderboard')
async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show leaderboard of total tracked time across configured users.

    Usage:
      /leaderboard [daily|weekly] [-N]
      -N can be an offset from -1 to -50.
    """
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    if not toggl_token_map:
        await update.message.reply_text(
            "Configuration Error: No Toggl tokens are set up. Use the `/add_user` command to begin.",
            parse_mode='Markdown'
        )
        return

    local_tz = datetime.now().astimezone().tzinfo
    now_local = datetime.now().astimezone()
    
    args = list(context.args or [])
    period = 'daily'
    offset = 0

    # Normalize arguments
    if 'daily' in args or 'day' in args:
        period = 'daily'
        if 'daily' in args: args.remove('daily')
        if 'day' in args: args.remove('day')
    elif 'weekly' in args or 'week' in args:
        period = 'weekly'
        if 'weekly' in args: args.remove('weekly')
        if 'week' in args: args.remove('week')

    # Find and parse offset
    offset_arg = next((arg for arg in args if arg.startswith('-') and arg[1:].isdigit()), None)
    if offset_arg:
        try:
            val = int(offset_arg)
            if -50 <= val <= -1:
                offset = val
                args.remove(offset_arg)
            else:
                await update.message.reply_text("Offset must be between -1 and -50.")
                return
        except ValueError:
            pass # Should not happen due to the check above

    if args: # If any unrecognized arguments are left
        await update.message.reply_text(
            "Usage: `/leaderboard [daily|weekly] [-N]` where N is 1-50."
        )
        return

    # Compute time window
    if period == 'daily':
        target_date = now_local.date() + timedelta(days=offset)
        start_local = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=local_tz)
        end_local = start_local + timedelta(days=1)
        title_period = f"Daily leaderboard for {target_date.strftime('%d/%m/%y')}"
    else: # weekly
        today = now_local.date()
        # Calculate the start of the week (Monday) for the target week
        start_of_current_week = today - timedelta(days=today.weekday())
        start_of_target_week = start_of_current_week + timedelta(weeks=offset)
        
        # The end of the target week is 6 days after the start
        end_of_target_week = start_of_target_week + timedelta(days=6)

        start_local = datetime.combine(start_of_target_week, datetime.min.time()).replace(tzinfo=local_tz)
        # For the current week, the end date should be now, not the end of the week
        if offset == 0:
            end_local = now_local
            title_period = f"Weekly leaderboard (since {start_local.date().strftime('%d/%m/%y')})"
        else:
            end_local = datetime.combine(end_of_target_week, datetime.max.time()).replace(tzinfo=local_tz)
            title_period = f"Weekly leaderboard ({start_local.date().strftime('%d/%m/%y')} - {end_local.date().strftime('%d/%m/%y')})"


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

        def safe_start_dt(e):
            s = e.get('start')
            if not s: return None
            try: return datetime.fromisoformat(s.replace('Z', '+00:00'))
            except Exception: return None

        total_seconds = 0
        for e in entries:
            sdt = safe_start_dt(e)
            if not sdt or not (start_local.astimezone(timezone.utc) <= sdt < end_local.astimezone(timezone.utc)):
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
                except Exception: pass
        
        totals.append((user_key, total_seconds, None))

    successful = sorted([(u, s) for (u, s, e) in totals if e is None], key=lambda x: x[1] or 0, reverse=True)

    lines = [f"📊 *{title_period}*\n"]
    if not successful:
        lines.append("No totals available.")
    else:
        for idx, (u, secs) in enumerate(successful, start=1):
            display = u.capitalize()
            formatted = format_duration(secs or 0)
            if idx == 1:
                lines.append(f"1. 🏆 *{display}*: `{formatted}`")
            else:
                lines.append(f"{idx}. {display}: `{formatted}`")

    for (u, s, err) in totals:
        if err:
            lines.append(f"- {u.capitalize()}: 🚨 {err}")

    await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
