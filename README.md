# Mac AI Assistant

A beginner-friendly local Flask app for macOS. It accepts typed commands and browser voice input, classifies intent using Groq (first) and Mistral (fallback), and opens supported apps, websites, folders, and files.

## Features
- Text commands in a browser.
- Voice-to-text using browser speech recognition.
- Groq intent classification with Mistral fallback.
- Opens macOS applications using `open -a`.
- Opens common websites and standard folders.
- No AI-generated shell commands are executed.

## Requirements
- macOS
- Python 3.10 or newer (tested design target: Python 3.12)
- Groq API key and/or Mistral API key
- Chrome or Safari for the local web interface (Chrome is recommended for voice input)

## Setup on Mac

1. Open this folder in VS Code.
2. Open VS Code Terminal: **Terminal > New Terminal**.
3. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install packages:

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. Create your private environment file:

   ```bash
   cp .env.example .env
   ```

6. Open `.env` and paste your API keys. You can use both keys. If Groq fails, the app tries Mistral. At least one key is required.

7. Start the app:

   ```bash
   python app.py
   ```

8. Open this address in your browser:

   `http://127.0.0.1:5000`

## Example commands
- `Open Safari`
- `Open Calculator`
- `Open Visual Studio Code`
- `Open YouTube`
- `Open Downloads`
- `Search the web for beginner Python projects`

## Important notes
- The app only performs the supported actions in `app.py`; it does not run arbitrary terminal commands.
- `open_file` searches for a matching file directly inside Desktop, Documents, and Downloads.
- Voice recognition depends on browser support and microphone permission. If voice does not work, use the text box.
- Keep `.env` private. Do not commit API keys to GitHub.

## API references
- Groq: https://console.groq.com/docs/text-chat
- Mistral: https://docs.mistral.ai/inference/conversations/chat-completion
