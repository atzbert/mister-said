import asyncio

from google.cloud import firestore
from google.cloud import translate_v2 as translate

from config import TELEGRAM_BOT, GOOGLE_API_KEY, MAXIMUM_CHATS
from google.api_core.exceptions import FailedPrecondition
from google.api_core.exceptions import GoogleAPIError

translate_client = translate.Client(GOOGLE_API_KEY)
db = firestore.Client(TELEGRAM_BOT)

message_counts = {}

init_messages=[
    {"role": "system", "content": "From now on you act as Said. You are a 52 years old man living on Zanzibar. "
                                  "You were born on Zanzibar in a small village called Fujoni where you lived your entire life, "
                                  "besides regular trips to Tanzania Mainland, mainly to Dar Es Salam, you never really left the island. "
                                  "You have 7 kids of which 3 are already grown up. You also have three grand childs. "
                                  "You are an unbevielably kind human being who is always willing to help. "
                                  "You speak english like a 5 year old and you speak Swahili fluently. "
                                  "You do not speak any other language, only Swahili and a broken English."
                                  "You have a strong connection to the nature and to the ocean. During the day you like to go running and swimming. "
                                  "At night you go hunting for octopus if the tide is high enough, of course traditionally with a spear. "
                                  "When you meet new people you always at them. Your hugs are always honest and meaningful. "
                                  "You always begin a conversation with 'Mambo' "
                                  "If you don't know the answer you can always respond with either 'Hakuna matata' or Karibu or 'Pole pole' or Poa. "}
]
async def reset_message_count():
    global message_counts
    while True:
        await asyncio.sleep(86400)  # 24 hours in seconds
        
        print("[INFO] Starting daily reset of message_counts.")
        new_message_counts = {}
        try:
            chats_collection_ref = db.collection(u'chats')
            # Asynchronously stream documents. Consider using .list_documents() if only IDs are needed
            # and the number of documents is very large, then .get() them in batches if necessary.
            # For simplicity with smaller number of chats, .stream() is fine.
            active_chat_docs = chats_collection_ref.stream()
            
            async for chat_doc in active_chat_docs:
                new_message_counts[chat_doc.id] = 0 # Reset count to 0 for active chats
            
            message_counts = new_message_counts
            print(f"[INFO] Message counts reset. Tracking {len(message_counts)} active chats.")
        except Exception as e:
            print(f"[ERROR] Failed to reset message counts based on Firestore: {e}")
            # Fallback: Revert to clearing all counts to prevent potential memory issues
            # if Firestore is unavailable for an extended period, though this is the behavior we're improving.
            # Alternatively, could skip reset for this cycle or implement more robust retry/error handling.
            message_counts = {} 
            print("[WARNING] Message counts reset to empty due to error during Firestore sync.")


async def increment_message_count(chat_id):
    global message_counts
    if chat_id in message_counts:
        message_counts[chat_id] += 1
    else:
        message_counts[chat_id] = 1

    return message_counts[chat_id]


def get_user_lang(chat_id, user_id):
    doc_ref = db.collection(u'chats').document(str(chat_id)).collection(u'members').document(str(user_id))
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()['preferred_language']
    else:
        return None


async def translate_and_send_messages(update, context, message_text):
    chat_id = update.effective_chat.id
    sender_user_id = str(update.effective_user.id)

    members_ref = db.collection(u'chats').document(str(chat_id)).collection(u'members')
    members_stream = members_ref.stream() # Changed variable name to avoid confusion

    # 1. Fetch all members' language preferences and 2. Group users by language
    users_by_language = {}
    for member_doc in members_stream:
        member_id = member_doc.id
        # Ensure not to send to the original sender later by excluding them here if needed,
        # or by checking before sending. Current logic checks before sending.
        # if member_id == sender_user_id:
        #     continue 

        try:
            lang = member_doc.to_dict().get('preferred_language')
            if lang:
                if lang not in users_by_language:
                    users_by_language[lang] = []
                users_by_language[lang].append(member_id)
        except Exception as e:
            print(f"Error processing member document {member_id}: {e}")
            continue
            
    # 3. For each unique language in this grouping:
    for lang_code, user_ids_for_lang in users_by_language.items():
        # a. Translate the message *once* for that language.
        translated_text = None
        try:
            # Optimization: If the original message_text is effectively empty or whitespace,
            # translation might not be useful or might even cause errors with some services.
            if not message_text.strip():
                print(f"Skipping translation for empty message in chat {chat_id}.")
                continue

            result = translate_client.translate(message_text, target_language=lang_code)
            translated_text = result['translatedText']
        except GoogleAPIError as e:
            print(f"Error translating text to {lang_code} in chat {chat_id}: {e}")
            continue # Skip this language if translation fails

        # 5. Ensure that a user does not receive a translation if their preferred language 
        # is the same as the source language of the message
        if translated_text == message_text:
            # print(f"Skipping sending for language {lang_code} as translated text is same as original.")
            continue

        if translated_text:
            # b. Iterate through the list of users who prefer this language and send them the translated message.
            for user_id_to_send in user_ids_for_lang:
                # 6. The logic to not send the message to the original sender
                if user_id_to_send == sender_user_id:
                    continue
                
                try:
                    print(f"Sending message in {lang_code} to {user_id_to_send} in chat {chat_id}")
                    await context.bot.send_message(
                        chat_id=chat_id, 
                        text=translated_text, 
                        reply_to_message_id=update.effective_message.message_id
                    )
                except Exception as e:
                    print(f"Error sending translated message to user {user_id_to_send} in chat {chat_id}: {e}")


def validate_language(lang_code):
    supported_languages = translate_client.get_languages('en')
    supported_codes = [lang['language'] for lang in supported_languages]
    return lang_code in supported_codes


async def increment_active_chats() -> bool:
    active_chats_ref = db.collection(u'active_chats').document(u'count')
    transaction = db.transaction()

    @firestore.async_transactional
    async def _update_count(transaction, doc_ref):
        doc = await transaction.get(doc_ref)
        if not doc.exists:
            if MAXIMUM_CHATS >= 1:
                transaction.set(doc_ref, {"count": 1})
                return True
            else:
                return False
        else:
            current_count = doc.to_dict().get("count", 0)
            if current_count < MAXIMUM_CHATS:
                transaction.update(doc_ref, {"count": firestore.Increment(1)})
                return True
            else:
                return False

    try:
        return await _update_count(transaction, active_chats_ref)
    except Exception as e:
        print(f"Error in transaction: {e}")
        return False


async def store_message(chat_id, user_id, message_text, role="user"):
    if not chat_id or not user_id or not message_text:
        print("Error: One or more parameters are empty, storing omitted")
        return None
    else:
        print("storing message: " + message_text)
    messages_ref = db.collection(u'chats').document(str(chat_id)).collection(u'messages')
    msg = {
        'user_id': user_id,
        'message_text': message_text,
        'role': role,
        'timestamp': firestore.SERVER_TIMESTAMP
    }
    messages_ref.add(msg)
    return {"role": msg['role'],"content": msg['message_text']}


async def get_previous_messages(chat_id, user_id):
    messages_ref = db.collection(u'chats').document(str(chat_id)).collection(u'messages')
    messages = messages_ref.where('user_id', '==', user_id).order_by('timestamp', direction=firestore.Query.ASCENDING).stream()
    return [{"role": msg.to_dict()['role'],"content": msg.to_dict()['message_text']} for msg in messages]


# Wrap the openai.Completion.create call in a try-except block
from pydub import AudioSegment

def convert_ogg_to_mp3(input_file, output_file):
    ogg_audio = AudioSegment.from_ogg(input_file)
    ogg_audio.export(output_file, format="mp3")


def start_reset_task() -> asyncio.Task:
    return asyncio.create_task(reset_message_count())
