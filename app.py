from flask import Flask, request, jsonify, send_file
import requests
import json
import os
import base64
import io
import openai  # New import for OpenAI TTS

app = Flask(__name__, static_url_path='/static')

# OpenRouter API Endpoint and Key
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = "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"

# OpenAI API key for TTS
openai.api_key = "tts-d62fc6e2335fcf98d75b0bac1a1a28df"  # <-- Replace with your TTS key

@app.route('/')
def home():
    return "Smart Blind Stick Flask Server Running final boss"

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image found in request'}), 400

    image = request.files['image']
    
    # Save image temporarily
    static_dir = os.path.join(app.root_path, 'static')
    os.makedirs(static_dir, exist_ok=True)
    image_path = os.path.join(static_dir, "temp.jpg")
    
    try:
        image.save(image_path)
    except Exception as e:
        return jsonify({'error': f"Failed to save image: {str(e)}"}), 500

    # Convert image to base64
    try:
        with open(image_path, "rb") as img_file:
            encoded_image = base64.b64encode(img_file.read()).decode('utf-8')
        image_data_url = f"data:image/jpeg;base64,{encoded_image}"
    except Exception as e:
        return jsonify({'error': f"Failed to encode image: {str(e)}"}), 500

    question = "You are assisting a blind person. Please describe in clear and simple spoken language what is visible in this image. Mention objects, people, obstacles, distance, and anything important that they should be aware of for navigation or safety. Keep the response short and focused."

    # Create payload for LLaMA model
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
            # Extract the text from LLaMA response
            final_answer = ai_response['choices'][0]['message']['content']
            if isinstance(final_answer, list):
                # Sometimes content is returned as a list of dicts
                final_answer_text = " ".join([c.get("text", "") for c in final_answer if c.get("type") == "text"])
            else:
                final_answer_text = str(final_answer)
        else:
            final_answer_text = f"API Error: {response.status_code}, {response.text}"

    except Exception as e:
        final_answer_text = f"Error while processing the image: {str(e)}"

    # --- Convert text to speech using OpenAI TTS ---
    try:
        tts_response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=final_answer_text
    )
    audio_bytes = tts_response.read()  # <-- important: read the binary audio data
except Exception as e:
    return jsonify({'error': f"TTS failed: {str(e)}"}), 500

    # Return the audio file
    return send_file(
        io.BytesIO(audio_bytes),
        mimetype="audio/mpeg",
        download_name="speech.mp3"
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
