from flask import Flask, request, jsonify, send_file
import requests
import json
import os
import io
from gtts import gTTS
from datetime import datetime
import tempfile
import firebase_admin
from firebase_admin import credentials, storage, firestore

# Initialize Flask app
app = Flask(__name__)

# --- API Keys & Config ---
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = os.getenv("OPENROUTER_API_KEY")  # stored in Render Environment Variables
FIREBASE_CRED_PATH = os.getenv("FIREBASE_CONFIG")  # Path or JSON string

# --- Initialize Firebase ---
if not firebase_admin._apps:
    if FIREBASE_CRED_PATH and os.path.exists(FIREBASE_CRED_PATH):
        cred = credentials.Certificate(FIREBASE_CRED_PATH)
    else:
        # Try initializing from JSON string (Render environment variable)
        cred = credentials.Certificate(json.loads(FIREBASE_CRED_PATH))
    firebase_admin.initialize_app(cred, {
        'storageBucket': '<your-project-id>.appspot.com'  # Replace with your Firebase Storage bucket name
    })

db = firestore.client()
bucket = storage.bucket()

# --- Helper Functions ---

def upload_to_firebase(local_path, remote_name):
    """Uploads a file to Firebase Storage and returns the public URL."""
    blob = bucket.blob(remote_name)
    blob.upload_from_filename(local_path)
    blob.make_public()
    return blob.public_url


# --- Routes ---

@app.route('/process', methods=['POST'])
def process_image():
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided'}), 400

        image = request.files['image']
        if image.filename == '':
            return jsonify({'error': 'Empty filename'}), 400

        # Save image temporarily
        temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        image.save(temp_img.name)

        # Upload image to Firebase Storage
        image_name = f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        image_url = upload_to_firebase(temp_img.name, image_name)

        # Send image for AI processing
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": f"Describe this image: {image_url}"}]
        }

        ai_response = requests.post(API_URL, headers=headers, json=payload)
        ai_response.raise_for_status()

        result_text = ai_response.json()["choices"][0]["message"]["content"]

        # Convert text to speech
        tts = gTTS(text=result_text, lang='en')
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(temp_audio.name)

        # Upload audio to Firebase
        audio_name = f"audio/{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        audio_url = upload_to_firebase(temp_audio.name, audio_name)

        # Store record in Firestore
        db.collection('image_analysis').add({
            'timestamp': datetime.now().isoformat(),
            'image_url': image_url,
            'audio_url': audio_url,
            'description': result_text
        })

        # Cleanup
        os.remove(temp_img.name)
        os.remove(temp_audio.name)

        # Return response
        return jsonify({
            'image_url': image_url,
            'audio_url': audio_url,
            'description': result_text
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def home():
    return "Flask AI + Firebase Server is Running ✅"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
