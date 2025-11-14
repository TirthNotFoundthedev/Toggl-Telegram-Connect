# Gemini Notes

This file contains key points for a professional developer to remember about this project.

*   **Project Structure**: The project is a Telegram bot that interacts with the Toggl and Supabase APIs. The code is organized into three main directories: `Toggl` for Toggl-related logic, `Supabase` for Supabase-related logic, and `Utilities` for general utility functions.
*   **Configuration**: The bot is configured through environment variables, which are loaded from a `.env` file. The main configuration variables are `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, and `SUPABASE_KEY`.
*   **Database**: The bot uses a Supabase database to store user tokens and command logs. The `supabase_client.py` file provides a convenient interface for interacting with the database.
*   **Error Handling**: The bot includes error handling for API requests and other potential issues. Errors are logged to the console and, in some cases, sent as messages to the user.
*   **Commands**: The bot supports a variety of commands for checking Toggl status, viewing reports, and managing users. The `main.py` file registers all of the command handlers.
*   **Interactive Menus**: The bot uses interactive menus with buttons to make it easier for users to interact with the bot. The `button_handlers.py` file manages these menus.
