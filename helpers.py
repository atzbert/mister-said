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
        message_counts = {}


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
    user_id = update.effective_user.id

    members_ref = db.collection(u'chats').document(str(chat_id)).collection(u'members')
    members = members_ref.stream()

    translations = {}

    for doc in members:
        lang = doc.to_dict()['preferred_language']
        if lang not in translations:
            try:
                result = translate_client.translate(message_text, target_language=lang)
                translated_text = result['translatedText']
                if translated_text != message_text:
                    translations[lang] = translated_text
            except GoogleAPIError as e:
                print(f"Error translating text: {e}")
                continue

    sent_langs = []
    for lang in translations:
        for doc in members:
            if str(user_id) != doc.id and doc.to_dict()['preferred_language'] == lang and lang not in sent_langs:
                print(f"sending message in {lang} to {doc.id} in chat {chat_id}")
                await context.bot.send_message(chat_id=chat_id, text=translations[lang], reply_to_message_id=update.effective_message.message_id)
                sent_langs.append(lang)


def validate_language(lang_code):
    supported_languages = translate_client.get_languages('en')
    supported_codes = [lang['language'] for lang in supported_languages]
    return lang_code in supported_codes


async def increment_active_chats() -> bool:
    active_chats_ref = db.collection(u'active_chats').document(u'count')
    try:
        active_chats_ref.update({"count": firestore.Increment(1)})
        doc = active_chats_ref.get()
        if doc.exists and doc.to_dict()['count'] <= MAXIMUM_CHATS:
            return True
        else:
            active_chats_ref.update({"count": firestore.Increment(-1)})
            return False
    except FailedPrecondition:
        active_chats_ref.set({"count": 1})
        return True


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


def start_reset_task():
    asyncio.create_task(reset_message_count())
