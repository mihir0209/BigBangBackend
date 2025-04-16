import cv2
import numpy as np

class FrameExtractor:
    def __init__(self, max_frames=30):
        self.max_frames = max_frames
    
    def extract_key_frames(self, video_path):
        """Extract key frames from video using scene detection"""
        cap = cv2.VideoCapture(video_path)
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        
        # If video is very short, just extract frames at regular intervals
        if duration < 30:
            return self._extract_uniform_frames(cap, fps, frame_count)
        
        # For longer videos, use scene detection
        return self._extract_scene_change_frames(cap, fps, frame_count)
    
    def _extract_uniform_frames(self, cap, fps, frame_count):
        """Extract frames at uniform intervals"""
        frames = []
        interval = max(1, frame_count // self.max_frames)
        
        for i in range(0, frame_count, interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break
                
            timestamp = i / fps
            frames.append((frame, timestamp))
            
            if len(frames) >= self.max_frames:
                break
                
        cap.release()
        return frames
    
    def _extract_scene_change_frames(self, cap, fps, frame_count):
        """Extract frames based on scene changes"""
        frames = []
        prev_frame = None
        frame_index = 0
        
        # Parameters for scene detection
        min_scene_change = 30.0  # Minimum threshold for scene change
        frame_skip = max(1, int(fps))  # Skip frames for efficiency
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_index += 1
            
            # Skip frames for efficiency
            if frame_index % frame_skip != 0 and frame_index != 1:
                continue
                
            # Convert to grayscale for comparison
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            if prev_frame is not None:
                # Calculate difference between current and previous frame
                diff = cv2.absdiff(gray, prev_frame)
                non_zero_count = np.count_nonzero(diff)
                score = non_zero_count * 100.0 / diff.size
                
                # If significant change detected, save the frame
                if score > min_scene_change:
                    timestamp = frame_index / fps
                    frames.append((frame, timestamp))
                    
                    if len(frames) >= self.max_frames:
                        break
            else:
                # Always include the first frame
                timestamp = frame_index / fps
                frames.append((frame, timestamp))
            
            prev_frame = gray
            
        cap.release()
        
        # If we didn't get enough frames, fall back to uniform extraction
        if len(frames) < 5:
            cap = cv2.VideoCapture(video_path)
            frames = self._extract_uniform_frames(cap, fps, frame_count)
            
        return frames
