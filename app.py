from flask import Flask, request, jsonify
import requests
import json
import os
import base64

app = Flask(__name__, static_url_path='/static')

# OpenRouter API Endpoint and Key
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = "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"

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

    question = "You are assisting a blind person. Please describe in clear and simple spoken language what is visible in this image. Mention objects, people, obstacles, distance, and anything important that they should be aware of for navigation or safety.keep the response short and focused"

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

        print("API Response Status Code:", response.status_code)
        print("API Response Text:", response.text)

        if response.status_code == 200:
            ai_response = response.json()
            final_answer = ai_response['choices'][0]['message']['content']
        else:
            final_answer = f"API Error: {response.status_code}, {response.text}"

    except Exception as e:
        final_answer = f"Error while processing the image: {str(e)}"

    return jsonify({'response': final_answer})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
