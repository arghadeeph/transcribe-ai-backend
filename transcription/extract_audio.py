import subprocess
import os

def extract_audio(input_path, output_path):
    command = [
        "ffmpeg",
        "-i", input_path,
        "-vn",                # no video
        "-acodec", "mp3",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)