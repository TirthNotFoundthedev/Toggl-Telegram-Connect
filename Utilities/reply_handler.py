from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
import logging

logger = logging.getLogger(__name__)

async def handle_wake_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles replies to wake messages sent by the bot.
    Forwards the reply to the original sender of the /wake command.
    Enforces a one-message limit per wake message.
    """
    if not update.effective_message or not update.effective_message.reply_to_message:
        return # Not a reply

    replied_message = update.effective_message.reply_to_message
    bot_user_id = context.bot.id

    # Check if the replied-to message was sent by this bot
    if replied_message.from_user and replied_message.from_user.id == bot_user_id:
        wake_lookup = context.application.bot_data.get('wake_message_lookup', {})
        
        # Check if the replied-to message is a wake message we're tracking
        if replied_message.message_id in wake_lookup:
            wake_data = wake_lookup[replied_message.message_id]
            original_sender_id = wake_data['sender_id']

            # Forward the reply to the original sender
            try:
                # Construct a message to send to the original sender
                replier_mention = update.effective_user.mention_html()
                reply_text = update.effective_message.text or "..."

                forward_text = f"{replier_mention} replied to your wake up message: {reply_text}"

                await context.bot.send_message(
                    chat_id=original_sender_id,
                    text=forward_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                
                # Invalidate the wake message after successful reply
                target_user_id = wake_data['target_id']
                user_active_wake = context.application.bot_data.get('user_active_wake', {})
                
                del wake_lookup[replied_message.message_id]
                if target_user_id in user_active_wake and user_active_wake[target_user_id] == replied_message.message_id:
                    del user_active_wake[target_user_id]

                await update.effective_message.reply_text(
                    "Your reply has been forwarded.",
                    reply_to_message_id=update.effective_message.message_id
                )

            except Exception as e:
                logger.error(f"Failed to forward wake reply: {e}")
                await update.effective_message.reply_text(
                    "Failed to forward your reply. The sender might have blocked the bot.",
                    reply_to_message_id=update.effective_message.message_id
                )
        else:
            # This message is not an active wake message
            await update.effective_message.reply_text(
                "This wake-up message has expired or has already been replied to.",
                reply_to_message_id=update.effective_message.message_id
            )
