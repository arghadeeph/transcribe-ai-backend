
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
import openai
from django.conf import settings
import tempfile
from .extract_audio import extract_audio
import os

openai.api_key = settings.OPENAI_API_KEY

class TranscribeView(APIView):

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
       
        file = request.FILES.get('file')
        filename = file.name.lower()
        language = request.data.get('language', 'en')

        if not file:
            return Response({"error": "No file uploaded"}, status=400 )
        
        try:
            #Transcription by Wishper
            # Save temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=filename) as temp_file:
                for chunk in file.chunks():
                    temp_file.write(chunk)
                temp_path = temp_file.name

            # Check if video
            video_extensions = ['.mp4', '.mov', '.avi', '.mkv']

            if any(filename.endswith(ext) for ext in video_extensions):
                audio_path = temp_path + ".mp3"
                extract_audio(temp_path, audio_path)
            else:
                audio_path = temp_path

            # Send to Whisper
            with open(audio_path, "rb") as audio_file:
                transcript_response = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json"
                )

            transcription_text = transcript_response.text
            segments = getattr(transcript_response, "segments", [])

            filtired_segments = []
            for segment in segments:
                filtired_segments.append({
                    'start': self.format_time(segment.start),
                    'end': self.format_time(segment.end),
                    'text': segment.text.strip(),
                })

            # Cleanup
            os.remove(temp_path)
            if audio_path != temp_path:
                os.remove(audio_path)

            #Translation by gpt4
            translation = openai.responses.create(
                model='gpt-4.1-mini',
                input = f"""
                        Translate the following text into {language}.

                        Requirements:
                        - Natural and fluent (not word-for-word)
                        - Preserve meaning and intent
                        - Sound like a native speaker
                        - Keep it simple and clear
                        - Maintain the original tone (formal/informal as appropriate)

                        Text:
                        {transcription_text}
                        """

                )
            transleted_text = translation.output_text

            return Response({
                 "meta": {
                    "file_name": file.name,
                    "file_size": file.size,
                    "file_type": filename.split('.')[-1],
                    "uploaded_by": str(request.user) if request.user.is_authenticated else "anonymous",
                    "language": language,
                    "processing_time": "optional (you can calculate)"
                },
                "transcripted_text": {
                    "full_text": transcription_text,
                    "segments": filtired_segments
                },
                "translated_text":{
                    "translation": transleted_text
                } 
            })
        
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    def format_time(self, seconds):
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02}:{secs:02}"
