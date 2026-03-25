import uuid
import tempfile
import os
import json
import logging

from pydub import AudioSegment
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import StreamingHttpResponse
from django.conf import settings

from .extract_audio import extract_audio
from .utils.job_store import JOB_STORE

import openai
openai.api_key = settings.OPENAI_API_KEY

logging.basicConfig(filename="app.log", level=logging.INFO, filemode="a")
logger = logging.getLogger(__name__)


class UploadV2View(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file uploaded"}, status=400)

        filename = file.name.lower()
        language = request.data.get("language", "en")
        ext = os.path.splitext(filename)[1]

        # Save uploaded file to a temp path
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            temp_path = tmp.name

        # Extract audio track if this is a video file
        video_extensions = {".mp4", ".mov", ".avi", ".mkv"}
        if ext in video_extensions:
            audio_path = f"{temp_path}_{uuid.uuid4()}.mp3"
            extract_audio(temp_path, audio_path)
            os.remove(temp_path)          # drop the raw video immediately
        else:
            audio_path = temp_path

        job_id = str(uuid.uuid4())
        JOB_STORE[job_id] = {"audio_path": audio_path, "language": language}

        return Response({
            "job_id": job_id,
            "stream_url": f"/api/v2/stream?job_id={job_id}",
        })

def ms_to_timestamp(ms: int) -> str:
    """Convert milliseconds to MM:SS string, e.g. 65000 → '01:05'."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def iter_audio_chunks(audio_path: str, chunk_ms: int = 5_000):
    """
    Yield (index, tmp_path) one chunk at a time so the first chunk is ready
    to transcribe almost immediately — no need to export the whole file first.
    """
    logger.info("Splitting audio: %s", audio_path)
    audio = AudioSegment.from_file(audio_path)
    total_ms = len(audio)

    for i, start_ms in enumerate(range(0, total_ms, chunk_ms)):
        end_ms = min(start_ms + chunk_ms, total_ms)
        chunk = audio[start_ms:end_ms]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        chunk.export(tmp.name, format="mp3")
        tmp.close()
        yield i, tmp.name, start_ms, end_ms

def stream_v2(request):
    job_id = request.GET.get("job_id")
    job = JOB_STORE.get(job_id)

    if not job:
        return StreamingHttpResponse("Invalid job_id", status=400)

    audio_path = job["audio_path"]
    language = job["language"]

    # Carry the last sentence of the previous chunk into the next Whisper call
    # so words at boundaries are not dropped or repeated.
    def generate():
        previous_text = ""

        try:
            full_transcript = []
            for i, chunk_path, start_ms, end_ms in iter_audio_chunks(audio_path):
                try:
                    with open(chunk_path, "rb") as f:
                        whisper_response = openai.Audio.transcribe(
                            model="whisper-1",
                            file=f,
                            # Feed prior context so Whisper doesn't restart tone/vocab
                            prompt=previous_text[-224:] if previous_text else None,
                        )

                    text = whisper_response["text"].strip()

                    if not text:
                        continue

                    # Update rolling context (last ~224 chars ≈ Whisper prompt limit)
                    previous_text = text

                    # translated = translate_text(text, language)

                    data = {
                        'index': i,
                        'text': text,
                        # 'translation': translated,
                        'start': ms_to_timestamp(start_ms),
                        'end': ms_to_timestamp(end_ms),
                    }

                    full_transcript.append({
                        "text": text,
                        "start": ms_to_timestamp(start_ms),
                        "end": ms_to_timestamp(end_ms),
                    })

                    yield f"data: {json.dumps(data)}\n\n"

                   

                except Exception as exc:
                    logger.exception("Chunk %d failed", i)
                    yield f"data: {json.dumps({'index': i, 'error': str(exc)})}\n\n"

                finally:
                    # Always clean up the chunk file
                    if os.path.exists(chunk_path):
                        os.remove(chunk_path)

            JOB_STORE[job_id]["transcript"] = full_transcript            

        finally:
            # Clean up original audio & job entry regardless of errors
            if os.path.exists(audio_path):
                os.remove(audio_path)
            # JOB_STORE.pop(job_id, None)
            logger.info("Job %s completed and cleaned up", job_id)

        yield f"data: {json.dumps({'status': 'completed'})}\n\n"

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    # Prevent any proxy/middleware from buffering the stream
    response["X-Accel-Buffering"] = "no"
    response["Cache-Control"] = "no-cache"
    return response

def stream_translate(request):
    
    import json as _json
   
    job_id   = request.GET.get("job_id")
    language = request.GET.get("language")

    # Re-use the stored transcript chunks from JOB_STORE
    job = JOB_STORE.get(job_id)
    if not job or "transcript" not in job:
        return StreamingHttpResponse("Invalid job_id or no transcript", status=400)

    chunks = job["transcript"]  # list of {text, start, end}

    def generate():
        for chunk in chunks:
            text = chunk["text"]
            if not text.strip():
                continue
            translated = translate_text(text, language)
            yield f"data: {json.dumps({'text': translated, 'start': chunk['start'], 'end': chunk['end']})}\n\n"

        yield f"data: {json.dumps({'status': 'completed'})}\n\n"

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    response["X-Accel-Buffering"] = "no"
    response["Cache-Control"] = "no-cache"
    return response

def translate_text(text: str, language: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful translator."},
                    {"role": "user", "content": f"""
                        Translate the following text into {language}:

                        Requirements:
                        - Natural and fluent (not word-for-word)
                        - Preserve meaning and intent
                        - Sound like a native speaker
                        - Do not ask for input
                        - Do not add any extra word or context.

                        Text:
                        {text}
                        """}
        ],
    )
    return response["choices"][0]["message"]["content"].strip()

class TranslateView(APIView):

    def post(self, request):
        job_id = request.data.get("job_id")
        language = request.data.get("language")

        job = JOB_STORE.get(job_id)

        if not job or "transcript" not in job:
            return Response({"error": "Invalid job_id"}, status=400)

        transcript = job["transcript"]

        translated_chunks = []

        full_text = " ".join([c["text"] for c in transcript])

        translated_full = translate_text(full_text, language)

        for chunk in transcript:
            translated = translate_text(chunk["text"], language)

            translated_chunks.append({
                "text": translated,
                "start": chunk["start"],
                "end": chunk["end"]
            })

        return Response({
            "translation": translated_chunks
        })