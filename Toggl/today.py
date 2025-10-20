
from datetime import timedelta, datetime, timezone 
import requests

from Toggl.general import format_duration, get_project_name

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all time entries for the given user for today (or a specified date).
    Uses the local system timezone bounds (so the query covers the same local day),
    and shows only total duration, description and project name for each entry.
    Also shows project-wise totals and the day's total.
    """
    toggl_token_map = context.application.bot_data.get('toggl_token_map', {})
    if not toggl_token_map:
        await update.message.reply_text(
            "Configuration Error: No Toggl tokens are set up. Use the `/add_user` command to begin.",
            parse_mode='Markdown'
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/today <name> [YYYY-MM-DD]`\nExample: `/today alice` or `/today alice 2023-08-01`",
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

    # Determine date to query: either provided or today IN LOCAL TIMEZONE
    try:
        if len(context.args) > 1:
            query_date = datetime.fromisoformat(context.args[1]).date()
        else:
            query_date = datetime.now().astimezone().date()
    except Exception:
        await update.message.reply_text("Invalid date format. Use YYYY-MM-DD.", parse_mode='Markdown')
        return

    # Use local timezone boundaries so the query covers the same local day
    local_tz = datetime.now().astimezone().tzinfo
    start_dt_local = datetime.combine(query_date, datetime.min.time()).replace(tzinfo=local_tz)
    end_dt_local = start_dt_local + timedelta(days=1)

    # Convert to UTC ISO strings for the Toggl API
    start_iso = start_dt_local.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    end_iso = end_dt_local.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

    await update.message.reply_text(
        f"Fetching time entries for *{user_key_input.capitalize()}* on *{query_date}* (local day)...",
        parse_mode='Markdown'
    )

    # Query Toggl: GET /me/time_entries?start=...&end=...
    ENTRIES_URL = "https://api.track.toggl.com/api/v9/me/time_entries"
    try:
        resp = requests.get(
            ENTRIES_URL,
            auth=(toggl_api_token, 'api_token'),
            params={'start': start_iso, 'end': end_iso}
        )
        resp.raise_for_status()
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

    try:
        entries = resp.json()
    except Exception as e:
        await update.message.reply_text(f"Error parsing response: {e}", parse_mode='Markdown')
        return

    # Strictly filter entries to those whose start timestamp falls within the local-day bounds.
    start_boundary_utc = start_dt_local.astimezone(timezone.utc)
    end_boundary_utc = end_dt_local.astimezone(timezone.utc)

    def entry_start_dt(e):
        s = e.get('start')
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            return None

    filtered_entries = []
    for e in entries:
        sdt = entry_start_dt(e)
        if sdt and (start_boundary_utc <= sdt < end_boundary_utc):
            filtered_entries.append(e)

    if not filtered_entries:
        await update.message.reply_text(
            f"No time entries found for *{user_key_input.capitalize()}* on *{query_date}*.",
            parse_mode='Markdown'
        )
        return

    # Cache for project names to avoid repeated API calls
    project_cache = {}

    # Helper to format a single entry line: only duration, project name and description
    def format_entry(e):
        desc = e.get('description') or "_(no description)_"

        # Determine duration in seconds: prefer explicit duration; if running entry, compute from start
        duration_val = e.get('duration')
        if isinstance(duration_val, int) and duration_val >= 0:
            dur_seconds = duration_val
        else:
            try:
                start_s = e.get('start')
                stop_s = e.get('stop')
                start_dt = datetime.fromisoformat(start_s.replace('Z', '+00:00'))
                stop_dt = datetime.fromisoformat(stop_s.replace('Z', '+00:00')) if stop_s else datetime.now(timezone.utc)
                dur_seconds = int((stop_dt - start_dt).total_seconds())
            except Exception:
                dur_seconds = 0

        proj_part = ""
        proj_name = "No Project Assigned"
        proj_id = e.get('project_id')
        workspace_id = e.get('workspace_id')
        if proj_id and workspace_id:
            cache_key = (proj_id, workspace_id)
            if cache_key in project_cache:
                proj_name = project_cache[cache_key]
            else:
                try:
                    pn = get_project_name(toggl_api_token, proj_id, workspace_id)
                except Exception:
                    pn = "Unknown Project"
                project_cache[cache_key] = pn
                proj_name = pn

            proj_part = f" — {proj_name}" if proj_name else ""

        line = f"• `{format_duration(dur_seconds)}`{proj_part}\n  📝 {desc}"
        return line, proj_name, dur_seconds

    # Sort filtered entries by their start time (ascending)
    filtered_entries.sort(key=lambda e: entry_start_dt(e) or datetime.min.replace(tzinfo=timezone.utc))
    formatted_results = [format_entry(ent) for ent in filtered_entries]

    # Compute project-wise totals and day total (use all filtered entries, not just displayed)
    project_totals = {}
    day_total_seconds = 0
    for _, proj_name, seconds in formatted_results:
        project_totals[proj_name] = project_totals.get(proj_name, 0) + int(seconds)
        day_total_seconds += int(seconds)

    # Prepare entry lines (limit display)
    lines = [fr[0] for fr in formatted_results]

    # Limit to a reasonable number to avoid huge messages
    MAX_LINES = 40
    if len(lines) > MAX_LINES:
        footer = f"\nAnd {len(lines)-MAX_LINES} more entries..."
        display_lines = lines[:MAX_LINES]
    else:
        footer = ""
        display_lines = lines

    # Prepare project totals display (sorted by descending time)
    proj_totals_lines = []
    for pname, secs in sorted(project_totals.items(), key=lambda kv: kv[1], reverse=True):
        proj_totals_lines.append(f"- *{pname}*: `{format_duration(secs)}`")

    message = (
        f"📅 *Time entries for {user_key_input.capitalize()} on {query_date}*\n\n"
        + "\n\n".join(display_lines)
        + footer
        + "\n\n📊 *Project totals:*\n"
        + ("\n".join(proj_totals_lines) if proj_totals_lines else "- None")
        + f"\n\n⏱ *Day total:* `{format_duration(day_total_seconds)}`"
    )

    await update.message.reply_text(message, parse_mode='Markdown')