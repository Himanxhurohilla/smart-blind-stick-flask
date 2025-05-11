from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__, static_url_path='/static')

# OpenRouter API Endpoint
API_URL = "https://openrouter.ai/api/v1"
API_KEY = "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"

@app.route('/')
def home():
    return "Smart Blind Stick Flask Server9 Running"

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image found'})

    image = request.files['image']
    image_path = "static/temp.jpg"
    image.save(image_path)

    # Generate Image URL
    image_url = request.host_url + "static/temp.jpg"

    question = "What is in this image?"

    # Send request to Meta Llama 4 Maverick Model
    response = requests.post(
        API_URL,
        headers={
            "Authorization": API_KEY,
            "Content-Type": "application/json"
        },
        data=json.dumps({
            "model": "meta-llama/llama-4-maverick",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        })
    )

    if response.status_code == 200:
        ai_response = response.json()
        final_answer = ai_response['choices'][0]['message']['content']
    else:
        final_answer = "Unable to identify scene"

    return jsonify({'response': final_answer})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
