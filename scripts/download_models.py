from transformers import pipeline

print("Image detector...")
pipeline("image-classification", model="Modotte/AIRealNet")
print("Audio detector...")
pipeline("audio-classification", model="MelodyMachine/Deepfake-audio-detection")
print("Whisper speech-to-text...")
pipeline("automatic-speech-recognition", model="openai/whisper-base")
print("All models downloaded.")