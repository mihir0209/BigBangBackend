import os
import cv2
import base64
import subprocess
import json
import requests
from moviepy.editor import VideoFileClip
from .text_extractor import TextExtractor
from .frame_extractor import FrameExtractor

class VideoProcessor:
    def __init__(self, upload_folder, results_folder):
        self.upload_folder = upload_folder
        self.results_folder = results_folder
        self.frame_extractor = FrameExtractor()
        self.text_extractor = TextExtractor()
        
    def download_video(self, video_url, job_id):
        """Download video from URL using yt-dlp for various platforms"""
        output_path = os.path.join(self.upload_folder, f"{job_id}.mp4")
        
        try:
            subprocess.run([
                "python", "-m", "yt_dlp",
                "--impersonate", "chrome",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "-o", f"uploads\\{job_id}.mp4",
                video_url
            ], check=True)
            return f"uploads\\{job_id}.mp4"
        except Exception as e:
            print(f"yt-dlp failed: {e}")
            
            # Fallback to direct download for direct video URLs
            if video_url.endswith('.mp4'):
                response = requests.get(video_url, stream=True)
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return output_path
            
            raise Exception(f"Failed to download video: {e}")
    
    def extract_frames_and_text(self, video_path, job_id):
        """Extract frames from video and perform OCR on them"""
        frames = self.frame_extractor.extract_key_frames(video_path)
        
        results = []
        for i, (frame, timestamp) in enumerate(frames):
            # Convert frame to base64 for sending to frontend
            _, buffer = cv2.imencode('.jpg', frame)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Extract text from frame
            text = self.text_extractor.extract_text(frame)
            
            results.append({
                "frame_id": i,
                "timestamp": timestamp,
                "image_base64": img_base64,
                "text": text
            })
            
        # Save results to JSON file
        results_path = os.path.join(self.results_folder, f"{job_id}_frames.json")
        with open(results_path, 'w') as f:
            # Save without the base64 images to keep file size reasonable
            json.dump([{k: v for k, v in item.items() if k != 'image_base64'} 
                      for item in results], f)
            
        return results
    
    def extract_and_transcribe_audio(self, video_path, job_id, api_key, language='en'):
        """Extract audio from video and transcribe it using Groq's Whisper API"""
        # Extract audio using moviepy
        audio_path = os.path.join(self.upload_folder, f"{job_id}.mp3")
        video = VideoFileClip(video_path)
        if video.audio is None:
            print("No audio stream detected in video. Skipping transcription.")
            return ""  # or return {} if you prefer a JSON object

        video.audio.write_audiofile(audio_path)
        
        # Prepare multipart form data for upload
        files = {
            'file': ('audio.mp3', open(audio_path, 'rb'), 'audio/mpeg')
        }
        
        # Call Groq API for transcription
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        # Prepare additional form data
        data = {
            'model': 'whisper-large-v3',
            'language': language,
            'response_format': 'json'
        }
        
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data
            )
            
            # Raise an exception for bad responses
            response.raise_for_status()
            
            # Parse the JSON response
            transcript_data = response.json()
            transcript = transcript_data.get('text', '')
            
            
            return transcript
        
        except requests.RequestException as e:
            # More detailed error handling
            print(f"Transcription API error: {e}")
            print(f"Response content: {response.text}")
            raise Exception(f"Transcription failed: {e}")
        except Exception as e:
            print(f"Unexpected error during transcription: {e}")
            raise