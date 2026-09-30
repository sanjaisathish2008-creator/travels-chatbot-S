import os
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import (
    CHATBOT_TITLE,
    SYSTEM_PROMPT,
    GEMINI_MODEL,
)

app = Flask(__name__)

MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CONTENT_LENGTH = 4000


def validate_history(history):
    """Validate and sanitize browser-supplied conversation history."""
    if history is None:
        return []

    if not isinstance(history, list):
        raise ValueError("Conversation history must be a list.")

    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]

    validated = []

    for item in history:
        if not isinstance(item, dict):
            raise ValueError("Invalid conversation history item.")

        role = item.get("role")
        content = item.get("content")

        if role not in {"user", "assistant"}:
            raise ValueError("Invalid conversation role.")

        if not isinstance(content, str):
            raise ValueError("Conversation content must be text.")

        content = content.strip()

        if not content:
            raise ValueError("Conversation content cannot be empty.")

        if len(content) > MAX_HISTORY_CONTENT_LENGTH:
            raise ValueError("Conversation content is too long.")

        validated.append({"role": role, "content": content})

    return validated


def build_contents(history, message):
    """Convert validated browser history into Gemini conversation contents."""
    contents = []

    for item in history:
        contents.append(
            types.Content(
                role="user" if item["role"] == "user" else "model",
                parts=[types.Part.from_text(text=item["content"])],
            )
        )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        )
    )

    return contents


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", chatbot_title=CHATBOT_TITLE)


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON request."}), 400

        message = data.get("message")
        history = data.get("history", [])

        if not isinstance(message, str):
            return jsonify({"error": "Message must be text."}), 400

        message = message.strip()

        if not message:
            return jsonify({"error": "Message cannot be empty."}), 400

        if len(message) > MAX_MESSAGE_LENGTH:
            return jsonify({"error": "Message is too long."}), 400

        try:
            validated_history = validate_history(history)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "The chatbot service is not configured yet."}), 500

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=build_contents(validated_history, message),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
                max_output_tokens=1200,
            ),
        )

        reply = getattr(response, "text", None)

        if not isinstance(reply, str) or not reply.strip():
            return jsonify({"error": "The chatbot could not generate a response."}), 502

        return jsonify({"reply": reply.strip()}), 200

    except Exception:
        # Never expose server details, SDK errors, prompts, or credentials.
        return jsonify({"error": "Sorry, something went wrong while generating the response."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
