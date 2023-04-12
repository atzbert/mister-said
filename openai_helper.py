import openai
import config
from openai import OpenAIError
from config import OPENAI_API_KEY
from helpers import convert_ogg_to_mp3


async def get_openai_response(messages) -> str:
    openai.api_key = OPENAI_API_KEY
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        print(response)
        if response['choices'][0]:
            message_content = response['choices'][0]['message']['content'].strip()
            return message_content
    except OpenAIError as e:
        print(f"Error getting response from OpenAI: {e}")
    return None


async def transcribe_audio(audio_data: bytes) -> str:
    openai.api_key = config.OPENAI_API_KEY

    with open("my_file.ogg", "wb") as f:
        f.write(audio_data)
    convert_ogg_to_mp3("my_file.ogg", "my_file.mp3")
    audio_file= open("my_file.mp3", "rb")
    transcript = await openai.Audio.transcribe("whisper-1", audio_file)
    if transcript:
        return transcript.strip()
    else:
        return None
