from flask import Flask, request, jsonify
import requests
import json
import os
import base64
import uuid
from gtts import gTTS
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
import gc  # <-- for memory cleanup

app = Flask(__name__, static_url_path='/static')

API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = os.getenv("OPENROUTER_API_KEY")

firebase_json = os.getenv("FIREBASE_CONFIG")
cred = credentials.Certificate(json.loads(firebase_json))
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smartstick-df0c6-default-rtdb.firebaseio.com/'
})

@app.route('/')
def home():
    return "Smart Blind Stick Flask Server (RAW Binary Upload Enabled)"

@app.route('/upload', methods=['POST'])
def upload_image():
    # --- get raw binary bytes from ESP32 ---
    if not request.data:
        return jsonify({'error': 'No image binary received'}), 400

    static_dir = os.path.join(app.root_path, 'static')
    os.makedirs(static_dir, exist_ok=True)

    image_filename = f"temp_{uuid.uuid4().hex}.jpg"
    image_path = os.path.join(static_dir, image_filename)

    try:
        with open(image_path, "wb") as f:
            f.write(request.data)
    except Exception as e:
        return jsonify({'error': f"Failed to save image: {str(e)}"}), 500

    # --- Convert to Base64 ---
    try:
        with open(image_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{encoded_image}"
    except Exception as e:
        return jsonify({'error': f"Failed to encode: {str(e)}"}), 500

    question = ("You are assisting a blind person. Describe the surroundings clearly and briefly.")

    payload = {
        "model": "meta-llama/llama-4-maverick",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": image_data_url}}
            ]
        }]
    }

    try:
        response = requests.post(API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            data=json.dumps(payload)
        )
        if response.status_code == 200:
            ai_response = response.json()
            final_answer = ai_response['choices'][0]['message']['content']
        else:
            final_answer = f"API Error {response.status_code}"
    except Exception as e:
        final_answer = f"AI Error: {str(e)}"

    # --- Delete temp image (prevents memory leak) ---
    try:
        os.remove(image_path)
        gc.collect()
    except:
        pass

    # --- TTS Generation ---
    try:
        tts_filename = f"tts_{uuid.uuid4().hex}.mp3"
        tts_filepath = os.path.join(static_dir, tts_filename)
        gTTS(text=final_answer, lang='en').save(tts_filepath)
        audio_url = f"https://{request.host}/static/{tts_filename}"
    except Exception:
        audio_url = None

    # --- Save record to Firebase ---
    try:
        ref = db.reference('image_history')
        ref.push({
            "text_output": final_answer,
            "timestamp": datetime.utcnow().isoformat()
        })
    except:
        pass

    return jsonify({'response': final_answer, 'audio_url': audio_url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
