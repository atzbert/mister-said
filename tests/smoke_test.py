import asyncio
from datetime import datetime

from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes
from unittest.mock import MagicMock

from handlers import greet_new_user, translate_message, remove_left_user, bot_removed_from_chat, bot_added_to_chat
from database import get_previous_messages, get_active_chats, get_user_lang

from google.cloud import firestore

db = firestore.Client()

async def get_previous_messages(chat_id, user_id=None):
    messages_ref = db.collection(u'chats').document(str(chat_id)).collection(u'messages')
    if user_id:
        messages_ref = messages_ref.where('user_id', '==', user_id)
    messages = messages_ref.order_by('timestamp', direction=firestore.Query.ASCENDING).stream()
    return [{"role": "user","content": msg.to_dict()['message_text']} for msg in messages]

async def get_active_chats(chat_id):
    doc_ref = db.collection(u'active_chats').document(str(chat_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()['count']
    return 0

async def get_user_lang(chat_id, user_id):
    doc_ref = db.collection(u'chats').document(str(chat_id)).collection(u'users').document(str(user_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()['lang']
    return None


async def async_send_message(*args, **kwargs):
    return None

async def check_db_state(chat_id, expected_messages, expected_active_chats, expected_user_lang):
    messages = await get_previous_messages(chat_id, user_id=1)
    assert messages == expected_messages

    active_chats = await get_active_chats(chat_id)
    assert active_chats == expected_active_chats

    user_lang = await get_user_lang(chat_id, user_id=1)
    assert user_lang == expected_user_lang

async def main():
    # Set up the context
    context = ContextTypes.DEFAULT_TYPE
    context.bot = MagicMock()
    context.bot.send_message = MagicMock(side_effect=async_send_message)

    # Simulate bot added to group chat
    update = await create_update(user_id=1, chat_id=1)
    update.effective_message.new_chat_members = [User(2, "Bot", True)]
    await greet_new_user(update, context)

    # Check database state
    await check_db_state(1, [], 1, "en")

    # Simulate a user sending a message
    update = await create_update(user_id=1, chat_id=1)
    update.effective_message = Message(2, update.effective_user, update.effective_chat, text="Hello, world!")
    await translate_message(update, context)

    # Check database state
    expected_messages = [{"role": "user", "content": "Hello, world!"}]
    await check_db_state(1, expected_messages, 1, "en")

    # Simulate a user leaving the group chat
    update = await create_update(user_id=1, chat_id=1)
    update.effective_message = Message(3, update.effective_user, update.effective_chat)
    update.effective_message.left_chat_member = User(1, "Test User", False)
    await remove_left_user(update, context)

    # Check database state
    await check_db_state(1, expected_messages, 0, "en")

    # Simulate bot removed from the group chat
    update = Update(4)
    update.effective_chat = Chat(1, "group")
    update.my_chat_member = MagicMock()
    update.my_chat_member.old_chat_member.status = "member"
    update.my_chat_member.new_chat_member.status = "left"
    await bot_removed_from_chat(update, context)

    # Check database state
    await check_db_state(1, expected_messages, 0, "en")


async def create_update(chat_id=1, user_id=1, date=datetime(2023, 1, 1)):
    update = Update(chat_id)
    update.effective_chat = Chat(chat_id, "group")
    update.effective_user = User(user_id, "Test User", False)
    update.effective_message = Message(chat_id, date, update.effective_chat)
    return update
