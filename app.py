from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__, static_url_path='/static')

# OpenRouter API Endpoint
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = "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"

@app.route('/')
def home():
    return "Smart Blind Stick Flasnk Servnner Running"

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image found in request'}), 400

    image = request.files['image']
    
    # Ensure static directory exists
    static_dir = os.path.join(app.root_path, 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    image_path = os.path.join(static_dir, "temp.jpg")
    
    try:
        image.save(image_path)
    except Exception as e:
        return jsonify({'error': f"Failed to save image: {str(e)}"}), 500

    # Generate Image URL
    image_url = request.host_url + "static/temp.jpg"
    question = "What is in this image?"

    try:
        # Send request to Meta Llama 4 Maverick Model
        response = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {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}",  # Ensure "Bearer" prefix
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

        # Debugging: Log the response from OpenRouter API
        print("API Response Status Code:", response.status_code)
        print("API Response Content-Type:", response.headers.get('Content-Type'))
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
