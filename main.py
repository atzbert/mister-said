import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ChatMemberHandler
from config import TELEGRAM_TOKEN
from commands import start, set_lang, my_lang, transcribe_voice_message
from handlers import greet_new_user, remove_left_user, translate_message, bot_removed_from_chat, bot_added_to_chat
from helpers import start_reset_task

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

start_handler = CommandHandler('start', start)
set_lang_handler = CommandHandler('setlang', set_lang)
my_lang_handler = CommandHandler('mylang', my_lang)
message_handler = MessageHandler(filters.TEXT, translate_message)
new_user_handler = ChatMemberHandler(greet_new_user, ChatMemberHandler.CHAT_MEMBER)
left_user_handler = ChatMemberHandler(remove_left_user, ChatMemberHandler.CHAT_MEMBER)
bot_modified_handler = ChatMemberHandler(bot_added_to_chat, ChatMemberHandler.MY_CHAT_MEMBER)
bot_removed_handler = ChatMemberHandler(bot_removed_from_chat, ChatMemberHandler.MY_CHAT_MEMBER)
voice_handler = MessageHandler(filters.VOICE, transcribe_voice_message)

app.add_handler(start_handler)
app.add_handler(set_lang_handler)
app.add_handler(my_lang_handler)
app.add_handler(message_handler)
app.add_handler(new_user_handler)
app.add_handler(left_user_handler)
app.add_handler(bot_modified_handler)
app.add_handler(bot_removed_handler)
app.add_handler(voice_handler)

def handle_task_completion(task: asyncio.Task) -> None:
    """Callback to handle the completion of the reset_message_count task."""
    try:
        # Check if the task raised an exception
        if task.exception() is not None:
            print(f"[ERROR] Reset message count task failed: {task.exception()}")
        else:
            # Optionally, log successful completion or check result if the task returns one
            print("[INFO] Reset message count task completed (or was cancelled).")
    except asyncio.CancelledError:
        print("[INFO] Reset message count task was cancelled.")
    except Exception as e:
        # Log any other error that might occur within the callback itself
        print(f"[ERROR] Exception in handle_task_completion: {e}")

if __name__ == "__main__":
    # Start the background task for resetting message counts
    reset_task = start_reset_task()
    reset_task.add_done_callback(handle_task_completion)

    # Run the bot
    app.run_polling()