import os
import cv2
import base64
import subprocess
import json
import requests
import re
import time
import random
import platform
import threading
import concurrent.futures
from moviepy.editor import VideoFileClip
from .text_extractor import TextExtractor
from .frame_extractor import FrameExtractor
from pytube import YouTube
from urllib.parse import parse_qs, urlparse

class VideoProcessor:
    def __init__(self, upload_folder, results_folder):
        self.upload_folder = upload_folder
        self.results_folder = results_folder
        self.frame_extractor = FrameExtractor()
        self.text_extractor = TextExtractor()
        # Detect if running on Render or local
        self.is_render = 'RENDER' in os.environ or platform.system() != 'Windows'
        # Timeouts for different methods (in seconds)
        self.timeouts = {
            'invidious': 10, 
            'direct_request': 15,
            'pytube': 25,
            'yt_dlp': 40
        }
        
    def download_video(self, video_url, job_id):
        """Download video from URL using multiple methods with fallbacks"""
        output_path = os.path.join(self.upload_folder, f"{job_id}.mp4")
        
        # Create uploads directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # More comprehensive YouTube URL detection
        youtube_patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
        ]
        
        is_youtube_url = False
        video_id = None
        
        for pattern in youtube_patterns:
            match = re.search(pattern, video_url)
            if match:
                is_youtube_url = True
                video_id = match.group(1)
                break
                
        # Explicit check for standard YouTube URL formats
        if video_url.startswith(('https://www.youtube.com/watch?v=', 
                                'https://youtu.be/', 
                                'http://www.youtube.com/watch?v=',
                                'http://youtu.be/',
                                "https://www.youtube.com/shorts/")):
            is_youtube_url = True
            # Extract video ID from URL if not already done
            if not video_id:
                parsed_url = urlparse(video_url)
                if parsed_url.netloc == 'youtu.be':
                    video_id = parsed_url.path.lstrip('/')
                elif 'shorts' in parsed_url.path:
                    video_id = parsed_url.path.split('/')[-1]
                else:
                    query_params = parse_qs(parsed_url.query)
                    video_id = query_params.get('v', [None])[0]
            
        print(f"URL: {video_url}")
        print(f"Is YouTube: {is_youtube_url}")
        print(f"Video ID: {video_id}")
        print(f"Running on Render: {self.is_render}")
        
        # For testing on render, we'll try to directly download from any available source
        # This is an optimization to avoid timeouts by:
        # 1. Trying faster methods first
        # 2. Running methods concurrently when possible
        # 3. Setting timeouts on slow methods
        
        if not is_youtube_url:
            # Non-YouTube video - try direct download or yt-dlp
            try:
                return self._download_with_yt_dlp(video_url, output_path)
            except Exception as e:
                print(f"yt-dlp failed: {e}")
                if video_url.endswith('.mp4'):
                    return self._direct_download(video_url, output_path)
                raise Exception(f"Failed to download non-YouTube video: {e}")

        # For YouTube videos, try to download using multiple methods concurrently
        results = []
        errors = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # First try the invidious approach with timeout
            print("Starting Invidious download attempt...")
            future_invidious = executor.submit(self._try_with_timeout, 
                                              self._download_with_invidious, 
                                              self.timeouts['invidious'],
                                              video_url, output_path, video_id)
            
            # Brief delay before starting other methods to allow invidious to succeed if it's fast
            time.sleep(0.5)
            
            # Then try pytube
            print("Starting pytube download attempt...")
            future_pytube = executor.submit(self._try_with_timeout,
                                          self._download_with_pytube_advanced,
                                          self.timeouts['pytube'],
                                          video_url, output_path, video_id)
            
            # Brief delay before launching yt-dlp
            time.sleep(0.5)
            
            # Finally try yt-dlp (can be slow)
            print("Starting yt-dlp download attempt...")
            future_yt_dlp = executor.submit(self._try_with_timeout,
                                          self._download_with_yt_dlp_advanced,
                                          self.timeouts['yt_dlp'],
                                          video_url, output_path, video_id)
            
            # Wait for the first successful result or until all futures complete
            for future in concurrent.futures.as_completed([future_invidious, future_pytube, future_yt_dlp]):
                try:
                    result = future.result()
                    if result:
                        print(f"Download successful: {result}")
                        # Cancel remaining futures to avoid unnecessary processing
                        for f in [future_invidious, future_pytube, future_yt_dlp]:
                            if not f.done():
                                f.cancel()
                        return result
                except Exception as e:
                    print(f"Download method failed: {str(e)}")
                    errors.append(str(e))
                    continue
        
        # If all concurrent methods failed, try direct request as a last resort
        try:
            print("Trying direct request as last resort...")
            return self._try_with_timeout(self._download_with_direct_request, 
                                         self.timeouts['direct_request'],
                                         video_url, output_path, video_id)
        except Exception as e:
            print(f"Direct request failed: {e}")
            errors.append(str(e))
        
        # Finally, try direct download if it's an MP4
        if video_url.endswith('.mp4'):
            try:
                print("Attempting direct download for .mp4 URL...")
                return self._direct_download(video_url, output_path)
            except Exception as e:
                print(f"Direct .mp4 download failed: {e}")
                errors.append(str(e))
        
        # All methods failed
        raise Exception(f"All download methods failed. Errors: {', '.join(errors)}")
    
    def _try_with_timeout(self, func, timeout, *args, **kwargs):
        """Run a function with a timeout"""
        result = [None]
        error = [None]
        
        def run_func():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                error[0] = e
        
        thread = threading.Thread(target=run_func)
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            print(f"Function {func.__name__} timed out after {timeout} seconds")
            # Let the thread continue to run in the background
            # This is needed because some functions might be writing to the output file
            # but we don't want to wait for them to complete
            return None
        
        if error[0]:
            raise error[0]
        
        return result[0]
        
    def _direct_download(self, url, output_path):
        """Perform a direct download from a URL"""
        print(f"Directly downloading from URL: {url}")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"Direct download complete: {output_path}")
        return output_path
        
    def _download_with_pytube(self, video_url, output_path, video_id=None):
        """Download using pytube"""
        print(f"Downloading YouTube video using pytube: {video_url}")
        
        # Add user-agent to avoid detection
        yt = YouTube(
            video_url,
            use_oauth=False,
            allow_oauth_cache=True
        )
        
        print(f"Video title: {yt.title}")
        
        # Try progressive streams first (audio+video combined)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        
        if not stream:
            # Try adaptive streams if no progressive stream is found
            stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc().first()
        
        if not stream:
            raise Exception("No suitable stream found for this YouTube video.")
        
        print(f"Selected stream: {stream.resolution}, {stream.mime_type}")
        
        # Download the video
        stream.download(output_path=os.path.dirname(output_path), filename=os.path.basename(output_path))
        print(f"Download complete: {output_path}")
        return output_path
    
    def _download_with_pytube_advanced(self, video_url, output_path, video_id=None):
        """Download using pytube with advanced anti-detection measures"""
        print(f"Downloading YouTube video using pytube advanced: {video_url}")
        
        # Rotate user agents to appear like different browsers
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.2365.92",
        ]
        
        user_agent = random.choice(user_agents)
        
        # Use the pytube-related-API
        # When on Render, try to fetch using a more complex approach
        try:
            from pytube import YouTube
            
            # Create a YouTube object with a random user agent
            yt = YouTube(
                url=video_url,
                use_oauth=False,
                allow_oauth_cache=True
            )
            
            # Explicitly set the user agent on the innertube client
            if hasattr(yt, '_innertube_client') and hasattr(yt._innertube_client, '_headers'):
                yt._innertube_client._headers['User-Agent'] = user_agent
            
            # Also set the user agent on the session object
            if hasattr(yt, '_http'):
                yt._http.headers['User-Agent'] = user_agent
            
            print(f"Video title: {yt.title}")
            
            # Add another small delay to mimic human waiting for video info
            time.sleep(random.uniform(0.5, 1.0))
            
            # Try different stream types
            # First try progressive
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
            
            if not stream:
                # Then try adaptive
                stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc().first()
            
            if not stream:
                # Then try any format
                stream = yt.streams.order_by('resolution').desc().first()
            
            if not stream:
                raise Exception("No suitable stream found for this YouTube video.")
            
            print(f"Selected stream: {stream.resolution}, {stream.mime_type}")
            
            # Download the video
            stream.download(output_path=os.path.dirname(output_path), filename=os.path.basename(output_path))
            print(f"Download complete: {output_path}")
            return output_path
        except Exception as e:
            print(f"Advanced pytube download failed: {e}")
            raise
    
    def _download_with_yt_dlp(self, video_url, output_path, video_id=None):
        """Download using yt-dlp with multiple user agents"""
        # Different user agents to try
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
        ]
        
        # Try different user agents
        for user_agent in user_agents:
            try:
                print(f"Using yt-dlp with user agent: {user_agent[:30]}...")
                cmd = [
                    "python", "-m", "yt_dlp",
                    "--user-agent", user_agent, 
                    "--impersonate", "chrome",
                    "--no-check-certificate",
                    "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "-o", output_path,
                    video_url
                ]
                result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=20)
                print(f"yt-dlp download complete: {output_path}")
                return output_path
            except subprocess.TimeoutExpired:
                print("yt-dlp process timed out")
                continue
            except subprocess.CalledProcessError as e:
                print(f"yt-dlp with user agent {user_agent[:15]}... failed: {e}")
                if hasattr(e, 'stderr'):
                    print(f"Error output: {e.stderr}")
                continue
        
        # If all user agents failed
        raise Exception("All yt-dlp download attempts failed")
        
    def _download_with_yt_dlp_advanced(self, video_url, output_path, video_id=None):
        """Download using yt-dlp with advanced anti-detection options"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
        ]
        
        # Browser types to impersonate
        browsers = ["chrome", "firefox", "safari"]
        
        # Try different approaches
        for user_agent in user_agents:
            for browser in browsers:
                try:
                    print(f"Using yt-dlp advanced with {browser} and custom agent...")
                    
                    cmd = [
                        "python", "-m", "yt_dlp",
                        "--user-agent", user_agent,
                        "--impersonate", browser,
                        "--no-check-certificate",
                        "--geo-verification-proxy", "", # Try without geo verification
                        "--add-header", f"Referer:https://www.youtube.com/watch?v={video_id}",
                        "--add-header", "Origin:https://www.youtube.com",
                        "--add-header", "Accept-Language:en-US,en;q=0.9",
                        # Reduce sleeps to speed up the process
                        "--sleep-requests", "0.5",
                        "--sleep-interval", "0.5", 
                        "--max-sleep-interval", "1",
                        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                        "-o", output_path,
                        video_url
                    ]
                    
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=20)
                    print(f"yt-dlp advanced download complete: {output_path}")
                    return output_path
                except subprocess.TimeoutExpired:
                    print(f"yt-dlp process with {browser} timed out")
                    continue
                except subprocess.CalledProcessError as e:
                    print(f"yt-dlp advanced with {browser} failed: {e}")
                    if hasattr(e, 'stderr'):
                        print(f"Error output: {e.stderr}")
                    continue
        
        # If all attempts failed
        raise Exception("All yt-dlp advanced download attempts failed")
    
    def _download_with_direct_request(self, video_url, output_path, video_id):
        """Download via direct API request to YouTube"""
        if not video_id:
            raise Exception("Video ID required for direct request download")
            
        print(f"Attempting direct API request download for video ID: {video_id}")
        
        # Try to get video info using YouTube's own API endpoints
        session = requests.Session()
        
        # Add headers to look like a browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com'
        })
        
        # First get the watch page with a timeout
        response = session.get(f"https://www.youtube.com/watch?v={video_id}", timeout=10)
        
        # Extract the master.m3u8 URL from the page
        patterns = [
            r'"(?:hlsManifestUrl|dashManifestUrl)":"([^"]+)"',
            r'(?:hlsManifestUrl|dashManifestUrl)\":\"([^\"]+)\"'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                manifest_url = matches[0].replace('\\/', '/')
                print(f"Found manifest URL: {manifest_url[:50]}...")
                
                # Get the manifest file with a timeout
                manifest = session.get(manifest_url, timeout=10).text
                
                # Find the highest quality stream URL
                stream_urls = re.findall(r'https://[^\"\']+', manifest)
                if stream_urls:
                    # Take the first URL which is typically the highest quality
                    stream_url = stream_urls[0]
                    print(f"Found stream URL: {stream_url[:50]}...")
                    
                    # Download the stream with a timeout
                    with open(output_path, 'wb') as f:
                        response = session.get(stream_url, stream=True, timeout=10)
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"Direct download complete: {output_path}")
                    return output_path
        
        raise Exception("Could not find video stream URL in YouTube page")
    
    def _download_with_invidious(self, video_url, output_path, video_id):
        """Download using Invidious instances as proxy"""
        if not video_id:
            raise Exception("Video ID required for Invidious download")
            
        # List of public Invidious instances - updated list with more reliable instances
        instances = [
            "https://vid.puffyan.us",
            "https://invidious.snopyta.org",
            "https://invidious.kavin.rocks",
            "https://yewtu.be",
            "https://yt.artemislena.eu",
            "https://invidious.flokinet.to",
            "https://invidious.projectsegfau.lt"
        ]
        
        # Shuffle the list to distribute load and avoid detection patterns
        random.shuffle(instances)
        
        for instance in instances:
            try:
                print(f"Trying Invidious instance: {instance}")
                
                # Get video info from Invidious API with a short timeout
                api_url = f"{instance}/api/v1/videos/{video_id}"
                
                # Add headers to look like a browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'application/json',
                    'Referer': f"{instance}/watch?v={video_id}"
                }
                
                response = requests.get(api_url, headers=headers, timeout=5)
                
                if response.status_code != 200:
                    print(f"Instance {instance} returned status {response.status_code}")
                    continue
                
                video_data = response.json()
                
                # Find the highest quality format
                formats = video_data.get('formatStreams', [])
                if not formats:
                    print(f"No format streams found on {instance}")
                    continue
                
                # Sort by quality (assuming higher resolution = higher quality)
                formats.sort(key=lambda x: int(x.get('quality', '0').replace('p', '')), reverse=True)
                best_format = formats[0]
                
                # Download the video
                url = best_format.get('url')
                if not url:
                    print(f"No URL found in best format on {instance}")
                    continue
                
                print(f"Downloading from {instance}, quality: {best_format.get('quality')}")
                
                # Download with a normal browser-like session and a timeout
                session = requests.Session()
                session.headers.update(headers)
                
                response = session.get(url, stream=True, timeout=10)
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f"Invidious download complete: {output_path}")
                return output_path
            except Exception as e:
                print(f"Invidious instance {instance} failed: {e}")
                continue
        
        raise Exception("All Invidious instances failed")
    
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