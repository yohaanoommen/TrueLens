# TruthLens: Product Overview and Feature Verification

**Problem Statement 04: Multimodal Digital Forensics and Deepfake Detection System**
Domain: Digital Forensics & Cybersecurity | Challenge Area: Multimodal Media Authenticity Analysis | Expected Outcome: Explainable forensic report

**Event:** Innovedge Hackathon 2026 (Innovation and Entrepreneurship Development Club)
**Team / Builder:** `<your name>`
**Repository:** `<repo link>`
**Demo video (backup):** `<link>`

> **How to use this file.** Section 3 maps every requirement in the problem statement to a feature, the code that implements it, and a way to verify it. The **Status** column is updated as features are completed. Anything not marked ✅ is not claimed as working. Section 9 lists known limitations.

**Status legend:** ✅ working and verified | 🟡 partial | ⬜ not built | ❌ cut (reason given)

---

## 1. What TruthLens does

TruthLens is a forensic analysis platform for investigators. It accepts **image, video, audio, and text** evidence, examines each for indicators of manipulation, correlates signals across the different media, and generates an **explainable forensic report**.

It is built around one principle from the problem statement: **a detection score is an indicator, not a final verdict.** TruthLens never outputs a bare "REAL" or "FAKE". Every finding shows:

| Question | How the report answers it |
|---|---|
| What was flagged? | Indicator name and plain-language explanation |
| Where was it found? | Image region, video frame/timestamp, audio segment, metadata field, or text span |
| Which evidence supports it? | Linked artifacts (heatmaps, frames, spectrograms, transcripts) and the SHA-256 of the source file |
| How do different signals relate? | A cross-modal section showing which findings support or conflict with each other |
| What limitations remain? | A mandatory limitations statement on every finding, plus recommended human checks |

Original evidence is hashed on upload and never modified. All conclusions are designed to be reviewed by a human investigator.

## 2. Quick start for judges

```bash
# 1. Install
git clone <repo link> && cd truthlens
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Pre-download model weights (one-time; app then runs offline)
python scripts/download_models.py

# 3. Configure the free Gemini key (only needed for text/cross-modal reasoning)
#    Get one at https://aistudio.google.com/app/apikey
cp .env.example .env     # then add GEMINI_API_KEY
python scripts/test_llm.py   # optional: confirm the key works

# 4. Run
streamlit run app.py
```

**Fastest way to evaluate:** open the app, upload the files from `samples/` (ground truth in `samples/README.md`), click **Analyze**, then open the report.

If the LLM is unreachable, text and cross-modal LLM checks show as **"unavailable"** with the reason. The rest of the system still runs.

## 3. Requirement traceability matrix

Each row comes from the problem statement. "Verify" tells a judge exactly how to check it.

### 3.1 Core capabilities (Section 03)

| # | Capability from problem statement | TruthLens feature | Implemented in | How to verify | Status |
|---|---|---|---|---|---|
| 1 | **Image authenticity analysis**: signs of editing, compositing, synthetic generation, metadata inconsistencies | EXIF/metadata inspection, Error Level Analysis with heatmap, pretrained AI-image detector | `truthlens/analyzers/image.py` | Upload `samples/manipulated/` image; report shows flagged region + heatmap and metadata findings | ⬜ |
| 2 | **Video forensics**: frames and temporal consistency, suspicious visual changes | Frame sampling, image checks per frame, frame-difference spike detection, flagged timestamps | `truthlens/analyzers/video.py` | Upload sample video; report lists flagged timestamps with frame images | ⬜ |
| 3 | **Audio and voice analysis**: synthetic or cloned speech, unusual audio characteristics | Windowed synthetic-speech detection, spectral checks, annotated spectrogram, flagged segments with start/end times | `truthlens/analyzers/audio.py` | Upload real vs. cloned clip; compare segments and spectrograms | ⬜ |
| 4 | **Text and context analysis**: compare captions/transcripts to supplied media and evidence | Whisper transcription + LLM claim and contradiction analysis that quotes the exact span | `truthlens/analyzers/transcribe.py`, `text.py` | Upload media with a contradicting caption; report quotes the conflicting span | ⬜ |
| 5 | **Cross-modal correlation**: compare image, video, audio, text signals for mismatches or patterns | Rule-based correlation: transcript vs. caption, metadata vs. claimed date/source, audio vs. video timing, agreement summary | `truthlens/analyzers/cross_modal.py` | Upload the mismatched sample set; "Cross-modal context" section shows linked finding IDs | ⬜ |
| 6 | **Manipulation indicators**: identify and categorize suspicious frames, audio segments, metadata observations | Every finding carries a category (`analyzer`), location type, and explanation | `truthlens/schemas.py` | Inspect `report.json`; each finding has `analyzer`, `location`, `explanation` | ⬜ |
| 7 | **Confidence and uncertainty**: calibrated levels, limitations, alternative explanations | Rule-based Low/Medium/High/Inconclusive levels, written reasoning, per-finding limitations, "what would change this" | `truthlens/confidence.py` | Open report "Overall assessment" and any finding's limitations | ⬜ |
| 8 | **Forensic report and traceability**: structured report with evidence references, flagged locations, detected indicators, analysis history | Self-contained HTML + JSON report with analysis log and SHA-256 hashes | `truthlens/report/` | Download report; check evidence refs, hashes, analysis log | ⬜ |

### 3.2 Suggested analysis workflow (Section 04)

| Step | Requirement | TruthLens implementation | Status |
|---|---|---|---|
| 1. Ingest | Upload media and related context | Multi-file upload (image/video/audio/text) plus optional caption, claimed date, and notes; files hashed and stored read-only | ⬜ |
| 2. Analyze | Examine each supported media type | Per-modality analyzers run independently; failures are isolated | ⬜ |
| 3. Correlate | Compare signals across sources | Cross-modal correlation step | ⬜ |
| 4. Review | Inspect flags, evidence, uncertainty | Results view shows findings grouped by modality with limitations always visible | ⬜ |
| 5. Report | Export findings with traceable references | HTML and JSON download | ⬜ |

### 3.3 What the forensic report shows (Section 05)

| Required element | Where it appears in the report | Status |
|---|---|---|
| **Flagged evidence**: suspicious region, frame, timestamp, or audio segment | "Flagged evidence" table (location column) | ⬜ |
| **Indicator**: the observed signal and why it was flagged | Per-finding explanation | ⬜ |
| **Cross-modal context**: related evidence from other media or sources | "Cross-modal context" section | ⬜ |
| **Confidence**: calibrated score with limitations and uncertainty | Per-finding confidence + overall level with reasoning | ⬜ |
| **Source trace**: input file and evidence reference for review | SHA-256, filename, and artifact links on every finding | ⬜ |
| **Summary**: findings, caveats, recommended human checks | "Overall assessment" and "Recommended human checks" | ⬜ |

### 3.4 Expected deliverable (Section 06)

| Requirement | Status |
|---|---|
| Working prototype that accepts supported image, video, and text/audio inputs | ⬜ |
| Generates a structured forensic report | ⬜ |
| Demonstrates detection indicators | ⬜ |
| Demonstrates cross-modal checks | ⬜ |
| Shows confidence levels | ⬜ |
| Shows evidence references | ⬜ |
| States clear limitations | ⬜ |

### 3.5 What a strong solution shows (Section 07)

| Criterion | How TruthLens addresses it | Status |
|---|---|---|
| Useful analysis across multiple media types | Image, video, audio, text analyzers in one pipeline | ⬜ |
| Explainable, evidence-linked findings | Every finding has an explanation and linked artifacts | ⬜ |
| Meaningful cross-modal correlation | Four documented correlation checks | ⬜ |
| Calibrated confidence and honest uncertainty | Rule-based levels, `inconclusive` outcome, no bare scores | ⬜ |
| Clear reporting, usability, responsible handling of evidence | Self-contained report, hashed read-only originals, human-review footer | ⬜ |

### 3.6 "Build for forensic trust" principle

| Principle | How it is enforced | Status |
|---|---|---|
| Show what was flagged | Indicator + explanation on every finding | ⬜ |
| Show where it was found | Typed location (region, frame, timestamp, segment, metadata, text span) | ⬜ |
| Show which evidence supports it | `evidence_refs` to artifacts that exist on disk | ⬜ |
| Show how signals relate | Cross-modal findings reference related finding IDs | ⬜ |
| Show what limitations remain | `limitations` field is required by the schema | ⬜ |
| Preserve original evidence | Originals saved read-only and named by SHA-256 | ⬜ |
| Keep conclusions reviewable by a human | No verdicts; footer and "recommended human checks" in every report | ⬜ |

## 4. How TruthLens works

```
Upload (image / video / audio / text + context)
   │
   ▼
Ingest: SHA-256 hash, store original read-only
   │
   ▼
Per-modality analyzers ──► Findings (common schema)
   │   image: EXIF · ELA · AI-image detector
   │   video: frame sampling · frame-difference spikes · audio extraction
   │   audio: synthetic-speech detector · spectral checks · Whisper transcript
   │   text:  LLM claim / contradiction analysis (cites exact span)
   ▼
Cross-modal correlation ──► Cross-modal findings
   ▼
Confidence layer (rule-based) ──► Low / Medium / High / Inconclusive + reasoning
   ▼
Report: HTML (self-contained) + JSON, with analysis log
```

### Finding schema (summary)

Every analyzer returns findings in one structure, so the report can treat all media the same way.

| Field | Meaning |
|---|---|
| `modality` | image, video, audio, text, or cross_modal |
| `analyzer` | Specific method, e.g. `image.ela` |
| `indicator` | What was observed |
| `status` | `flagged`, `clear`, or `unavailable` |
| `confidence` | low, medium, or high (belief that the finding indicates manipulation) |
| `location` | Region box, frame index, time range, metadata field, or text span |
| `explanation` | Plain-language reason it matters |
| `limitations` | What could make this wrong (required on every finding) |
| `evidence_refs` | Heatmaps, frames, spectrograms, transcripts |
| `source_file_sha256` | Hash of the original file |

## 5. Confidence methodology

TruthLens does **not** claim statistical calibration, because there is no labeled evaluation set large enough to support it. Instead it uses transparent rules a reviewer can inspect in `truthlens/confidence.py`.

| Overall level | Rule |
|---|---|
| **High** | 3+ flagged findings from at least 2 independent methods, with multi-modality or cross-modal agreement and no strong conflicting evidence |
| **Medium** | 2 independent flagged methods, or 1 high finding supported by another |
| **Low** | A single flagged finding, or only weak signals |
| **Inconclusive** | Conflicting findings, or most analyzers unavailable |

- Methods that rely on the same underlying signal are not counted as independent.
- Weak signals (e.g. missing EXIF, a single AI-detector score) are capped at low or medium.
- Every report states why the level was chosen and what additional evidence would change it.
- Raw model scores are stored for transparency but are never shown as "% fake".

## 6. Responsible handling of evidence

- **Integrity:** every upload is hashed (SHA-256) and the original is stored read-only; analysis writes only to a separate artifacts folder.
- **Traceability:** each finding links to its source file hash and to the artifact that supports it. The report includes an analysis log of every step, including failures.
- **Honest failure:** if a model fails to load or an API call fails, the finding is marked **unavailable** with the real reason. The system never substitutes placeholder or random results.
- **No automated verdicts:** reports end with a notice that results are indicators requiring human review.
- **Privacy:** analysis of models and files runs locally; only text sent to the LLM leaves the machine (see Section 9).

## 7. Demo evidence

Sample files and their **ground truth** are listed in `samples/README.md`, so judges can compare TruthLens output against what is actually true.

| Sample | Ground truth | What TruthLens should show |
|---|---|---|
| `samples/real/photo.jpg` | Unedited, EXIF intact | Few or no flags; findings marked clear |
| `samples/manipulated/edited.jpg` | Edited region | Flagged region with ELA heatmap |
| `samples/manipulated/ai_image.png` | AI-generated | Detector flag with limitations noted |
| `samples/real/voice.wav` | Real recording | Mostly clear segments |
| `samples/manipulated/cloned_voice.wav` | Synthetic speech | Flagged segments with timestamps |
| `samples/manipulated/video.mp4` | Manipulated segment | Flagged timestamps and frames |
| `samples/context/matching_caption.txt` | Matches media | No contradiction found |
| `samples/context/contradicting_caption.txt` | Contradicts media | Cross-modal contradiction with quoted span |

> Update this table with the real file names and observed results before submission.

### Suggested 3-4 minute walkthrough

1. Upload a mismatched evidence set (media plus a contradicting caption).
2. Watch the per-step progress as each analyzer runs.
3. Open the flagged image region and its ELA heatmap.
4. Show the flagged audio segment on the annotated spectrogram.
5. Show the cross-modal finding linking the contradiction to the related findings.
6. Open the report: overall level and reasoning, limitations, recommended human checks, analysis log.
7. Run a case that ends **Inconclusive** to show honest uncertainty.

## 8. Technology

| Layer | Technology |
|---|---|
| Language / UI | Python 3.11, Streamlit |
| Schemas | Pydantic v2 |
| Image | Pillow, OpenCV, exifread, custom ELA, pretrained Hugging Face AI-image detector (`<model name>`) |
| Video | OpenCV, ffmpeg |
| Audio | librosa, soundfile, matplotlib, pretrained Hugging Face synthetic-speech detector (`<model name>`) |
| Transcription | faster-whisper |
| Text / cross-modal | Google Gemini API (free tier, Flash model: `<model name>`) with strict JSON output, called through a single wrapper (`truthlens/llm.py`) |
| Report | Jinja2, self-contained HTML |

No models were trained for this project. All detectors are pretrained and used as-is.

## 9. Known limitations (stated honestly)

> Edit this list to reflect what you actually observed during testing.

- **Detectors are not proof.** Pretrained AI-image and synthetic-speech detectors generalize poorly to generators and voice-cloning tools they were not trained on, and can produce false positives and false negatives.
- **ELA false positives.** Re-saved, resized, or heavily compressed images can show inconsistencies without being manipulated.
- **Missing metadata is weak evidence.** Social platforms strip EXIF; absence alone is not suspicious.
- **Audio quality matters.** Phone recordings, compression, and background noise reduce detector reliability.
- **Video analysis is simple.** It relies on sampled frames, per-frame image checks, and frame-difference spikes, not a deep temporal model.
- **LLM output is an indicator, not ground truth.** Text and cross-modal reasoning can misread context. Findings quote the exact span so a human can check.
- **Confidence is rule-based, not statistically calibrated.** There is no large labeled evaluation set behind it.
- **Small test set.** The demo set is tiny and does not support accuracy claims.
- **LLM calls leave the machine.** Only text (captions, transcripts, notes) is sent to Google Gemini; media files are never uploaded. On the free tier Google may use requests to improve its products, so sensitive or private evidence should not be analyzed with it. Everything else is local.
- **Free-tier rate limits.** Gemini's free tier is rate-limited. If the limit is hit, LLM-based checks are reported as unavailable rather than failing silently.
- **Cut or partial features:** `<list anything marked 🟡 or ❌ above, with the reason>`

## 10. Judge verification checklist

A quick pass for evaluators. Tick as you confirm in the running app or report.

**Inputs and integrity**
- [ ] Accepts image, video, audio, and text inputs
- [ ] File hashes shown for each input
- [ ] Original files are not modified

**Analysis**
- [ ] Image: metadata, compression/heatmap, synthetic-image indicators
- [ ] Video: flagged timestamps with frame evidence
- [ ] Audio: flagged segments with timestamps and spectrogram
- [ ] Text: caption/transcript contradictions quote the exact span

**Cross-modal**
- [ ] Correlation findings reference related findings from other media
- [ ] Both supporting and conflicting signals are surfaced

**Trust and explainability**
- [ ] Every finding has an explanation, location, evidence reference, and limitations
- [ ] Confidence is a level with written reasoning, not a bare score
- [ ] Failed or unavailable analyses are shown, not hidden
- [ ] At least one case ends Inconclusive

**Report**
- [ ] Contains flagged evidence, indicators, cross-modal context, confidence, source trace, and summary
- [ ] Includes recommended human checks and an analysis log
- [ ] Opens offline as a single HTML file; JSON export available
- [ ] Ends with the human-review notice

## 11. Repository map

```
app.py                       Streamlit UI
truthlens/schemas.py         Finding / Report models
truthlens/storage.py         Hashing and read-only evidence storage
truthlens/pipeline.py        Orchestration
truthlens/confidence.py      Confidence rules
truthlens/llm.py             Single wrapper around the Gemini API
truthlens/analyzers/         image, video, audio, transcribe, text, cross_modal
truthlens/report/            HTML report generator and template
scripts/                     download_models.py, run_samples.py, test_llm.py
samples/                     Demo evidence and ground truth
tests/                       Schema validation tests
SPEC.md                      Build specification
product.md                   This document
```

---

*TruthLens produces automated indicators only. It is not a final verdict and requires review by a human investigator.*