# 🔍 TruthLens

**Multimodal digital forensics and deepfake detection with explainable, evidence-linked reports.**

Built for **Innovedge Hackathon 2026** (Problem Statement 04: Multimodal Digital Forensics and Deepfake Detection System).

TruthLens takes image, video, audio, and text evidence, looks for indicators of manipulation, cross-checks signals across media types, and produces a forensic report that shows **what was flagged, where it was found, which evidence supports it, how the signals relate, and what limitations remain.**

> **A detection score is an indicator, not a verdict.** TruthLens never outputs a bare "REAL" or "FAKE". Every finding comes with an explanation, a location, evidence, and limitations, and every report is designed to be reviewed by a human investigator.

---

## Features

| Area | What it does |
|---|---|
| **Image** | Metadata/EXIF inspection, Error Level Analysis (ELA) with heatmap, pretrained AI-image detector |
| **Video** | Frame sampling, per-frame image checks, frame-difference spike detection, flagged timestamps |
| **Audio** | Synthetic-speech detection on time windows, spectral checks, annotated spectrogram, flagged segments |
| **Text** | Whisper transcription, LLM claim and contradiction analysis that quotes the exact span |
| **Cross-modal** | Transcript vs. caption, metadata vs. claimed date/source, audio vs. video timing, agreement summary |
| **Confidence** | Rule-based Low / Medium / High / Inconclusive levels with written reasoning |
| **Report** | Self-contained HTML plus JSON, with SHA-256 hashes, evidence references, and an analysis log |

## Why you can trust the output

- **Original evidence is never modified.** Uploads are hashed (SHA-256) and stored read-only. Analysis writes only to a separate artifacts folder.
- **No fake results.** If a model fails to load or an API call fails, the finding is marked **unavailable** with the real reason. Nothing is silently replaced by a placeholder score.
- **Limitations on every finding.** The schema requires them.
- **Honest uncertainty.** Conflicting or weak evidence produces an **Inconclusive** result instead of a forced guess.
- **Confidence is rule-based, not statistically calibrated.** The rules are documented in [`product.md`](product.md) and implemented in `truthlens/confidence.py`.

## Quick start

**Requirements:** Python 3.11, [ffmpeg](https://ffmpeg.org/download.html) installed and on your PATH.

```bash
# 1. Clone and set up
git clone <repo-url>
cd truthlens
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Download model weights once (the app then runs offline)
python scripts/download_models.py

# 3. Configure the LLM key (free Gemini key: https://aistudio.google.com/app/apikey)
cp .env.example .env               # then edit .env and add your key
python scripts/test_llm.py         # optional: confirm the key works

# 4. Run the app
streamlit run app.py
```

Streamlit opens at `http://localhost:8501`.

## Usage

1. **Upload** one or more files: images, video, audio, or text. Optionally add a caption, claimed date, or notes about the evidence.
2. Click **Analyze** and watch the per-step progress.
3. **Review** findings grouped by media type. Each shows its location, confidence, explanation, evidence, and limitations.
4. Check the **cross-modal** section to see where signals from different media support or contradict each other.
5. **Download** the report as HTML (opens offline) or JSON.

### Try it with the sample set

Evidence files with known ground truth are in [`samples/`](samples/). See `samples/README.md` for what each file is, so you can compare TruthLens output against the truth.

To run the analyzers from the command line without the UI:

```bash
python scripts/run_samples.py
```

## Configuration

Settings go in `.env` (never commit this file):

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Free Google Gemini API key from [AI Studio](https://aistudio.google.com/app/apikey) |
| `GEMINI_MODEL` | Gemini Flash model name to use (check AI Studio for current names) |

The free tier needs no credit card. Your project's live rate limits are shown at `aistudio.google.com/rate-limit`.

If the LLM is unreachable or the key is missing, text and cross-modal LLM checks are reported as **unavailable**. Image, video, and audio analysis still run locally.

## How it works

```
Upload ──► Ingest (hash, store read-only)
              │
              ▼
        Per-modality analyzers ──► Findings (one shared schema)
              │
              ▼
        Cross-modal correlation
              │
              ▼
        Confidence layer (rule-based)
              │
              ▼
        Report: HTML + JSON
```

Every analyzer returns findings in the same structure: modality, indicator, status, confidence, location, explanation, limitations, evidence references, and the source file hash. The schema is defined in `truthlens/schemas.py`.

## Project structure

```
app.py                      Streamlit UI
truthlens/
├── schemas.py              Finding and Report models
├── storage.py              Hashing and read-only evidence storage
├── pipeline.py             Orchestrates analysis end to end
├── confidence.py           Overall confidence rules
├── llm.py                  Single wrapper around the Gemini API
├── analyzers/
│   ├── image.py            EXIF, ELA, AI-image detector
│   ├── video.py            Frame sampling and frame checks
│   ├── audio.py            Synthetic-speech and spectral analysis
│   ├── transcribe.py       Whisper transcription
│   ├── text.py             LLM text and claim analysis
│   └── cross_modal.py      Cross-media correlation rules
└── report/                 HTML report generator and template
scripts/                    download_models.py, run_samples.py, test_llm.py
samples/                    Demo evidence with ground truth
tests/                      Schema validation tests
```

## Tech stack

Python 3.11 · Streamlit · Pydantic v2 · Pillow · OpenCV · librosa · faster-whisper · Hugging Face pretrained detectors · Jinja2 · Google Gemini API, free tier (text and cross-modal reasoning)

No models were trained for this project. All detectors are pretrained and used as-is.

## Limitations

TruthLens is a hackathon prototype. Please read these before relying on any result:

- Pretrained detectors can miss new generators and voice-cloning tools, and can produce false positives.
- ELA can flag images that were only re-saved or resized.
- Missing EXIF metadata is weak evidence, since social platforms strip it.
- Audio detection degrades with compression, phone recordings, and noise.
- Video analysis is simple (sampled frames and frame differences), not a deep temporal model.
- LLM output can misread context, so findings quote the exact span for human checking.
- The test set is small and does not support accuracy claims.
- Only text (captions, transcripts, notes) is sent to Google Gemini; media files are never uploaded. On the free tier, Google may use requests to improve its products, so do not analyze sensitive or private evidence with it. All other analysis runs locally.

The full, current list is in [`product.md`](product.md).

## Documentation

| File | Purpose |
|---|---|
| [`product.md`](product.md) | Feature checklist mapped to the problem statement, methodology, and judge verification checklist |
| [`SPEC.md`](SPEC.md) | Build specification and staged development plan |
| [`samples/README.md`](samples/README.md) | Demo evidence and ground truth |

## Responsible use

TruthLens produces **automated indicators only**. It is not a final verdict and is not a substitute for a qualified human investigator. Do not use its output as sole evidence to accuse, penalize, or make legal decisions about any person.

## License

`<choose a license, e.g. MIT, or remove this section>`

## Author

`<your name>` · Innovedge Hackathon 2026