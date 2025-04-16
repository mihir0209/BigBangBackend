import cv2
import pytesseract
import numpy as np

class TextExtractor:
    def __init__(self):
        # Configure pytesseract path if needed
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pass
    
    def extract_text(self, frame):
        """Extract text from a video frame using OCR"""
        try:
            # Preprocess the image for better OCR results
            preprocessed = self._preprocess_image(frame)
            
            # Perform OCR
            text = pytesseract.image_to_string(preprocessed)
            
            # Clean up the text
            text = self._clean_text(text)
            
            return text
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""
    
    def _preprocess_image(self, image):
        """Preprocess image to improve OCR accuracy"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        
        # Apply dilation and erosion to remove noise
        kernel = np.ones((1, 1), np.uint8)
        img = cv2.dilate(thresh, kernel, iterations=1)
        img = cv2.erode(img, kernel, iterations=1)
        
        # Apply median blur
        img = cv2.medianBlur(img, 3)
        
        # Invert back
        img = 255 - img
        
        return img
    
    def _clean_text(self, text):
        """Clean up extracted text"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Remove common OCR errors or patterns if needed
        
        return text
