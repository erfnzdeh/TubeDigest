import os
from openai import OpenAI

class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def generate_summary(self, transcript: str) -> str:
        """Generate a summary using OpenAI's API."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates concise, informative summaries of YouTube video transcripts."},
                    {"role": "user", "content": f"Please summarize the following transcript in 3-4 paragraphs, highlighting the main points and key takeaways:\n\n{transcript}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Error generating summary" 