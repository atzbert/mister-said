import asyncio # Required for new tests
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from google.cloud import translate_v2, firestore
from google.cloud.firestore import Client
from google.cloud.firestore_v1.document import DocumentSnapshot

import config
import helpers
import openai
from helpers import increment_message_count, get_user_lang, validate_language, increment_active_chats
from helpers import translate_and_send_messages
from google.api_core.exceptions import FailedPrecondition

# Replace with your actual chat_id and user_id
CHAT_ID = "123456"
USER_ID = "123"

config.MESSAGE_LIMIT = 2

@pytest.mark.asyncio
async def test_increment_message_count_new_chat():
    chat_id = "new_chat"
    assert await increment_message_count(chat_id) == 1

@pytest.mark.asyncio
async def test_increment_message_count_existing_chat():
    chat_id = "existing_chat"
    await increment_message_count(chat_id)
    assert await increment_message_count(chat_id) == 2

@pytest.mark.asyncio
async def test_increment_message_count_multi_chat():
    chat_id1 = "chat1"
    chat_id2 = "chat2"
    assert await increment_message_count(chat_id1) == 1
    assert await increment_message_count(chat_id2) == 1
    assert await increment_message_count(chat_id1) == 2
    assert await increment_message_count(chat_id2) == 2


def test_get_user_lang_existing_user():
    chat_id = "chat1"
    user_id = "user1"
    user_lang = "en"

    client = MagicMock(spec=Client)
    client.collection().document().collection().document().get().exists = True
    client.collection().document().collection().document().get().to_dict.return_value = {"preferred_language": user_lang}
    helpers.db = client
    result = get_user_lang(chat_id, user_id)

    # Uncomment the following line if the function uses the Firestore client directly
    # result = get_user_lang(chat_id, user_id, client)

    assert result == user_lang

def test_get_user_lang_non_existing_user():
    chat_id = "chat1"
    user_id = "non_existing_user"

    client = MagicMock(spec=Client)
    client.collection().document().collection().document().get().exists = False
    helpers.db = client

    result = get_user_lang(chat_id, user_id)

    # Uncomment the following line if the function uses the Firestore client directly
    # result = get_user_lang(chat_id, user_id, client)

    assert result is None

def test_validate_language():
    assert validate_language("en") is True
    assert validate_language("invalid_code") is False

@pytest.mark.asyncio
async def test_get_openai_response():
    response = await openai.get_openai_response("hello again")
    print(response)


@pytest.mark.asyncio
async def test_increment_active_chats_first_chat_document_does_not_exist():
    """Test case where the 'count' document doesn't exist."""
    mock_db = MagicMock(spec=Client)
    mock_transaction = AsyncMock(spec=firestore.AsyncTransaction)
    mock_doc_ref = MagicMock()
    mock_doc_snapshot = AsyncMock(spec=DocumentSnapshot)
    mock_doc_snapshot.exists = False

    mock_db.collection.return_value.document.return_value = mock_doc_ref
    mock_db.transaction.return_value = mock_transaction
    
    # The transaction.get() is called inside the @firestore.async_transactional decorated function
    # So we need to mock the result of the transaction.get() call
    async def mock_transaction_get_side_effect(doc_ref_arg, **kwargs):
        return mock_doc_snapshot
    
    mock_transaction.get = mock_transaction_get_side_effect

    # Patch firestore.async_transactional to just run the inner function
    # This allows us to avoid dealing with the complexities of the decorator
    # and directly test the logic within _update_count
    with patch("google.cloud.firestore.async_transactional", lambda x: x):
        helpers.db = mock_db
        config.MAXIMUM_CHATS = 5 # Ensure MAXIMUM_CHATS is >= 1
        result = await increment_active_chats()

    assert result is True
    mock_transaction.set.assert_called_once_with(mock_doc_ref, {"count": 1})


@pytest.mark.asyncio
async def test_increment_active_chats_count_less_than_max():
    """Test case where count < MAXIMUM_CHATS."""
    mock_db = MagicMock(spec=Client)
    mock_transaction = AsyncMock(spec=firestore.AsyncTransaction)
    mock_doc_ref = MagicMock()
    mock_doc_snapshot = AsyncMock(spec=DocumentSnapshot)
    mock_doc_snapshot.exists = True
    mock_doc_snapshot.to_dict.return_value = {"count": 2}

    mock_db.collection.return_value.document.return_value = mock_doc_ref
    mock_db.transaction.return_value = mock_transaction
    async def mock_transaction_get_side_effect(doc_ref_arg, **kwargs):
        return mock_doc_snapshot
    mock_transaction.get = mock_transaction_get_side_effect
    
    with patch("google.cloud.firestore.async_transactional", lambda x: x):
        helpers.db = mock_db
        config.MAXIMUM_CHATS = 5
        result = await increment_active_chats()

    assert result is True
    mock_transaction.update.assert_called_once_with(mock_doc_ref, {"count": firestore.Increment(1)})


@pytest.mark.asyncio
async def test_increment_active_chats_count_equals_max():
    """Test case where count == MAXIMUM_CHATS."""
    mock_db = MagicMock(spec=Client)
    mock_transaction = AsyncMock(spec=firestore.AsyncTransaction)
    mock_doc_ref = MagicMock()
    mock_doc_snapshot = AsyncMock(spec=DocumentSnapshot)
    mock_doc_snapshot.exists = True
    mock_doc_snapshot.to_dict.return_value = {"count": 5}

    mock_db.collection.return_value.document.return_value = mock_doc_ref
    mock_db.transaction.return_value = mock_transaction
    async def mock_transaction_get_side_effect(doc_ref_arg, **kwargs):
        return mock_doc_snapshot
    mock_transaction.get = mock_transaction_get_side_effect

    with patch("google.cloud.firestore.async_transactional", lambda x: x):
        helpers.db = mock_db
        config.MAXIMUM_CHATS = 5
        result = await increment_active_chats()

    assert result is False
    mock_transaction.update.assert_not_called()
    mock_transaction.set.assert_not_called()


@pytest.mark.asyncio
async def test_increment_active_chats_max_chats_zero_new_document():
    """Test case where MAXIMUM_CHATS is 0 and document doesn't exist."""
    mock_db = MagicMock(spec=Client)
    mock_transaction = AsyncMock(spec=firestore.AsyncTransaction)
    mock_doc_ref = MagicMock()
    mock_doc_snapshot = AsyncMock(spec=DocumentSnapshot)
    mock_doc_snapshot.exists = False

    mock_db.collection.return_value.document.return_value = mock_doc_ref
    mock_db.transaction.return_value = mock_transaction
    async def mock_transaction_get_side_effect(doc_ref_arg, **kwargs):
        return mock_doc_snapshot
    mock_transaction.get = mock_transaction_get_side_effect

    with patch("google.cloud.firestore.async_transactional", lambda x: x):
        helpers.db = mock_db
        config.MAXIMUM_CHATS = 0
        result = await increment_active_chats()

    assert result is False
    mock_transaction.set.assert_not_called()


@pytest.mark.asyncio
async def test_increment_active_chats_transaction_exception():
    """Test case where the transaction raises an exception."""
    mock_db = MagicMock(spec=Client)
    mock_transaction = AsyncMock(spec=firestore.AsyncTransaction)

    mock_db.collection.return_value.document.return_value = MagicMock()
    mock_db.transaction.return_value = mock_transaction
    
    async def mock_transaction_side_effect(transaction, doc_ref):
        # This is to simulate the behavior of the decorated function
        # It will call the actual _update_count which in turn calls transaction.get
        # We want the transaction itself, or rather the execution of the transactional function, to fail
        raise Exception("Simulated transaction error")

    # We patch the decorator to essentially call our mock_transaction_side_effect
    # which then simulates an error during the transaction's execution.
    with patch("google.cloud.firestore.async_transactional", return_value=mock_transaction_side_effect):
        helpers.db = mock_db
        config.MAXIMUM_CHATS = 5
        result = await increment_active_chats()

    assert result is False



@pytest.mark.asyncio
@patch("helpers.translate_client")
@patch("helpers.db")
async def test_translate_and_send_messages_and_skip_sender(mock_db, mock_translate_client):
    # Set up the mock for the members stream
    # user1 (sender) - English
    # user2 - French
    # user3 - Spanish
    # user4 - French (to test grouping)
    mock_members = [
        MagicMock(id="user1", to_dict=lambda: {"preferred_language": "en"}), # Sender
        MagicMock(id="user2", to_dict=lambda: {"preferred_language": "fr"}),
        MagicMock(id="user3", to_dict=lambda: {"preferred_language": "es"}),
        MagicMock(id="user4", to_dict=lambda: {"preferred_language": "fr"}), # Shares language with user2
    ]
    mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = mock_members

    # Set up the mock for the translate_client to return based on target_language
    def custom_translate_side_effect(message, target_language):
        if target_language == "en":
            return {"translatedText": "Translated text in English"} # Different from original
        elif target_language == "fr":
            return {"translatedText": "Texte traduit en français"}
        elif target_language == "es":
            return {"translatedText": "Texto traducido al español"}
        # Case: translation is same as original (e.g. sender's language is 'en', message is 'Hello')
        # For this test, we ensure translated text is different from "Original message"
        # If translate_client returned {"translatedText": "Original message"} for 'en', 
        # then no message would be sent to 'en' users (which is correct).
        raise ValueError(f"Unexpected target_language: {target_language}")

    mock_translate_client.translate.side_effect = custom_translate_side_effect

    # Set up update and context MagicMock objects
    # user1 is the sender of "Original message"
    update = MagicMock(effective_chat=MagicMock(id="chat1"), effective_user=MagicMock(id="user1"), effective_message=MagicMock(message_id="msg1"))
    context = MagicMock(bot=MagicMock(send_message=AsyncMock()))

    # Call the function
    await translate_and_send_messages(update, context, "Original message")

    # Check if translate_client.translate was called correctly (once per unique language)
    # Unique languages are 'en', 'fr', 'es'. So, 3 calls.
    assert mock_translate_client.translate.call_count == 3
    expected_translate_calls = [
        call("Original message", target_language="en"),
        call("Original message", target_language="fr"),
        call("Original message", target_language="es"),
    ]
    mock_translate_client.translate.assert_has_calls(expected_translate_calls, any_order=True)

    # Check if the messages were sent to the correct users with correct text
    # user1 (en) is sender, so no message.
    # user2 (fr) gets French text.
    # user3 (es) gets Spanish text.
    # user4 (fr) gets French text.
    expected_send_calls = [
        call(chat_id="chat1", text="Texte traduit en français", reply_to_message_id="msg1"), # for user2
        call(chat_id="chat1", text="Texto traducido al español", reply_to_message_id="msg1"), # for user3
        call(chat_id="chat1", text="Texte traduit en français", reply_to_message_id="msg1"), # for user4
    ]
    context.bot.send_message.assert_has_calls(expected_send_calls, any_order=True)
    # Ensure send_message was called 3 times
    assert context.bot.send_message.call_count == 3



@pytest.fixture
def firestore_mock():
    with patch("helpers.firestore.Client") as mock_client:
        yield mock_client

@pytest.mark.asyncio
async def test_get_previous_messages():
    chat_id = "chat1"
    user_id = "user1"

    mock_doc_1 = MagicMock(id="1", to_dict=lambda: {"user_id": "user1", "message_text": "Test message 1", "role": "user", "timestamp": "2023-01-01"})
    mock_doc_2 = MagicMock(id="2", to_dict=lambda: {"user_id": "user1", "message_text": "Test response 1", "role": "assistant", "timestamp": "2023-01-02"})
    mock_doc_3 = MagicMock(id="2", to_dict=lambda: {"user_id": "user1", "message_text": "Test message 2", "role": "user", "timestamp": "2023-01-03"})

    with patch('helpers.db') as mock_db:
        mock_db.collection.return_value.document.return_value.collection.return_value.where.return_value.order_by.return_value.stream.return_value = [mock_doc_1, mock_doc_2, mock_doc_3]

        result = await helpers.get_previous_messages(chat_id, user_id)
        expected = [
            {"role": "user", "content": "Test message 1"},
            {"role": "assistant", "content": "Test response 1"},
            {"role": "user", "content": "Test message 2"}
        ]

        assert result == expected

@pytest.mark.asyncio
async def test_store_message_for_user():
    chat_id = "chat1"
    user_id = "user1"
    message_text = "Test message"

    with patch('helpers.db') as mock_db:
        await helpers.store_message(chat_id, user_id, message_text)
        mock_db.collection.return_value.document.return_value.collection.return_value.add.assert_called_once_with({
            'user_id': user_id,
            'message_text': message_text,
            'role': "user",
            'timestamp': firestore.SERVER_TIMESTAMP
        })

# --- Tests for reset_message_count and start_reset_task ---

@pytest.mark.asyncio
@patch('helpers.asyncio.sleep', new_callable=AsyncMock) # Mock sleep to prevent actual sleeping
@patch('helpers.db')
async def test_reset_message_count_rebuilds_from_firestore(mock_db, mock_sleep):
    """
    Test that reset_message_count rebuilds message_counts based on active chats in Firestore,
    and resets their counts to 0.
    """
    # Initial state: some chats exist, some don't match Firestore
    helpers.message_counts = {"chat1": 10, "chat2": 5, "stale_chat": 100}

    # Mock Firestore stream to return specific active chats
    mock_chat_doc1 = MagicMock(id="chat1")
    mock_chat_doc2 = MagicMock(id="chat2_new") # A new chat not previously in message_counts
    
    # Create an async iterable from the mock documents
    async def mock_stream_generator():
        yield mock_chat_doc1
        yield mock_chat_doc2
        
    mock_db.collection.return_value.stream.return_value = mock_stream_generator()

    # We need to run reset_message_count once, not its infinite loop.
    # We can do this by making asyncio.sleep raise an exception after the first call.
    mock_sleep.side_effect = asyncio.CancelledError # Stop the loop after one iteration

    with pytest.raises(asyncio.CancelledError): # Expect CancelledError to break the loop
        await helpers.reset_message_count()

    # Assertions:
    # - 'stale_chat' should be gone.
    # - 'chat1' should be reset to 0.
    # - 'chat2' (which was not in Firestore mock) should be gone.
    # - 'chat2_new' (from Firestore mock) should be added and set to 0.
    assert "stale_chat" not in helpers.message_counts
    assert "chat2" not in helpers.message_counts
    assert helpers.message_counts.get("chat1") == 0
    assert helpers.message_counts.get("chat2_new") == 0
    assert len(helpers.message_counts) == 2

    # Ensure sleep was called (meaning one loop iteration started)
    mock_sleep.assert_awaited_once_with(86400)
    mock_db.collection.assert_called_once_with(u'chats')


@pytest.mark.asyncio
@patch('helpers.asyncio.sleep', new_callable=AsyncMock) # Mock sleep
@patch('helpers.db')
async def test_reset_message_count_firestore_error_fallback(mock_db, mock_sleep):
    """
    Test that reset_message_count falls back to clearing message_counts
    if Firestore operations fail.
    """
    helpers.message_counts = {"chat1": 10, "chat2": 5} # Initial state

    # Mock Firestore stream to raise an exception
    mock_db.collection.return_value.stream.side_effect = Exception("Firestore unavailable")

    mock_sleep.side_effect = asyncio.CancelledError # Stop the loop after one iteration

    with pytest.raises(asyncio.CancelledError):
        await helpers.reset_message_count()

    # Assertions:
    # - message_counts should be empty due to fallback.
    assert helpers.message_counts == {}
    mock_sleep.assert_awaited_once_with(86400)


def test_start_reset_task_returns_task_object():
    """
    Test that start_reset_task creates and returns an asyncio.Task.
    """
    # We need an event loop to create a task, even if it's a mock one for this sync test part
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    with patch('helpers.asyncio.create_task') as mock_create_task:
        mock_task = MagicMock(spec=asyncio.Task)
        mock_create_task.return_value = mock_task
        
        returned_task = helpers.start_reset_task()
        
        mock_create_task.assert_called_once_with(helpers.reset_message_count())
        assert returned_task == mock_task

    # Clean up the loop if we created one for this test
    if not asyncio.get_event_loop().is_running(): # Check if we set a new loop that isn't running
        asyncio.set_event_loop(None)
        loop.close()

@pytest.mark.asyncio
async def test_store_message_for_assistant():
    chat_id = "chat1"
    user_id = "user1"
    message_text = "Test message"

    with patch('helpers.db') as mock_db:
        await helpers.store_message(chat_id, user_id, message_text, role='assistant')
        mock_db.collection.return_value.document.return_value.collection.return_value.add.assert_called_once_with({
            'user_id': user_id,
            'message_text': message_text,
            'role': "assistant",
            'timestamp': firestore.SERVER_TIMESTAMP
        })
