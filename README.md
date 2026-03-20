# Transcribe AI – Backend

AI-powered transcription and translation API built with Django REST Framework.
This service processes audio/video files, generates transcripts using Whisper, and translates them using LLM APIs.

---

## 🚀 Features

* Audio & video transcription
* Multi-language translation
* FFmpeg-based audio extraction from video
* REST API (Django DRF)
* OpenAI integration (Whisper + GPT)
* File upload support

---

## 🛠 Tech Stack

* Python
* Django
* Django REST Framework
* OpenAI API
* FFmpeg

---

## 📡 API Endpoint

### POST `/api/transcribe/`

**Request (form-data):**

* `file`: audio/video file
* `language`: target language (e.g. en, hi, bn)

**Response:**

```json
{
  "transcript": "Hello world",
  "translated_text": "नमस्ते दुनिया"
}
```

---

## ⚙️ Setup

```bash
git clone https://github.com/your-username/transcribe-ai-backend.git
cd transcribe-ai-backend

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

## 🔑 Environment Variables

Create a `.env` file:

```
OPENAI_API_KEY=your_api_key
```

---

## ▶️ Run Server

```bash
python manage.py runserver
```

---

## ⚠️ Requirements

* Python 3.9+
* FFmpeg installed on system

---

## 📌 Notes

* Supports audio: mp3, wav, m4a
* Supports video: mp4, mov (via audio extraction)
* For large files, async processing is recommended (future enhancement)

---

## 📄 License

MIT License
