# AI Meeting Intelligence System

> Production-grade conversational intelligence pipeline for extracting actionable insights from meeting audio

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end AI system that transforms raw meeting audio into structured intelligence: transcripts, action items, decisions, and follow-ups. Built with production-grade architecture for scalability and real-time deployment.

## Features

### Audio Processing Pipeline
- **Adaptive Noise Reduction** — noisereduce with stationary/non-stationary detection
- **Voice Activity Detection (VAD)** — Silero VAD for speech segmentation
- **Signal Enhancement** — bandpass filtering, impulse noise removal, mouth noise suppression
- **Format Normalization** — automatic conversion to 16kHz mono WAV

### Transcription & Diarization
- **High-Accuracy Transcription** — AssemblyAI Universal-2 model
- **Speaker Diarization** — automatic speaker labeling and segmentation
- **Timestamp Alignment** — millisecond-precision utterance timing

### Intelligence Extraction
- **Action Item Detection** — identifies commitments with owners and deadlines
- **Decision Tracking** — extracts agreed-upon decisions with context
- **Follow-up Identification** — surfaces deferred topics and open questions
- **Source Attribution** — links every insight back to exact transcript quotes

### Output Generation
- **Markdown Recaps** — human-readable meeting summaries
- **Structured JSON** — machine-readable intelligence for downstream systems
- **Timestamp References** — every item linked to original audio position

## Architecture

```
meeting-intelligence/
├── src/
│   ├── audio/              # Signal processing & VAD
│   │   ├── preprocess.py   # Orchestrator
│   │   ├── vad.py          # Silero VAD integration
│   │   └── filters.py      # DSP filters
│   │
│   ├── transcription/      # Speech-to-text
│   │   ├── transcriber.py  # AssemblyAI client
│   │   └── formatter.py    # Transcript formatting
│   │
│   ├── intelligence/       # NLU extraction
│   │   ├── extractor.py    # LLM-based extraction
│   │   └── prompts.py      # Versioned prompts
│   │
│   ├── output/             # Export layer
│   │   └── recap.py        # Markdown generation
│   │
│   ├── utils/              # Shared utilities
│   │   ├── config.py       # Centralized config
│   │   └── logger.py       # Structured logging
│   │
│   └── main.py             # Pipeline orchestrator
│
├── data/                   # Input audio samples
├── outputs/                # Generated artifacts
└── tests/                  # Unit & integration tests
```

## Installation

### Prerequisites
- Python 3.10+
- ffmpeg (for audio conversion)
- AssemblyAI API key
- Groq API key (for LLM extraction)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/meeting-intelligence.git
cd meeting-intelligence

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (macOS)
brew install ffmpeg

# Configure API keys
cp .env.example .env
# Edit .env and add your API keys
```

### Environment Variables

Create a `.env` file:

```env
ASSEMBLYAI_API_KEY=your_assemblyai_key_here
GROQ_API_KEY=your_groq_key_here
```

## Usage

### Basic Usage

```bash
cd src
python main.py ../data/samples/meeting.mp3 "Sprint Planning"
```

### Skip Preprocessing (if audio is already clean)

```bash
python main.py ../data/samples/meeting.mp3 "Q4 Review" --skip-preprocess
```

### Output

The pipeline generates:
- **Console output** — formatted transcript and recap
- **Markdown file** — `meeting_recap.md` in the same directory as input audio
- **Structured logs** — timestamped processing steps

### Example Output

```markdown
# Meeting Recap: Sprint Planning

## Action Items
- [ ] **Speaker B**: Implement user authentication API — due Friday
  > *"I'll handle the auth endpoints by end of week"*

## Decisions Made
- Use PostgreSQL instead of MongoDB for user data
  > *"We agreed PostgreSQL is better for relational queries"*

## Follow-ups
- Database migration strategy *(owner: Speaker A)*
  Reason: Need to evaluate downtime impact

## Open Questions
- Should we support OAuth2? *(asked by Speaker C)*
```

## Configuration

All parameters are centralized in `src/utils/config.py`:

```python
# Audio preprocessing
SAMPLE_RATE = 16000
VAD_THRESHOLD = 0.4
BANDPASS_LOW = 300
BANDPASS_HIGH = 3400

# Transcription
ASSEMBLYAI_BASE_URL = "https://api.assemblyai.com"

# Intelligence extraction
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_TEMPERATURE = 0.1
```

## Roadmap

### Phase 1: Core Pipeline ✅
- [x] Audio preprocessing with VAD
- [x] Transcription with speaker labels
- [x] Intelligence extraction
- [x] Markdown recap generation

### Phase 2: Quality & Benchmarking (In Progress)
- [ ] Transcript correction with LLM post-processing
- [ ] WER benchmarking against ground truth
- [ ] Multi-model comparison (AssemblyAI vs Whisper)
- [ ] Diarization accuracy metrics


## Benchmark Results

| Model | WER | CER | Time |
|------|------|------|------|
| AssemblyAI | 0.0667 | 0.0449 | 2.31s |
| Whisper Large-v3 | 0.4000 | 0.2135 | 5.84s |



### Phase 3: Real-Time Systems
- [ ] Streaming audio ingestion
- [ ] Incremental transcription
- [ ] Live action item detection
- [ ] WebSocket API for real-time clients

### Phase 4: Production Deployment
- [ ] Docker containerization
- [ ] Kubernetes deployment configs
- [ ] Horizontal scaling with Redis queue
- [ ] Monitoring with Prometheus/Grafana

### Phase 5: Advanced Features
- [ ] Multi-language support
- [ ] Custom vocabulary injection
- [ ] Sentiment analysis per speaker
- [ ] Meeting summary generation
- [ ] Integration with Slack/Teams

## Technical Details

### Audio Preprocessing Pipeline

1. **Format Conversion** — ffmpeg to 16kHz mono WAV
2. **VAD Segmentation** — Silero VAD isolates speech regions
3. **Impulse Noise Removal** — detects and suppresses transient spikes
4. **Spectral Noise Reduction** — noisereduce with adaptive profiling
5. **Bandpass Filtering** — 300-3400 Hz (human voice range)
6. **Mouth Noise Suppression** — energy-based burst detection
7. **Normalization** — peak normalization to -1 dB

### Intelligence Extraction

Uses a structured prompt with Groq's Llama 3.3 70B:
- **Zero-shot extraction** — no fine-tuning required
- **JSON schema enforcement** — guarantees parseable output
- **Source attribution** — every item includes exact transcript quote
- **Precision over recall** — filters vague statements

## Performance

- **Audio preprocessing**: ~2-3x realtime (10min audio → 3-5min processing)
- **Transcription**: ~1x realtime (AssemblyAI API)
- **Intelligence extraction**: ~5-10 seconds per meeting
- **End-to-end**: ~15-20 minutes for 1-hour meeting

## Contributing

Contributions welcome! Areas of interest:
- Benchmark datasets for meeting intelligence
- Alternative transcription backends (Whisper, Deepgram)
- Real-time streaming support
- Diarization improvements

## License

MIT License - see [LICENSE](LICENSE) for details

## Acknowledgments

- [Silero VAD](https://github.com/snakers4/silero-vad) for voice activity detection
- [AssemblyAI](https://www.assemblyai.com/) for transcription API
- [Groq](https://groq.com/) for fast LLM inference
- [noisereduce](https://github.com/timsainb/noisereduce) for spectral noise reduction

---

**Built for production-grade conversational intelligence systems**
