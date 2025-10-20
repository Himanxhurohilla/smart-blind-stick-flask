from flask import Flask, request, jsonify
import requests
import json
import os
import base64
import uuid
from gtts import gTTS
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db  # Use db for Realtime Database

app = Flask(__name__, static_url_path='/static')

# --- OpenRouter API ---
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- Firebase Initialization ---
firebase_json = os.getenv("FIREBASE_CONFIG")
if not firebase_json:
    raise ValueError("FIREBASE_CONFIG environment variable is not set")

cred = credentials.Certificate(json.loads(firebase_json))

# Initialize Realtime Database (replace with your Realtime DB URL)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smartstick-df0c6-default-rtdb.firebaseio.com/'
})

# --- Home Route ---
@app.route('/')
def home():
    return "Smart Blind Stick Flask Server Running with TTS and Realtime Database Integration"

# --- Upload Route ---
@app.route('/upload', methods=['POST'])
def upload_image():
    # --- Check for image ---
    if 'image' not in request.files:
        return jsonify({'error': 'No image found in request'}), 400

    image = request.files['image']

    # --- Save uploaded image temporarily ---
    static_dir = os.path.join(app.root_path, 'static')
    os.makedirs(static_dir, exist_ok=True)
    image_path = os.path.join(static_dir, f"temp_{uuid.uuid4().hex}.jpg")

    try:
        image.save(image_path)
    except Exception as e:
        return jsonify({'error': f"Failed to save image: {str(e)}"}), 500

    # --- Convert image to Base64 for OpenRouter ---
    try:
        with open(image_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{encoded_image}"
    except Exception as e:
        return jsonify({'error': f"Failed to encode image: {str(e)}"}), 500

    # --- AI prompt ---
    question = (
        "You are assisting a blind person. Please describe in clear and simple spoken language "
        "what is visible in this image. Mention objects, people, obstacles, distance, and "
        "anything important that they should be aware of for navigation or safety. "
        "Keep the response short and focused."
    )

    # --- OpenRouter Payload ---
    payload = {
        "model": "meta-llama/llama-4-maverick",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image_data_url}}
                ]
            }
        ]
    }

    # --- Call AI model ---
    try:
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            data=json.dumps(payload)
        )

        if response.status_code == 200:
            ai_response = response.json()
            final_answer = ai_response['choices'][0]['message']['content']
        else:
            final_answer = f"API Error: {response.status_code}, {response.text}"

    except Exception as e:
        final_answer = f"Error while processing the image: {str(e)}"

    # --- Convert AI text response to speech using gTTS ---
    try:
        tts_filename = f"tts_{uuid.uuid4().hex}.mp3"
        tts_filepath = os.path.join(static_dir, tts_filename)

        tts = gTTS(text=final_answer, lang='en')
        tts.save(tts_filepath)

        audio_url = f"https://{request.host}/static/{tts_filename}"
    except Exception as e:
        audio_url = None
        print("TTS Error:", str(e))

    # --- Prepare record for Realtime Database ---
    record = {
        "text_output": final_answer,
        "timestamp": datetime.utcnow().isoformat()  # store as ISO string
    }

    # --- Save to Realtime Database ---
    try:
        ref = db.reference('image_history')  # root node for history
        ref.push(record)
        print("Saved record to Realtime Database")
    except Exception as e:
        print(f"Error saving to Realtime Database: {str(e)}")

    # --- Return both text + audio link ---
    return jsonify({
        'response': final_answer,
        'audio_url': audio_url
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
