import requests
import json

class Summarizer:
    def __init__(self):
        pass
    
    def generate_summary(self, transcript, frames_text, video_title, api_key):
        """Generate a summary of the video using Groq API"""
        if not api_key:
            return "API key not provided. Please add your Groq API key to use this feature."
        
        # Prepare the prompt for the AI
        prompt = self._create_summary_prompt(transcript, frames_text, video_title)
        
        # Call Groq API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama3-70b-8192",  # Using Llama 3 70B model
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates detailed, structured summaries of videos based on their transcript and visual content. Your summaries are concise, well-organized, and formatted in Markdown."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 2048
        }
        
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                return f"Error generating summary: {response.text}"
                
            result = response.json()
            summary = result["choices"][0]["message"]["content"]
            
            return summary
        except Exception as e:
            return f"Error calling Groq API: {str(e)}"
    
    def _create_summary_prompt(self, transcript, frames_text, video_title):
        """Create a prompt for the AI to generate a summary"""
        prompt = f"""
I need you to create a detailed, structured summary of a video titled "{video_title}".

I'll provide you with:
1. The transcript of the video's audio
2. Text extracted from key frames of the video

Please analyze this information and create a comprehensive summary with the following sections:
- **Summary**: A brief 2-3 sentence overview of the video content
- **Main Points**: Bullet points of the key ideas or arguments presented
- **Key Insights**: The most important takeaways or conclusions
- **Timeline**: A brief chronological breakdown of the video's content (if applicable)
- **Reference Links**: Suggest 3-5 relevant online resources (articles, documentation, tutorials) that would be helpful for someone interested in this topic. For each reference, provide a title and a brief description of why it's relevant.

Format your response in Markdown with clear headings and bullet points. Keep the summary concise and focused on the most important information.

Here's the transcript:
{transcript[:4000] if len(transcript) > 4000 else transcript}

Here's the text extracted from key frames:
{frames_text[:2000] if len(frames_text) > 2000 else frames_text}
"""
        return prompt
