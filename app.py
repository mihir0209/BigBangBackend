from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
from PIL import Image
import io
import base64
from image_processing.enhancer import ImageEnhancer
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import json
import uuid
import re
import urllib.parse
import traceback
from utils.video_processor import VideoProcessor
from utils.summarizer import Summarizer

app = Flask(__name__)
CORS(app)

@app.route('/enhance', methods=['POST'])
def enhance_image():
    try:
        data = request.json
        image_data = data['image']
        method = data.get('method', 'sharpen')
        intensity = float(data.get('intensity', 50))
            
        # Convert base64 to image
        image_data = base64.b64decode(image_data.split(',')[1])
        image = Image.open(io.BytesIO(image_data))
        opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        
        # Apply enhancement using ImageEnhancer
        enhanced = ImageEnhancer.enhance(opencv_image, method, intensity)
        
        # Convert back to PIL Image
        enhanced_image = Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB))
        
        # Save to bytes
        img_byte_arr = io.BytesIO()
        enhanced_image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Convert to base64
        enhanced_base64 = base64.b64encode(img_byte_arr).decode()
        
        return jsonify({
            'status': 'success',
            'image': f'data:image/png;base64,{enhanced_base64}'
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configuration
UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
CACHE_FOLDER = 'cache'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)
os.makedirs(CACHE_FOLDER, exist_ok=True)

# Initialize processors
video_processor = VideoProcessor(UPLOAD_FOLDER, RESULTS_FOLDER)
summarizer = Summarizer()

# Groq API key - to be filled by the user
GROQ_API_KEY = "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"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_video():
    try:
        print("=== New Request Received ===")
        
        # Get request data
        data = request.get_json()
        if not data:
            print("Error: No JSON data in request")
            return jsonify({'error': 'No JSON data provided'}), 400
            
        print(f"Request data: {data}")
        
        page_url = data.get('pageUrl')
        page_title = data.get('pageTitle', 'Unknown Title')
        
        if not page_url:
            print("Error: No page URL provided")
            return jsonify({'error': 'No page URL provided'}), 400
        
        print(f"Processing URL: {page_url}")
        print(f"Page title: {page_title}")
        
        # Extract video ID and platform
        video_info = extract_video_info(page_url)
        
        if not video_info or not video_info.get('video_id'):
            print(f"No supported video found at URL: {page_url}")
            return jsonify({
                'noVideo': True,
                'message': 'No supported video found on this page'
            })
        
        video_id = video_info['video_id']
        platform = video_info['platform']
        video_url = video_info['video_url']
        
        print(f"Detected {platform} video with ID: {video_id}")
        print(f"Video URL: {video_url}")
        
        # Check if we have cached results
        cache_key = f"{platform}_{video_id}"
        cached_result = check_cache(cache_key)
        
        if cached_result:
            print(f"Returning cached result for {cache_key}")
            return jsonify({
                'videoTitle': cached_result.get('title', page_title),
                'videoSource': platform.capitalize(),
                'summary': cached_result.get('summary', ''),
                'transcript': cached_result.get('transcript', '')
            })
        
        # Check if API key is set
        if not GROQ_API_KEY:
            print("Error: GROQ_API_KEY is not set")
            return jsonify({'error': 'API key not configured. Please set GROQ_API_KEY in app.py'}), 500
        
        # Generate a unique ID for this processing job
        job_id = str(uuid.uuid4())
        print(f"Generated job ID: {job_id}")
        
        # Download and process the video
        print("Downloading video...")
        video_path = video_processor.download_video(video_url, job_id)
        print(f"Video downloaded to: {video_path}")
        
        # Extract frames and their text
        print("Extracting frames and text...")
        frames_data = video_processor.extract_frames_and_text(video_path, job_id)
        print(f"Extracted {len(frames_data)} frames")
        
        # Extract audio and transcribe
        print("Extracting and transcribing audio...")
        transcript = video_processor.extract_and_transcribe_audio(
            video_path, 
            job_id, 
            api_key=GROQ_API_KEY
        )
        print(f"Transcription complete: {len(transcript)} characters")
        
        # Save transcript to file
        transcript_path = os.path.join(RESULTS_FOLDER, f"{job_id}_transcript.txt")
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(transcript)
        print(f"Transcript saved to: {transcript_path}")
        
        # Save frames text to file
        frames_text = "\n\n".join([frame["text"] for frame in frames_data if frame["text"]])
        frames_text_path = os.path.join(RESULTS_FOLDER, f"{job_id}_frames_text.txt")
        with open(frames_text_path, 'w', encoding='utf-8') as f:
            f.write(frames_text)
        print(f"Frames text saved to: {frames_text_path}")
        
        # Generate summary using Groq API
        print("Generating summary...")
        summary = summarizer.generate_summary(
            transcript, 
            frames_text, 
            page_title, 
            api_key=GROQ_API_KEY
        )
        print(f"Summary generated: {len(summary)} characters")
        
        # Save summary to file
        summary_path = os.path.join(RESULTS_FOLDER, f"{job_id}_summary.md")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"Summary saved to: {summary_path}")
        
        # Cache the results
        cache_results(cache_key, {
            'title': page_title,
            'platform': platform,
            'summary': summary,
            'transcript': transcript
        })
        print(f"Results cached with key: {cache_key}")
        
        # Return results
        print("Returning results to client")
        return jsonify({
            'videoTitle': page_title,
            'videoSource': platform.capitalize(),
            'summary': summary,
            'transcript': transcript
        })
        
    except Exception as e:
        print("=== ERROR ===")
        print(f"Error processing video: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def extract_video_info(url):
    """Extract video ID and platform from URL"""
    print(f"Extracting video info from: {url}")
    
    youtube_patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            print(f"Matched YouTube video ID: {video_id}")
            return {
                'platform': 'youtube',
                'video_id': video_id,
                'video_url': f'https://www.youtube.com/watch?v={video_id}'
            }
    
    # Vimeo
    vimeo_patterns = [
        r'vimeo\.com\/(\d+)',
        r'vimeo\.com\/channels\/[a-zA-Z0-9]+\/(\d+)',
        r'player\.vimeo\.com\/video\/(\d+)'
    ]
    
    for pattern in vimeo_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            print(f"Matched Vimeo video ID: {video_id}")
            return {
                'platform': 'vimeo',
                'video_id': video_id,
                'video_url': f'https://vimeo.com/{video_id}'
            }
    
    # Dailymotion
    dailymotion_pattern = r'dailymotion\.com\/video\/([a-zA-Z0-9]+)'
    match = re.search(dailymotion_pattern, url)
    if match:
        video_id = match.group(1)
        print(f"Matched Dailymotion video ID: {video_id}")
        return {
            'platform': 'dailymotion',
            'video_id': video_id,
            'video_url': f'https://www.dailymotion.com/video/{video_id}'
        }
    
    # Direct video URL
    if url.endswith(('.mp4', '.webm', '.ogg')):
        # Generate a hash of the URL as the video ID
        import hashlib
        video_id = hashlib.md5(url.encode()).hexdigest()
        print(f"Direct video URL detected, generated ID: {video_id}")
        return {
            'platform': 'direct',
            'video_id': video_id,
            'video_url': url
        }
    
    # If no match found, return None
    print("No video pattern matched")
    return None

def check_cache(cache_key):
    """Check if results are cached for this video"""
    cache_file = os.path.join(CACHE_FOLDER, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            print(f"Cache file found: {cache_file}")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading cache: {e}")
    return None

def cache_results(cache_key, results):
    """Cache results for future use"""
    cache_file = os.path.join(CACHE_FOLDER, f"{cache_key}.json")
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Results cached to: {cache_file}")
    except Exception as e:
        print(f"Error writing cache: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    print("=== Chat Request Received ===")
    try:
        data = request.json
        print(f"Chat request data: {json.dumps(data, indent=2)[:500]}...")
        
        user_message = data.get('message')
        chat_history = data.get('chatHistory', [])
        video_data = data.get('videoData', {})
        
        print(f"User message: {user_message}")
        print(f"Chat history length: {len(chat_history)}")
        print(f"Video data keys: {list(video_data.keys())}")
        
        if not user_message or not video_data:
            print("Error: Missing required data in chat request")
            return jsonify({'error': 'Missing required data'}), 400
        
        # Use the defined API key
        api_key = GROQ_API_KEY
        print(f"Using API key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
        
        if not api_key:
            print("Error: GROQ_API_KEY is not configured")
            return jsonify({'error': 'API key not configured'}), 500
        
        # Create prompt for the chat
        print("Creating chat prompt...")
        prompt = f"""
You are a helpful assistant that can answer questions about a specific video. 
You have access to the video's transcript, summary, and title.

Video Title: {video_data.get('videoTitle', 'Unknown')}

Video Summary:
{video_data.get('summary', 'No summary available')}

Based on the above information, please answer the user's question. 
If you don't know the answer based on the provided information, say so honestly.
"""
        print(f"Prompt created: {len(prompt)} characters")
        
        # Prepare messages for the API
        messages = [
            {
                "role": "system",
                "content": prompt
            }
        ]
        
        # Add chat history
        for message in chat_history:
            messages.append({
                "role": message.get("role", "user"),
                "content": message.get("content", "")
            })
        
        print(f"Total messages prepared: {len(messages)}")
        
        # Call Groq API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama3-70b-8192",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        print(f"Preparing to call Groq API with payload size: {len(json.dumps(payload))} bytes")
        
        try:
            import requests
            print("Sending request to Groq API...")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            print(f"Groq API response status: {response.status_code}")
            
            if response.status_code != 200:
                error_text = response.text
                print(f"Groq API error: {error_text}")
                return jsonify({'error': f'API error: {error_text}'}), 500
            
            print("Parsing Groq API response...")
            result = response.json()
            assistant_response = result["choices"][0]["message"]["content"]
            
            print(f"Assistant response: {assistant_response[:100]}...")
            return jsonify({'response': assistant_response})
        except Exception as e:
            print(f"Exception during Groq API call: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error: {str(e)}'}), 500
    except Exception as e:
        print(f"Unexpected error in chat endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

if __name__ == '__main__':
    if not GROQ_API_KEY:
        print("WARNING: GROQ_API_KEY is not set. Please set it in app.py")
    app.run(debug=True, port=5000)
