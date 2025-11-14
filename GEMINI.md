# Gemini Notes

This file contains key points for a professional developer to remember about this project.

*   **Project Structure**: The project is a Telegram bot that interacts with the Toggl and Supabase APIs. The code is organized into three main directories: `Toggl` for Toggl-related logic, `Supabase` for Supabase-related logic, and `Utilities` for general utility functions.
*   **Configuration**: The bot is configured through environment variables, which are loaded from a `.env` file. The main configuration variables are `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, and `SUPABASE_KEY`.
*   **Database**: The bot uses a Supabase database to store user tokens and command logs. The `supabase_client.py` file provides a convenient interface for interacting with the database.
*   **Error Handling**: The bot includes error handling for API requests and other potential issues. Errors are logged to the console and, in some cases, sent as messages to the user.
*   **Commands**: The bot supports a variety of commands for checking Toggl status, viewing reports, and managing users. The `main.py` file registers all of the command handlers.
*   **Deployment**: To deploy the bot as a single executable, use the following PyInstaller command sequence:
    1.  Run PyInstaller:
        ```bash
        pyinstaller main.py --onefile --noconsole --hidden-import dotenv --hidden-import supabase --hidden-import telegram
        ```
    2.  Delete the old executable (if it exists):
        ```bash
        Remove-Item -Path "dist/Toggl Status Checker.exe" -ErrorAction SilentlyContinue
        ```
    3.  Rename the newly created `main.exe`:
        ```bash
        Rename-Item -Path "dist/main.exe" -NewName "Toggl Status Checker.exe"
        ```
    4.  Run the new executable:
        ```bash
        Start-Process -FilePath "dist/Toggl Status Checker.exe"
        ```
*   **Notifications**: A custom notification script is available at `GEMINI-Addons/notifier.py`. It can be used to send messages via a Telegram bot.

    *   **Usage**: `python GEMINI-Addons/notifier.py "Your message here"`
