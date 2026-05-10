import os
from dotenv import load_dotenv

load_dotenv()

# API
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# AssemblyAI
ASSEMBLYAI_BASE_URL = "https://api.assemblyai.com"

# Groq
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE = 0.1

# Audio preprocessing
SAMPLE_RATE = 16000
VAD_THRESHOLD = 0.4
VAD_MIN_SPEECH_MS = 200
VAD_MIN_SILENCE_MS = 300
VAD_SPEECH_PAD_MS = 100
BANDPASS_LOW = 300
BANDPASS_HIGH = 3400
NOISE_PROP_DECREASE = 0.85

# Paths
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
