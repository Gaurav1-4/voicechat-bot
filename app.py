import os
import json
import re
from flask import Flask, request, jsonify, render_template, send_file
from groq import Groq
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Initialize Groq Client
client = None
if os.environ.get("GROQ_API_KEY"):
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    except Exception as e:
        print(f"Warning: Failed to initialize Groq Client. {e}")

# Load textbook contents
try:
    with open('books_content.json', 'r', encoding='utf-8') as f:
        books_content = json.load(f)
        textbook_context = f"Flamingo Book Text:\n{books_content.get('Flamingo', '')}\n\nVistas Book Text:\n{books_content.get('Vistas', '')}"
except Exception as e:
    print("Warning: books_content.json not found. Run pdf_extractor.py first.")
    textbook_context = ""

system_prompt_template = """You are EduVoice AI, a helpful voice assistant for Class 12 students.
Your Goal is to help Class 12 students by answering their questions.

CRITICAL INSTRUCTION FOR BREVITY: Keep your answers VERY short and conversational, no more than 2-4 sentences max! Do not write huge paragraphs. A voice bot must be quick and to the point.

CRITICAL INSTRUCTION: You MUST always reply using ONLY the English alphabet (Roman script). If the user asks a question in Hindi or "Hinglish", you must reply using English words or Hinglish but ONLY using English letters. Do NOT output any Devanagari or Hindi script.

Every loop you must follow these steps in your thought process and response:
1. Listen to the user's question.
2. Detect subject (usually English Core Class 12).
3. Find chapter (identify which chapter from Flamingo or Vistas they are talking about).
4. Think step by step about the answer based on the provided textbook text.
5. Give a simple explanation.
6. Give formula if needed (for English, this might just be a literary device or key theme format).
7. Give example.
8. Ask: "Do you want another explanation?" at the end.
9. Improve your answer if the user indicates they were confused previously.
10. Never stop until user says Exit.

Class 12 English Syllabus Knowledge:
- Flamingo Prose: 
  Chapter 1: The Last Lesson
  Chapter 2: Lost Spring
  Chapter 3: Deep Water
  Chapter 4: The Rattrap
  Chapter 5: Indigo
  Chapter 6: Poets and Pancakes
  Chapter 7: The Interview
  Chapter 8: Going Places
- Flamingo Poems: 
  1. My Mother at Sixty-six
  2. Keeping Quiet
  3. A Thing of Beauty
  4. A Roadside Stand
  5. Aunt Jennifer's Tigers
- Vistas: 
  Chapter 1: The Third Level
  Chapter 2: The Tiger King
  Chapter 3: Journey to the end of the Earth
  Chapter 4: The Enemy
  Chapter 5: On the Face of It
  Chapter 6: Memories of Childhood

Textbook Content Context (Use this to answer detailed questions):
{context}
"""

def get_relevant_context(query, text, max_chars=4000):
    words = [w for w in re.findall(r'\w+', query.lower()) if len(w) > 4 or w.isdigit()]
    if not words:
        return text[:max_chars]
        
    best_chunk = text[:max_chars]
    max_score = -1
    
    chunk_size = 2000
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size]
        score = sum(1 for w in words if w in chunk.lower())
        if score > max_score:
            max_score = score
            best_chunk = chunk
            
    return best_chunk

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    if not client:
        return jsonify({'error': 'Groq API Key is not set or invalid.'}), 500

    try:
        user_text = request.form.get('text', '').strip()

        if not user_text:
            if 'audio' not in request.files:
                return jsonify({'error': 'No audio file or text provided'}), 400

            audio_file = request.files['audio']
            ext = audio_file.filename.split('.')[-1] if '.' in audio_file.filename else 'webm'
            
            import uuid
            req_id = str(uuid.uuid4())
            raw_audio_path = f'/tmp/temp_audio_{req_id}.{ext}'
            
            audio_file.save(raw_audio_path)

            file_size = os.path.getsize(raw_audio_path)
            print(f"Received audio file {raw_audio_path} of size {file_size} bytes.")

            if file_size == 0:
                return jsonify({'error': 'Audio file is empty.'}), 400
            
            # Transcribe audio using Whisper Large v3 directly from the raw webm file
            prompt_text = "Class 12 English, CBSE, Flamingo, Vistas, The Last Lesson, Lost Spring, Deep Water, The Rattrap, Indigo, Poets and Pancakes, The Interview, Going Places, My Mother at Sixty-six, Keeping Quiet, A Thing of Beauty, A Roadside Stand, Aunt Jennifer's Tigers, The Third Level, The Tiger King, Journey to the end of the Earth, The Enemy, On the Face of It, Memories of Childhood."
            with open(raw_audio_path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                  file=("audio.webm", file.read()),
                  model="whisper-large-v3",
                  prompt=prompt_text
                )
            
            user_text = transcription.text
            if not user_text.strip():
                 return jsonify({'error': 'Could not hear any speech.'}), 400

        print(f"User asked: {user_text}", flush=True)

        # Get relevant context
        relevant_context = get_relevant_context(user_text, textbook_context)
        system_prompt = system_prompt_template.replace("{context}", relevant_context)

        # Get response from Llama 3
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            model="llama-3.1-8b-instant",
            temperature=0.3,
        )
        
        answer_text = chat_completion.choices[0].message.content
        
        # Generate Audio from the text
        if 'req_id' not in locals():
            import uuid
            req_id = str(uuid.uuid4())
            
        output_audio = f'/tmp/response_{req_id}.mp3'
        temp_text_file = f'/tmp/temp_answer_{req_id}.txt'
        
        with open(temp_text_file, "w", encoding="utf-8") as f:
            f.write(answer_text)
            
        voice_pref = request.form.get('voice', 'female')
        voice_id = 'en-IN-PrabhatNeural' if voice_pref == 'male' else 'en-IN-NeerjaNeural'
            
        import subprocess
        import sys
        # Use edge_tts via python module to generate the audio file (avoids PATH issues)
        subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', voice_id, '-f', temp_text_file, '--write-media', output_audio], check=True)
        
        # Return the audio file directly as a binary response, along with headers for the text
        response = send_file(output_audio, mimetype="audio/mpeg", as_attachment=False)
        response.headers['X-User-Text'] = user_text.encode('utf-8').decode('latin-1') # Ensure safe headers
        response.headers['X-Answer-Text'] = answer_text.encode('utf-8').decode('latin-1')
        
        return response

    except Exception as e:
        print(f"Error: {e}", flush=True)
        return jsonify({'error': str(e)}), 500
    finally:
        # Cleanup temporary files
        for var_name in ['raw_audio_path', 'temp_text_file', 'output_audio']:
            if var_name in locals() and os.path.exists(locals()[var_name]):
                try:
                    os.remove(locals()[var_name])
                except:
                    pass

if __name__ == '__main__':
    app.run(debug=True, port=5001)
