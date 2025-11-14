# Project Info

This document provides a high-level overview of the Python files in this project.

## `main.py`

The main entry point of the bot. It initializes the Telegram bot, loads environment variables, connects to Supabase, loads user tokens from the database, and registers all the command handlers.

## `Supabase/supabase_client.py`

This file manages all interactions with the Supabase database. It includes functions for initializing the client, loading and saving user tokens, and logging command usage.

## `Toggl/fnr.py`

This file contains the logic for the `/fnr` command, which calculates the Focus to Noise Ratio for a user's Toggl entries.

## `Toggl/general.py`

This file provides general utility functions for interacting with the Toggl API, such as fetching project names and formatting durations.

## `Toggl/leaderboard.py`

This file contains the logic for the `/leaderboard` command, which displays a leaderboard of user activity.

## `Toggl/status.py`

This file contains the logic for the `/status` command, which checks the current Toggl status of a user.

## `Toggl/today.py`

This file contains the logic for the `/today` command, which provides a summary of a user's Toggl entries for the day.

## `Toggl/wake.py`

This file contains the logic for the `/wake` command, which sends a "wake up" message to a user.

## `Utilities/admin.py`

This file contains administrative commands, such as viewing and resetting wake cooldowns.

## `Utilities/button_handlers.py`

This file manages the interactive buttons and menus for the Telegram bot.

## `Utilities/command_logging.py`

This file provides a decorator for logging command usage to the Supabase database.

## `Utilities/general.py`

This file contains general utility functions for the bot, such as the `/start` command.

## `Utilities/users.py`

This file contains user management commands, such as `/add_user` and `/users`.
