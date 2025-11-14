from telegram import Update
from telegram.ext import ContextTypes
from datetime import timedelta, datetime, timezone
import requests
from typing import List, Dict, Any, Optional

from Toggl.general import format_duration

from Utilities.command_logging import log_command_usage


@log_command_usage('fnr')
async def fnr_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Calculates the Focus to Noise Ratio (FNR) for a user's Toggl entries on a given day.
    FNR = (Total Tracked Duration) / (Total Block Span Time) for continuous blocks.
    A block breaks if the gap between entries is 1.5 hours or more.
    """
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    if not toggl_token_map:
        await update.message.reply_text(
            "Configuration Error: No Toggl tokens are set up. Use the `/add_user` command to begin.",
            parse_mode='Markdown'
        )
        return

    if len(context.args) < 1 or len(context.args) > 2:
        await update.message.reply_text(
            "Usage: `/fnr <user_name> [YYYY-MM-DD or -1..-7 offset]`\n\nExample: `/fnr john -1` (for yesterday)",
            parse_mode='Markdown'
        )
        return

    user_key_input = context.args[0].lower()
    toggl_api_token = toggl_token_map.get(user_key_input)
    if not toggl_api_token:
        available_users = ", ".join([u.capitalize() for u in sorted(toggl_token_map.keys())])
        await update.message.reply_text(
            f"User key '*`{context.args[0]}`*' not found. Available users: *{available_users}*",
            parse_mode='Markdown'
        )
        return

    # 1. Determine date to query (copied from today.py logic)
    query_date = datetime.now().astimezone().date()
    try:
        if len(context.args) > 1:
            arg = context.args[1].strip()
            if arg.startswith('-') and arg[1:].isdigit():
                offset = int(arg)
                if -7 <= offset <= -1:
                    query_date = (datetime.now().astimezone().date() + timedelta(days=offset))
                else:
                    raise ValueError("Offset out of supported range (-1 to -7)")
            else:
                query_date = datetime.fromisoformat(arg).date()
    except Exception:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD or -1..-7 for offsets.", parse_mode='Markdown')
        return

    # Use local timezone boundaries for the day (copied from today.py logic)
    local_tz = datetime.now().astimezone().tzinfo
    start_dt_local = datetime.combine(query_date, datetime.min.time()).replace(tzinfo=local_tz)
    end_dt_local = start_dt_local + timedelta(days=1)

    # Convert to UTC ISO strings for the Toggl API (copied from today.py logic)
    start_iso = start_dt_local.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    end_iso = end_dt_local.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    await update.message.reply_text(
        f"Calculating FNR for *{user_key_input.capitalize()}* on *{query_date}* (local day)...",
        parse_mode='Markdown'
    )

    # 2. Query Toggl API for time entries
    ENTRIES_URL = "https://api.track.toggl.com/api/v9/me/time_entries"
    try:
        resp = requests.get(
            ENTRIES_URL,
            auth=(toggl_api_token, 'api_token'),
            params={'start': start_iso, 'end': end_iso},
            timeout=10
        )
        resp.raise_for_status()
        entries_data: List[Dict[str, Any]] = resp.json()
    except requests.exceptions.HTTPError as errh:
        if errh.response.status_code in [401, 403]:
            await update.message.reply_text(
                f"🚨 Authentication failed for *{user_key_input.capitalize()}*. Check their token.",
                parse_mode='Markdown'
            )
            return
        await update.message.reply_text(f"HTTP Error fetching entries: {errh}", parse_mode='Markdown')
        return
    except requests.exceptions.RequestException as err:
        await update.message.reply_text(f"Network error fetching entries: {err}", parse_mode='Markdown')
        return
    except Exception as e:
        await update.message.reply_text(f"Error processing response: {e}", parse_mode='Markdown')
        return

    # Utility to safely get the datetime from the entry's 'start' field
    def entry_start_dt(e: Dict[str, Any]) -> Optional[datetime]:
        s = e.get('start')
        if not s: return None
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            return None

    # Utility to safely get the datetime from the entry's 'stop' field or current UTC time if running
    def entry_stop_dt(e: Dict[str, Any]) -> datetime:
        s = e.get('stop')
        if not s: return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            # Fallback for stop time if parsing fails
            return datetime.now(timezone.utc)

    # Utility to calculate entry duration in seconds (handle running entries)
    def entry_duration_seconds(e: Dict[str, Any]) -> int:
        duration_val = e.get('duration')
        if isinstance(duration_val, int) and duration_val >= 0:
            return duration_val
        try:
            start_dt = entry_start_dt(e)
            stop_dt = entry_stop_dt(e)
            if start_dt and stop_dt:
                return int((stop_dt - start_dt).total_seconds())
        except Exception:
            pass
        return 0

    # 3. Filter and sort entries based on local day boundaries (copied from today.py logic)
    start_boundary_utc = start_dt_local.astimezone(timezone.utc)
    end_boundary_utc = end_dt_local.astimezone(timezone.utc)

    filtered_entries = []
    for e in entries_data:
        sdt = entry_start_dt(e)
        # Only include entries that started within the local-day bounds
        if sdt and (start_boundary_utc <= sdt < end_boundary_utc):
            filtered_entries.append(e)

    if not filtered_entries:
        await update.message.reply_text(
            f"No time entries found for *{user_key_input.capitalize()}* on *{query_date}* to calculate FNR.",
            parse_mode='Markdown'
        )
        return

    # Sort filtered entries by their start time (ascending)
    filtered_entries.sort(key=lambda e: entry_start_dt(e) or datetime.min.replace(tzinfo=timezone.utc))

    # 4. Calculate FNR for continuous blocks
    results_message_parts = [f"📊 *FNR for {user_key_input.capitalize()} on {query_date}:*"]
    time_gap_limit = timedelta(hours=1,minutes=30) # The 2-hour gap rule

    i = 0
    block_number = 1
    while i < len(filtered_entries):
        # Start of a new block
        current_block_start_dt = entry_start_dt(filtered_entries[i])
        current_block_end_dt = entry_stop_dt(filtered_entries[i])
        current_block_total_tracked_seconds = entry_duration_seconds(filtered_entries[i])

        j = i + 1
        # Continue block while next entry starts within 2 hours of the previous one's stop time
        while j < len(filtered_entries):
            # Check the gap between the *previous* entry's stop time and the *current* (next) entry's start time
            prev_entry_stop_dt = entry_stop_dt(filtered_entries[j-1])
            next_entry_start_dt = entry_start_dt(filtered_entries[j])

            if next_entry_start_dt and (next_entry_start_dt - prev_entry_stop_dt) < time_gap_limit:
                # Still within the continuous block
                current_block_end_dt = entry_stop_dt(filtered_entries[j])
                current_block_total_tracked_seconds += entry_duration_seconds(filtered_entries[j])
                j += 1
            else:
                # Gap is 2 hours or more, or entry is missing start time -> block ends
                break

        # Block calculation
        if current_block_start_dt and current_block_end_dt:
            # The span of the block is from the start of the first entry to the end of the last entry
            block_span_seconds = int((current_block_end_dt - current_block_start_dt).total_seconds())

            if block_span_seconds > 0:
                fnr = (current_block_total_tracked_seconds / block_span_seconds) * 100 # In percentage
            else:
                fnr = 0.0

            # 6. Add the ratio and the start_time and end_time in the response text
            start_time_local = current_block_start_dt.astimezone(local_tz).strftime('%H:%M:%S')
            end_time_local = current_block_end_dt.astimezone(local_tz).strftime('%H:%M:%S')

            results_message_parts.append(
                f"\n**Block {block_number}:**"
                f"\n- Span: `{start_time_local}` to `{end_time_local}`"
                f"\n- Tracked Time: `{format_duration(current_block_total_tracked_seconds)}`"
                f"\n- Span Time: `{format_duration(block_span_seconds)}`"
                f"\n- **FNR:** `{fnr:.2f}%`"
            )
            block_number += 1
        
        # Move to the start of the next block
        i = j

    # 8. If next entry is in the next day, Send the response text as a message as a reply to the command
    if block_number == 1:
        # Only header was added, meaning no entries or blocks were formed
        await update.message.reply_text(
            f"No continuous focus blocks found for *{user_key_input.capitalize()}* on *{query_date}* (local day).",
            parse_mode='Markdown'
        )
    else:
        message = "\n".join(results_message_parts)
        await update.message.reply_text(message, parse_mode='Markdown')