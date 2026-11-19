from transformers import pipeline
from faster_whisper import WhisperModel

print("Image detector...")
pipeline("image-classification", model="Modotte/AIRealNet")
print("Audio detector...")
pipeline("audio-classification", model="MelodyMachine/Deepfake-audio-detection")
print("Whisper base...")
WhisperModel("base")
print("All models downloaded.")
