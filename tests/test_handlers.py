import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from telegram import Update, ChatMember

import handlers
from handlers import greet_new_user, translate_message, remove_left_user, bot_removed_from_chat, bot_added_to_chat

# Create mock Update and Context objects
UPDATE = MagicMock()
CONTEXT = MagicMock()

# Set the context.bot.username value
CONTEXT.bot.username = "TestBot"

# Mock the bot send_message method to be asynchronous
async def async_send_message(*args, **kwargs):
    pass

CONTEXT.bot.send_message = AsyncMock(side_effect=async_send_message)
CONTEXT.bot.send_chat_action = AsyncMock(side_effect=async_send_message)
translate_and_send_messages_mock = AsyncMock(side_effect=async_send_message)
handlers.translate_and_send_messages = translate_and_send_messages_mock


# Set mock values for the Update object
UPDATE.effective_chat.id = "123456"
UPDATE.effective_user.id = "123"
UPDATE.effective_user.full_name = "Test User"
UPDATE.effective_user.username = "testuser"
UPDATE.effective_user.is_bot = False
UPDATE.effective_message.text = "Hello"
UPDATE.effective_message.new_chat_members = [UPDATE.effective_user]
UPDATE.effective_message.left_chat_member = UPDATE.effective_user

# Test for greet_new_user
@pytest.mark.asyncio
async def test_greet_new_user():
    await greet_new_user(UPDATE, CONTEXT)
    CONTEXT.bot.send_message.assert_called()


# Test for translate_message without bot mention
@pytest.mark.asyncio
async def test_translate_message_no_bot_mention():
    CONTEXT.bot.send_message.reset_mock()
    CONTEXT.bot.send_chat_action.reset_mock()
    UPDATE.effective_message.text = "Hello, world!"
    await translate_message(UPDATE, CONTEXT)
    CONTEXT.bot.send_chat_action.assert_called()
    translate_and_send_messages_mock.assert_called()

# Test for translate_message with bot mention and OpenAI response
@pytest.mark.asyncio
async def test_translate_message_with_bot_mention_and_openai_response():
    CONTEXT.bot.send_message.reset_mock()
    CONTEXT.bot.send_chat_action.reset_mock()
    UPDATE.effective_message.text = f"@{CONTEXT.bot.username} tell me a joke"

    with patch("handlers.get_openai_response") as mock_get_openai_response:
        mock_get_openai_response.return_value = "Why did the chicken cross the road? To get to the other side!"
        await translate_message(UPDATE, CONTEXT)
        mock_get_openai_response.assert_called()
        CONTEXT.bot.send_message.assert_called()
        CONTEXT.bot.send_chat_action.assert_called()

# Test for translate_message with bot mention and no OpenAI response
@pytest.mark.asyncio
async def test_translate_message_with_bot_mention_no_openai_response():
    CONTEXT.bot.send_message.reset_mock()
    CONTEXT.bot.send_chat_action.reset_mock()
    UPDATE.effective_message.text = f"@{CONTEXT.bot.username} tell me a joke"

    with patch("handlers.get_openai_response") as mock_get_openai_response:
        mock_get_openai_response.return_value = ""
        await translate_message(UPDATE, CONTEXT)
        mock_get_openai_response.assert_called()
        CONTEXT.bot.send_message.assert_not_called()

# Test for remove_left_user
@pytest.mark.asyncio
async def test_remove_left_user():
    with patch("handlers.db") as mock_db:
        # Ensure the delete method is an AsyncMock
        mock_delete = AsyncMock()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.delete = mock_delete

        await remove_left_user(UPDATE, CONTEXT)

        mock_db.collection.assert_called_with("chats")
        mock_db.collection().document.assert_called_with(str(UPDATE.effective_chat.id))
        mock_db.collection().document().collection.assert_called_with("members")
        mock_db.collection().document().collection().document.assert_called_with(str(UPDATE.effective_user.id))
        mock_delete.assert_awaited_once()

# Test for bot_removed_from_chat
@pytest.mark.asyncio
async def test_bot_removed_from_chat():
    my_chat_member = MagicMock()
    my_chat_member.old_chat_member.status = ChatMember.ADMINISTRATOR
    my_chat_member.new_chat_member.status = ChatMember.BANNED
    UPDATE.my_chat_member = my_chat_member

    with patch("handlers.db") as mock_db:
        await bot_removed_from_chat(UPDATE, CONTEXT)
        mock_db.collection.assert_called_with("chats")
        mock_db.collection().document.assert_called_with(str(UPDATE.effective_chat.id))
        mock_db.collection().document().delete.assert_called()

# Test for bot_added_to_chat
@pytest.mark.asyncio
async def test_bot_added_to_chat():
    my_chat_member = MagicMock()
    my_chat_member.old_chat_member = None
    my_chat_member.new_chat_member.status = ChatMember.ADMINISTRATOR
    UPDATE.my_chat_member = my_chat_member

    with patch("handlers.db") as mock_db:
        await bot_added_to_chat(UPDATE, CONTEXT)
        mock_db.collection.assert_called_with("chats")
        mock_db.collection().document.assert_called_with(str(UPDATE.effective_chat.id))
        mock_db.collection().document().create.assert_called_with({"title": UPDATE.effective_chat.title})
