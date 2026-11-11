import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from groq import Groq

load_dotenv()
app = Flask(__name__)

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

SYSTEM_PROMPT = """
You classify commands for a safe macOS desktop assistant.
Return ONLY one valid JSON object with these keys:
{"action":"open_app|open_website|open_folder|open_file|search_web|youtube_search|recommend_channels|unknown",
 "target":"short target name or URL or search phrase",
 "message":"short friendly explanation"}

Rules:
- Never return shell commands, scripts, or terminal commands.
- "open Safari", "launch calculator", "start VS Code" => open_app.
- "open YouTube", "go to github.com" => open_website.
- "open Downloads", "show my Documents folder" => open_folder.
- "find/open my notes.txt" => open_file.
- "search the web for ..." => search_web.
- "find videos about Python on YouTube" => youtube_search.
- "search YouTube for AI agents" => youtube_search.
- "recommend AI channels" => recommend_channels.
- "suggest programming YouTube channels" => recommend_channels.
- For youtube_search, target should contain the video search topic only.
- For recommend_channels, target should identify the topic, such as AI, Python, or programming.
- If the request is unclear or asks for an unsupported action => unknown.
- For websites, target should be a domain or URL when possible.
- Do not claim an action has happened.
"""

def ask_groq(command):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is missing")
    client = Groq(api_key=key)
    result = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": command},
        ],
        temperature=0,
        max_completion_tokens=180,
    )
    return result.choices[0].message.content, "Groq"

def ask_mistral(command):
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY is missing")
    response = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": MISTRAL_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": command},
            ],
            "temperature": 0,
            "max_tokens": 180,
        },
        timeout=25,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"], "Mistral"

def classify(command):
    errors = []
    # Groq is tried first; Mistral is used if Groq is unavailable or fails.
    for provider in (ask_groq, ask_mistral):
        try:
            raw, provider_name = provider(command)
            raw = raw.strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
            data = json.loads(raw)
            allowed = {
    "open_app",
    "open_website",
    "open_folder",
    "open_file",
    "search_web",
    "youtube_search",
    "recommend_channels",
    "unknown"
}
            if data.get("action") not in allowed:
                raise ValueError("AI returned an unsupported action")
            data["target"] = str(data.get("target", "")).strip()
            data["message"] = str(data.get("message", "")).strip()
            data["provider"] = provider_name
            return data
        except Exception as exc:
            errors.append(f"{provider.__name__}: {exc}")
    raise RuntimeError("Both AI providers failed. " + " | ".join(errors))

WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "whatsapp": "https://web.whatsapp.com",
    "linkedin": "https://www.linkedin.com",
    "stackoverflow": "https://stackoverflow.com",
}

FOLDERS = {
    "home": Path.home(),
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "applications": Path("/Applications"),
    "pictures": Path.home() / "Pictures",
    "music": Path.home() / "Music",
    "movies": Path.home() / "Movies",
}

def open_with_macos(args):
    subprocess.run(["open"] + args, check=True, timeout=10)

def execute_action(data):
    action = data["action"]
    target = data["target"]
    if action == "youtube_search":
        if not target:
            raise ValueError("What video would you like to find?")
        url = "https://www.youtube.com/results?search_query=" + quote_plus(target)
        open_with_macos([url])
        return f"Searching YouTube for {target}."

    if action == "recommend_channels":
        topic = target.lower()

        if "python" in topic:
            channels = [
                "Corey Schafer",
                "Tech With Tim",
                "freeCodeCamp",
                "Programming with Mosh"
            ]
        elif "program" in topic:
            channels = [
                "freeCodeCamp",
                "Programming with Mosh",
                "Traversy Media",
                "CS50"
            ]
        else:
            channels = [
                "3Blue1Brown",
                "StatQuest",
                "Two Minute Papers",
                "IBM Technology",
                "DeepLearning.AI"
            ]

        return "Here are some recommended channels: " + ", ".join(channels)

    if action == "open_app":
        # Passing a list to subprocess avoids shell execution.
        if not target or len(target) > 100 or "/" in target or "\n" in target:
            raise ValueError("Please provide a valid application name.")
        open_with_macos(["-a", target])
        return f"Opening {target}."

    if action == "open_website":
        if not target:
            raise ValueError("I could not identify the website.")
        cleaned = target.lower().strip()
        url = WEBSITES.get(cleaned)
        if not url:
            candidate = target.strip()
            if not candidate.startswith(("http://", "https://")):
                candidate = "https://" + candidate
            parsed = urlparse(candidate)
            if not parsed.netloc or "." not in parsed.netloc or parsed.scheme not in ("http", "https"):
                raise ValueError("I could not identify a valid website.")
            url = candidate
        open_with_macos([url])
        return f"Opening {url}."

    if action == "search_web":
        if not target:
            raise ValueError("What would you like me to search for?")
        url = "https://www.google.com/search?q=" + quote_plus(target)
        open_with_macos([url])
        return f"Searching the web for: {target}"

    if action == "open_folder":
        key = target.lower().strip().replace("my ", "")
        folder = FOLDERS.get(key)
        if folder is None:
            raise ValueError("For now, I can open Home, Desktop, Downloads, Documents, Applications, Pictures, Music, and Movies.")
        if not folder.exists():
            raise ValueError(f"The {target} folder does not exist.")
        open_with_macos([str(folder)])
        return f"Opening {target} folder."

    if action == "open_file":
        filename = Path(target).name
        if not filename or filename != target.strip() or len(filename) > 150:
            raise ValueError("Please give me a simple file name, such as notes.pdf.")
        search_locations = [Path.home() / name for name in ("Desktop", "Documents", "Downloads")]
        matches = []
        for folder in search_locations:
            if folder.exists():
                matches.extend(p for p in folder.glob(filename) if p.is_file())
        if not matches:
            raise ValueError(f"I couldn't find {filename} directly inside Desktop, Documents, or Downloads.")
        open_with_macos([str(matches[0])])
        return f"Opening {matches[0].name}."

    return data.get("message") or "I couldn't understand that command. Try: open Safari, open YouTube, or open Downloads."

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/command")
def command():
    payload = request.get_json(silent=True) or {}
    user_command = str(payload.get("command", "")).strip()
    if not user_command:
        return jsonify({"ok": False, "message": "Please type or speak a command."}), 400
    if len(user_command) > 300:
        return jsonify({"ok": False, "message": "Please keep the command under 300 characters."}), 400
    try:
        result = classify(user_command)
        message = execute_action(result)
        return jsonify({
            "ok": True,
            "message": message,
            "provider": result["provider"],
            "action": result["action"],
        })
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500

if __name__ == "__main__":
    print("Mac AI Assistant is starting...")
    print("Open http://127.0.0.1:5000 in Chrome or Safari.")
    app.run(host="127.0.0.1", port=5000, debug=False)
