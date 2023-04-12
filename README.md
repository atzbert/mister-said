# Mister Said - Multilingual Telegram Group Chat Bot

Mister Said is a Telegram bot designed to facilitate multilingual group chat conversations by automatically translating messages sent by users. It uses the Google Translate API for translation and OpenAI's GPT-3.5-turbo for additional assistance when there are only two participants in a chat.

## Features

- Automatically translates messages in group chats based on users' preferred languages.
- Integrates with the OpenAI GPT-3.5-turbo API to provide assistance when only two participants are in a chat.
- Supports a wide range of languages.
- Uses Google Firestore for efficient data storage and retrieval.

## Setup

1. Install Python 3.8 or newer.
2. Clone the repository.
3. Install the required Python packages: `pip install -r requirements.txt`.
4. Set up the environment variables in `config.py`:
    - `TELEGRAM_BOT`: Your Telegram bot token.
    - `GOOGLE_API_KEY`: Your Google API key for the Translate API.
    - `OPENAI_API_KEY`: Your OpenAI API key.
    - `MESSAGE_LIMIT`: The daily message limit for the bot.
    - `MAXIMUM_CHATS`: The maximum number of group chats the bot can join.
5. Deploy the bot using a server or a cloud platform of your choice.

## Usage

### Adding the bot to a group chat

1. Search for your bot in Telegram using its username.
2. Add the bot to a group chat by selecting the group and clicking on "Add to Group."

### Setting your preferred language

1. Once the bot is added to a group chat, send the following command to set your preferred language: `/setlang [language_code]`. Replace `[language_code]` with the desired language code (e.g., `en` for English, `es` for Spanish, etc.). You can find the supported language codes here: https://cloud.google.com/translate/docs/languages
2. The bot will confirm the language setting and store it in the Firestore database.

### Sending messages

1. To send a message in the group chat, simply type it as you normally would. Mister Said will automatically translate the message based on each user's preferred language.
2. If there are only two participants in the chat (including the bot), Mister Said will use the OpenAI GPT-3.5-turbo API to provide assistance instead of translation.

## Background

Mister Said was created to bridge language barriers in group chat environments, making it easier for users to communicate in their preferred languages. By leveraging the power of the Google Translate API and OpenAI's GPT-3.5-turbo, the bot provides accurate translations and context-aware assistance when needed.

## Support

For questions or assistance regarding Mister Said, please open an issue on the GitHub repository, and we will be happy to help.
