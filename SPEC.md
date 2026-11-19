# TruthLens: Multimodal Digital Forensics and Deepfake Detection (Solo Build)

> **Coding agents: read this file fully before writing any code.**
> Build ONE stage at a time. Do not start a later stage until the current stage's "Done when" checks pass. Do not add features, packages, or files not described here without asking.

---

## 1. Goal

A working prototype that accepts **image, video, audio, and text** evidence, analyzes each, correlates signals across them, and produces an **explainable forensic report** with flagged locations, evidence references, calibrated confidence levels, and explicit limitations.

**Core principle: build for forensic trust.** A detection score is an indicator, not a verdict. Every report must show:

1. **What** was flagged
2. **Where** (region, frame, timestamp, segment)
3. **Which evidence** supports it
4. **How different signals relate** across modalities
5. **What limitations remain**

Original evidence is never modified. Conclusions are always reviewable by a human.

## 2. Constraints

- **One developer, 24 hours.** Simplicity beats completeness.
- **No model training.** Pretrained models and classical forensics only.
- **Never output a bare "REAL/FAKE" verdict or a naked percentage.**
- **No fake results.** If something cannot run, say so (section 5.2).
- **No auth, no database.** Files and JSON on disk only.
- **Offline-friendly.** Model weights are pre-downloaded; only the LLM call needs internet.

## 3. Architecture (single app, no separate API server)

Streamlit UI calls Python functions directly. No FastAPI unless time is left over (it is not required).

```
Upload -> Ingest (hash, store original) -> Analyzers (per modality)
       -> Cross-modal correlation -> Confidence layer -> Report (HTML + JSON)
```

## 4. Stack (fixed)

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| UI | Streamlit |
| Schemas | Pydantic v2 |
| Image | Pillow, OpenCV, `exifread` (or `piexif`), own ELA, one pretrained HF AI-image detector |
| Video | OpenCV frame sampling, reuse image analyzers, `ffmpeg` to extract audio |
| Audio | librosa, soundfile, matplotlib, one pretrained HF synthetic-speech detector |
| Transcription | `faster-whisper` (small or base model) |
| Text / cross-modal | **Google Gemini API (free tier via AI Studio)**, `google-genai` SDK, a Flash model, strict JSON output. Key in `GEMINI_API_KEY`. All LLM calls go through one function, `truthlens/llm.py: ask_llm()` |
| Report | Jinja2 -> self-contained HTML (images embedded as base64) |
| Hashing | `hashlib.sha256` |

**Dependency rules:** pin every package in `requirements.txt` as soon as it works. Do not add packages without asking. API keys live in `.env` (never committed).

## 5. Data contracts

### 5.1 Finding (the central schema, defined in `truthlens/schemas.py`)

```json
{
  "id": "f_0001",
  "modality": "image",
  "analyzer": "image.ela",
  "indicator": "Inconsistent compression levels",
  "status": "flagged",
  "confidence": "medium",
  "raw_score": 0.64,
  "location": {
    "type": "region",
    "bbox": [120, 80, 200, 150],
    "frame_index": null,
    "start_s": null,
    "end_s": null,
    "detail": null
  },
  "explanation": "A rectangular region around the face compresses differently from the background, which can indicate it was edited after the original save.",
  "limitations": "ELA also produces false positives on re-saved or resized images. Not conclusive on its own.",
  "evidence_refs": ["artifacts/img1_ela_heatmap.png"],
  "source_file_sha256": "ab12...ef"
}
```

| Field | Rules |
|---|---|
| `modality` | `image`, `video`, `audio`, `text`, `cross_modal` |
| `analyzer` | `<modality>.<method>`, e.g. `image.exif`, `image.ela`, `image.ai_detector`, `video.frame_scan`, `audio.synthetic_speech`, `audio.spectral`, `text.contradiction`, `cross.transcript_vs_caption` |
| `status` | `flagged` (suspicious), `clear` (checked, nothing found), `unavailable` (could not run) |
| `confidence` | `low`, `medium`, `high`: belief that *this finding indicates manipulation*. Not a probability |
| `raw_score` | Optional float 0-1 from the model or heuristic. **Uncalibrated. Never display as "% fake"** |
| `location.type` | `region` (bbox in pixels), `frame` (frame_index, optional bbox), `timestamp` (start_s, end_s), `metadata` (detail = field name), `text_span` (detail = quoted span), `file` (whole file) |
| `explanation` | Plain language, 1-3 sentences |
| `limitations` | **Required on every finding**, including `clear` ones |
| `evidence_refs` | Paths relative to the case folder; files must exist |
| `source_file_sha256` | Hash of the original file. Cross-modal findings list related finding IDs in `location.detail` |

### 5.2 Failure behavior (IMPORTANT)

If a model fails to load, a file can't be decoded, or an API call fails, return a Finding with `status: "unavailable"` and the **real error reason in `limitations`**. **Never** return placeholder, random, or hardcoded scores in real code paths. Fake data is allowed only in `stubs.py`, and stub findings must use `"analyzer": "STUB.*"`.

### 5.3 Analyzer interface

```python
def analyze(path: str, case_dir: str, context: dict | None = None) -> list[Finding]:
    """
    path: absolute path to the original file (read-only, never modify)
    case_dir: write artifacts to <case_dir>/artifacts/
    context: optional extras, e.g. {"caption": "...", "claimed_date": "..."}
    Must not raise. Catch exceptions and return an 'unavailable' Finding.
    """
```

Cross-modal: `correlate(findings, inputs, context) -> list[Finding]`

### 5.4 Report JSON (`data/cases/<case_id>/report.json`)

```json
{
  "case_id": "c_20260101_001",
  "created_at": "ISO-8601",
  "inputs": [{"file_id": "...", "filename": "photo.jpg", "media_type": "image", "sha256": "...", "size_bytes": 12345}],
  "context": {"caption": "...", "notes": "..."},
  "findings": [],
  "overall": {
    "level": "low | medium | high | inconclusive",
    "summary": "Plain-language summary.",
    "reasoning": "Why this level was chosen and what would change it.",
    "supporting_findings": ["f_0001"],
    "caveats": ["..."]
  },
  "recommended_human_checks": ["Verify the original source of the image"],
  "analysis_log": [{"time": "ISO-8601", "step": "image.ela", "file": "sha256", "result": "ok | unavailable", "note": "..."}]
}
```

## 6. Repo layout

```
truthlens/
├── SPEC.md
├── requirements.txt
├── .env.example              # GEMINI_API_KEY=, GEMINI_MODEL=
├── app.py                    # Streamlit UI (thin; calls pipeline)
├── truthlens/
│   ├── schemas.py            # Pydantic models (source of truth)
│   ├── llm.py                # ask_llm(prompt) -> str; the ONLY place that calls Gemini
│   ├── storage.py            # case folders, hashing, read-only originals
│   ├── pipeline.py           # runs analyzers, correlation, confidence, report
│   ├── confidence.py         # overall confidence rules
│   ├── stubs.py              # labeled fake findings for early UI work
│   ├── analyzers/
│   │   ├── image.py          # EXIF, ELA, AI-detector
│   │   ├── video.py          # frame sampling + image checks + audio extraction
│   │   ├── audio.py          # synthetic-speech detector + spectral features
│   │   ├── transcribe.py     # Whisper
│   │   ├── text.py           # LLM text/claim analysis
│   │   └── cross_modal.py    # correlation rules
│   └── report/
│       ├── generator.py
│       └── report.html.j2
├── scripts/
│   ├── download_models.py    # pre-fetch all model weights
│   ├── test_llm.py           # confirms the Gemini key, model, and JSON output work
│   └── run_samples.py        # run analyzers on samples/ and print findings
├── samples/                  # demo evidence + README.md with ground truth
├── tests/
│   └── test_schemas.py
└── data/                     # runtime only, gitignored
    └── cases/<case_id>/{originals,artifacts}/
```

## 7. Build stages

Each stage ends with something demoable. Commit after each stage passes its checks. If time runs short, stop at the last completed stage and polish; do not leave a half-built stage in `main`.

### Stage 0: Setup (hours 0-1)
- Repo, virtualenv, `requirements.txt`, `.gitignore` (include `.env`, `data/`, model caches).
- Get a free Gemini key at `aistudio.google.com/app/apikey`, put it in `.env` as `GEMINI_API_KEY`, and set `GEMINI_MODEL` to a current Flash model name (check AI Studio; names change).
- Run `python scripts/test_llm.py` and confirm it passes. Check your real limits at `aistudio.google.com/rate-limit`.
- Pick **specific** HF models for the image detector and the audio detector. Write `scripts/download_models.py` and confirm they load with network disabled.
- Collect the demo samples (section 11).

**Done when:** `python scripts/download_models.py` succeeds and models load offline.

### Stage 1: Skeleton (hours 1-3)
- `schemas.py` (Finding, InputFile, Report), `storage.py` (hash, save original read-only), `stubs.py`.
- `pipeline.py` with `run_case(files, context)` returning a Report using stub findings.
- `app.py`: upload, caption box, Analyze button, findings list with limitations visible.

**Done when:** you can upload a file in Streamlit and see stub findings (clearly labeled STUB) and a downloadable `report.json`.

### Stage 2: Image analysis + report (hours 3-8)
- `analyzers/image.py`: EXIF/metadata inspection, ELA with heatmap artifact, one HF AI-image detector.
- `confidence.py` with the rules in section 8.
- `report/generator.py` + template: full HTML report per section 9.
- Replace stubs with real image findings in the pipeline.

**Done when:** a real photo and an edited photo each produce a report, the edited one flags a region on a heatmap, and every finding has limitations. **You now have a demoable product.**

### Stage 3: Audio (hours 8-13)
- `transcribe.py`: Whisper with segment timestamps, saved as an artifact.
- `analyzers/audio.py`: windowed (3-5 s) synthetic-speech detection, flagged segments with start/end, spectrogram artifact with flagged segments marked, simple spectral checks.
- Add audio to the pipeline, UI, and report.

**Done when:** a real clip and a cloned/synthetic clip give different, explainable results with timestamps, or an honest "inconclusive".

### Stage 4: Text and cross-modal (hours 13-17)
- `truthlens/llm.py`: `ask_llm(prompt, json_mode=True)` wrapping Gemini. Reads `GEMINI_API_KEY` and `GEMINI_MODEL` from the environment, retries once on rate-limit errors, and raises a clear error that callers turn into an `unavailable` Finding.
- `analyzers/text.py`: LLM with strict JSON output (via `ask_llm`); must cite the exact span it reacts to.
- **Privacy:** send only captions, transcripts, and notes to the LLM. Never send the media files. The free Gemini tier may use requests to improve Google products, so do not use sensitive or private evidence in demos.
- `cross_modal.py`, at least these checks:
  1. Transcript vs caption/claim contradictions
  2. EXIF/file timestamps or device vs claimed date/source
  3. Flagged audio segment vs flagged video frames at the same time range (supports or leaves unresolved)
  4. Agreement summary: which signals support each other, which conflict
- Add the cross-modal section to the report.

**Done when:** a mismatched set (e.g. caption contradicts the audio) produces a cross-modal finding that references the related finding IDs.

### Stage 5: Video, minimal (hours 17-20)
- `analyzers/video.py`: sample ~1 frame/sec (cap ~30), run image analyzers on frames, flag worst **timestamps**, save flagged frames as artifacts, extract the audio track and reuse `audio.py`.
- Simple frame-difference spike metric only. No deep temporal model.

**Done when:** a video produces flagged timestamps with frame artifacts and audio findings in the same report.

### Stage 6: Freeze and demo prep (hours 20-24)
- **No new features.** Bug fixes, wording, UI polish.
- Verify the "never fake" rule: grep for hardcoded or random scores outside `stubs.py`.
- Run the full demo end to end from a clean state, offline except the LLM.
- Record a backup screen recording. Write slides. Sleep.

**Cut in this order if behind:** video metrics, extra detectors, PDF export, UI polish. **Never cut:** limitations, evidence references, the working end-to-end flow, honest "unavailable"/"inconclusive" behavior.

## 8. Confidence rules (`confidence.py`)

We do **not** claim statistical calibration. Confidence is a transparent rule-based mapping, and the report states this.

**Per finding:** set by each analyzer from signal strength and the known reliability of the method. Weak signals (missing EXIF, a single AI-detector score) cap at `low` or `medium`.

**Overall:**
- `high`: 3+ flagged findings from at least 2 independent methods, with multi-modality or cross-modal agreement and no strong conflicting evidence
- `medium`: 2 independent flagged methods, or 1 `high` finding supported by another
- `low`: a single flagged finding, or only weak signals
- `inconclusive`: conflicting findings, or most analyzers `unavailable`

Methods sharing the same underlying signal are not independent. The report must list **why** the level was chosen and **what would change it**.

## 9. Report requirements

HTML report sections, in order:
1. Case header: case ID, date, input files with SHA-256
2. Overall assessment: level, summary, reasoning, caveats
3. Flagged evidence table: file, modality, location, indicator, confidence
4. Visual evidence: heatmaps, flagged frames, annotated spectrogram
5. Cross-modal context: which signals support or conflict
6. Per-finding detail: explanation and **limitations**
7. Recommended human checks
8. Analysis log, including `unavailable` steps (never hidden)
9. Footer: "Automated indicators only. Not a final verdict. Requires review by a human investigator."

Self-contained (images as base64) so it opens offline.

## 10. UI requirements (`app.py`)

- Multi-file upload (image, video, audio, text) and an optional caption/claim box
- Analyze button with progress per step
- Overall assessment card, findings grouped by modality, visual evidence, cross-modal section
- Download buttons for report HTML and JSON
- Limitations always visible beside each finding; never a naked score
- `unavailable` findings shown greyed out with the reason

## 11. Demo set (`samples/`, collect by hour 3)

- 1 real unedited photo with intact EXIF
- 1 manipulated image (splice/edit) and 1 fully AI-generated image
- 1 real voice clip and 1 cloned/synthetic voice clip
- 1 short real video, and 1 manipulated one if feasible
- 1 caption that **contradicts** the media and 1 that matches
- `samples/README.md` listing the ground truth for each file, so you can judge your own output honestly

**Demo story (3-4 min):** upload a mismatched set -> pipeline runs -> flagged image region heatmap -> audio segment flagged at a timestamp -> cross-modal contradiction -> open the report showing limitations and recommended human checks. Include one case where the system says **"inconclusive"** to show honest uncertainty.

## 12. Working with the coding agent

**Rules for every prompt**
- Start with: "Read SPEC.md fully. Implement only Stage N. Do not touch files outside this stage."
- One analyzer or one task per prompt.
- After each task: "Run it on `samples/` and show me the actual output."
- If a result looks wrong, ask the agent to **explain it**, not to tune thresholds until it matches the expected answer.
- Commit after every passing stage. If the agent breaks something, roll back rather than patching on top.

**Stage prompts (paste one at a time)**

*Stage 1*
> Read SPEC.md. Implement Stage 1 only: `truthlens/schemas.py` (Pydantic v2 models exactly per section 5), `storage.py`, `stubs.py` (3 findings, analyzer names prefixed `STUB.`), `pipeline.py` with `run_case`, and `app.py` in Streamlit with upload, caption box, Analyze button, findings list showing limitations, and a JSON download. Add `tests/test_schemas.py` validating the stubs. Run the app and confirm it works.

*Stage 2*
> Read SPEC.md. Implement Stage 2 only. First `truthlens/analyzers/image.py` with EXIF inspection and ELA (write ELA with Pillow, save a heatmap to artifacts), following the analyzer interface in 5.3 and the failure behavior in 5.2. Run it on `samples/` and show me the printed findings for a real and an edited image before continuing. Then add the HF AI-image detector, then `confidence.py`, then the HTML report generator per section 9.

*Stage 3*
> Read SPEC.md. Implement Stage 3 only. First `transcribe.py` with faster-whisper, saving a timestamped transcript artifact. Then `analyzers/audio.py` with windowed segment analysis and a spectrogram artifact with flagged segments marked. If a model fails to load, return an `unavailable` Finding with the real error. Test on `samples/` and show me the output before wiring it into the UI and report.

*Stage 4*
> Read SPEC.md. Implement Stage 4 only. First `truthlens/llm.py` with `ask_llm()` using the `google-genai` SDK and a Flash model from `GEMINI_MODEL`; it must be the only code that calls Gemini. Then `analyzers/text.py` using `ask_llm` with strict JSON output that quotes the exact span; handle API failure or rate limits as an `unavailable` Finding with the real error. Run `python scripts/test_llm.py` first to confirm the key works. Then `cross_modal.py` with the four checks in section 7 Stage 4. Test with the contradicting and matching captions in `samples/`.

*Stage 5*
> Read SPEC.md. Implement Stage 5 only. `analyzers/video.py`: sample frames, reuse `analyzers/image.py`, flag worst timestamps with frame artifacts, extract the audio track with ffmpeg and reuse `analyzers/audio.py`. Keep it simple; no temporal deep models.

*Stage 6 (audit)*
> Read SPEC.md. Audit the codebase: find any code path outside `stubs.py` that returns hardcoded, random, or placeholder scores; find any Finding missing `limitations`; find any analyzer that can raise instead of returning `unavailable`. Report what you find and fix only those issues.

## 13. Definition of done

- [ ] Accepts image, video, audio, and text inputs
- [ ] Every analyzer returns schema-valid findings and never crashes the pipeline
- [ ] At least 3 cross-modal checks working
- [ ] Confidence computed by documented rules, with reasons shown
- [ ] Report shows flagged locations, evidence references, cross-modal context, limitations, and the analysis log
- [ ] Originals unmodified and hashed
- [ ] No fake or hardcoded results outside `stubs.py`
- [ ] Runs offline with pre-downloaded models (LLM excepted, with a clear fallback message)
- [ ] Demo rehearsed and a backup recording saved
