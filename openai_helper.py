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


import tempfile
import os

async def transcribe_audio(audio_data: bytes) -> str:
    openai.api_key = config.OPENAI_API_KEY
    
    ogg_temp_file = None
    mp3_temp_file = None

    try:
        # Create a temporary file for the OGG data
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as ogg_f:
            ogg_temp_file = ogg_f.name
            ogg_f.write(audio_data)

        # Create a temporary file for the MP3 data
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as mp3_f:
            mp3_temp_file = mp3_f.name
        
        convert_ogg_to_mp3(ogg_temp_file, mp3_temp_file)

        with open(mp3_temp_file, "rb") as audio_f:
            transcript_response = await openai.Audio.transcribe("whisper-1", audio_f)
        
        if transcript_response and 'text' in transcript_response:
            return transcript_response['text'].strip()
        else:
            # Log if the response format is unexpected
            print(f"Unexpected response format from OpenAI: {transcript_response}")
            return None
            
    except OpenAIError as e:
        print(f"Error during OpenAI audio transcription: {e}")
        return None
    except Exception as e:
        # Catch other potential errors, e.g., during file operations or conversion
        print(f"An unexpected error occurred during audio transcription: {e}")
        return None
    finally:
        # Clean up temporary files
        if ogg_temp_file and os.path.exists(ogg_temp_file):
            os.remove(ogg_temp_file)
        if mp3_temp_file and os.path.exists(mp3_temp_file):
            os.remove(mp3_temp_file)
