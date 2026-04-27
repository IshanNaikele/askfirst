# Ask First — Health Pattern Analyzer

> Cross-conversation health pattern detection with temporal reasoning, powered by LLMs.

Built for the Ask First AI Intern Assignment by **Ishan Naikele**
📧 [ishannaikele23@gmail.com](mailto:ishannaikele23@gmail.com) | 🐙 [github.com/IshanNaikele](https://github.com/IshanNaikele)

---

## What This Does

Clary (Ask First's AI companion) reads a user's full health conversation history across months and surfaces hidden patterns — things users themselves never connected. This system is the reasoning layer behind that.

Two core capabilities:

1. **Cross-conversation pattern detection with temporal reasoning** — finds causal links between behaviors and symptoms across time, not just within a single session.
2. **Confidence scoring per pattern** — every pattern comes with a score and a one-line justification in JSON format, with streaming support.

---

## Folder Structure

```
ASKFIRST/
├── data/
│   └── askfirst_synthetic_dataset.json     # Input: 3 user profiles, 8-10 sessions each
│
├── outputs/
│   ├── step1_extracted/                    # Per-user structured event extraction
│   │   ├── USR001.json
│   │   ├── USR002.json
│   │   └── USR003.json
│   ├── step2_timeline/                     # Chronological timeline with day offsets
│   │   ├── USR001.json
│   │   ├── USR002.json
│   │   └── USR003.json
│   ├── step3_candidates/                   # Code-detected pattern candidates
│   │   ├── USR001.json
│   │   ├── USR002.json
│   │   └── USR003.json
│   └── step4_reasoned/                     # LLM-reasoned confirmed patterns
│       ├── USR001.json
│       ├── USR002.json
│       └── USR003.json
│
├── prompts/
│   └── extraction_prompt.txt               # System prompt for Step 1 event extraction
│
├── steps/
│   ├── __init__.py
│   ├── step1_extractor.py                  # Groq LLM: raw conversation → structured events
│   ├── step2_timeline.py                   # Builds chronological timeline with day offsets
│   ├── step3_candidates.py                 # Algorithmic pattern candidate generation
│   ├── step4_reasoner.py                   # Groq LLM: temporal reasoning + confidence scoring
│   └── step5_ui.py                         # Streamlit UI
│
├── .env                                    # Your API keys (not committed)
├── .gitignore
├── LICENSE
├── main.py                                 # Run all 4 pipeline steps in sequence
├── README.md
└── requirements.txt
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/IshanNaikele/askfirst.git
cd askfirst
```

### 2. Create and activate a virtual environment

```bash
python -m venv my_env
source my_env/bin/activate        # Mac/Linux
my_env\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your API key

Create a `.env` file in the root:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

---

## How to Run

### Option A — Full pipeline (Steps 1–4)

Runs extraction → timeline → candidates → reasoning and saves all outputs.

```bash
python main.py
```

### Option B — Run individual steps

```bash
python steps/step1_extractor.py     # Extract events from raw conversations
python steps/step2_timeline.py      # Build timelines
python steps/step3_candidates.py    # Generate pattern candidates
python steps/step4_reasoner.py      # LLM reasoning + confidence scoring
```

### Option C — Launch the Streamlit UI

> Run the full pipeline first (Option A) before launching the UI.

```bash
streamlit run steps/step5_ui.py
```

Opens at `http://localhost:8501`. Select a user to view their timeline, confirmed patterns, reasoning traces, and raw JSON output.

---

## Pipeline Explained

### Step 1 — Event Extraction (`step1_extractor.py`)

**Model:** `llama-3.1-8b-instant` via Groq (fast, low-cost, sufficient for structured extraction)

Each conversation session is sent to the LLM with a structured extraction prompt. The model returns JSON with:
- `symptoms` (name, intensity, certainty)
- `behaviors` (diet changes, sleep patterns, exercise habits)
- `context` (stress, travel, work changes)
- `clary_interpretation`

**Streaming is enabled** on all LLM calls. Output is validated and intensity labels are normalized (`bad → severe`, `low → mild`, etc.).

---

### Step 2 — Timeline Builder (`step2_timeline.py`)

Pure Python. Sorts sessions by timestamp and computes:
- `days_since_start` — absolute day offset from first session
- `days_since_previous` — gap between consecutive sessions
- `event_window` — sliding window of last 3 session IDs (used for context management in Step 4)

No LLM call. Deterministic.

---

### Step 3 — Candidate Generator (`step3_candidates.py`)

Four algorithmic detectors, no LLM:

| Detector | What it finds |
|---|---|
| Repeated co-occurrence | Behavior + symptom appear together in 2+ sessions |
| Delayed effect | Behavior in session A, symptom appears 1–60 days later in session B |
| Intervention confirmation | Symptom present, then marked resolved after a behavior change |
| Cross-pattern linking | One behavior linked to multiple symptoms → root cause candidate |

Each candidate gets a **consistency score** (how often does the symptom appear when the behavior is present?) and **counter examples** (sessions where behavior appeared without the symptom).

A pre-filter removes weak candidates before passing to the LLM, reducing noise and token cost.

---

### Step 4 — Reasoner (`step4_reasoner.py`)

**Model:** `llama-3.3-70b-versatile` via Groq (stronger reasoning capability needed here)

The LLM receives:
- Full timeline summary (all sessions, symptoms, behaviors, day offsets)
- All filtered candidates from Step 3

**Context management strategy:**
The entire timeline is included in each reasoning call. Since users have 8–10 sessions over ~3 months, the full context fits comfortably within the model's context window. This avoids chunking errors — a symptom on Day 80 can only be correctly attributed to a behavior on Day 5 if both are visible simultaneously.

The LLM is instructed to:
- Check time order (behavior must precede symptom)
- Check consistency scores and counter examples
- Note delay durations explicitly (e.g., "hair fall 9 weeks after caloric restriction")
- Merge duplicate candidates into one pattern
- Reject false associations with explicit reasoning
- Use **only** valid session IDs from the provided list (hallucination guard)

**Streaming is enabled.** Output is a JSON array of confirmed and rejected patterns, each with a `reasoning_trace` array showing step-by-step logic.

---

### Step 5 — Streamlit UI (`step5_ui.py`)

Three sections:
- **Health Timeline** — session-by-session view with symptoms, behaviors, and resolved items
- **Confirmed Patterns** — expandable cards with confidence badge, consistency score, counter examples, and full reasoning trace
- **Raw JSON** — tabs for confirmed patterns, rejected patterns, and all Step 3 candidates

---

## Output Format (Step 4 JSON)

```json
[
  {
    "pattern": "Late night eating → stomach pain",
    "behavior": "late night eating",
    "symptom": "stomach pain",
    "confidence": "high",
    "sessions_involved": ["S001", "S004", "S007"],
    "delay_type": "immediate",
    "consistency_score": 1.0,
    "counter_examples_found": 0,
    "root_cause": null,
    "downstream_patterns": [],
    "reasoning_trace": [
      "Step 1: Code detected co-occurrence in S001, S004, S007",
      "Step 2: Time order confirmed — eating mention precedes pain in all 3 cases",
      "Step 3: Consistency 1.0 — symptom always present when behavior present",
      "Step 4: Zero counter examples found",
      "Step 5: Confidence HIGH — 3 occurrences, perfect consistency, zero counter examples"
    ],
    "rejected": false
  }
]
```

---

## LLM Choice

| Step | Model | Reason |
|---|---|---|
| Step 1 | `llama-3.1-8b-instant` | Fast, cheap, reliable for structured JSON extraction from short conversations |
| Step 4 | `llama-3.3-70b-versatile` | Better multi-step reasoning needed for temporal causal analysis across a full timeline |

Both via **Groq** — chosen for free-tier availability, fast inference speeds, and native streaming support.

---

## Requirements

```
groq
streamlit
python-dotenv
```

Install with:
```bash
pip install -r requirements.txt
```

---

## One-Page Writeup

### Approach to the Reasoning Problem

The system is split into two distinct reasoning layers — algorithmic and neural — intentionally. The algorithmic layer (Step 3) is fast, deterministic, and good at generating exhaustive candidates without missing obvious patterns. The LLM layer (Step 4) is slower but capable of understanding delay semantics, merging near-duplicate candidates, and rejecting spurious associations.

The key design choice is **full timeline context per reasoning call**. Instead of chunking sessions and reasoning piecemeal, the entire timeline is passed in one shot. This lets the model correctly reason that a symptom on Day 78 is causally downstream of a behavior change on Day 6 — something impossible to detect if the context is windowed.

Confidence scoring is made explicit by forcing the model to output a `reasoning_trace` array — not a confidence label alone. The trace acts as an audit log: it shows what the system considered, making hallucinations visible rather than hidden.

---

### Where the System Fails or Hallucinates Confidently

**Session ID hallucination.** Even with explicit valid-session constraints in the prompt, the 70B model occasionally generates session IDs that don't exist. A post-processing validator strips these, but this means some patterns may end up with fewer sessions than they should — silently weakening confidence scores.

**Spurious delayed patterns.** The Step 3 delayed-effect detector generates candidates for any behavior-symptom pair within a 60-day window. With 8–10 sessions and multiple behaviors and symptoms per session, this produces combinatorial noise. The consistency filter catches most of it, but weak patterns with consistency 0.5–0.6 sometimes pass through and get assigned medium confidence by the LLM — which may or may not be warranted.

**Temporal direction errors.** In a small number of cases the model assigns causality to a behavior that appears *after* the symptom — a reversal of the causal arrow. The prompt instructs against this explicitly, but it still occurs for patterns with short time gaps where the model interprets the behavior and symptom as concurrent.

**What would be built differently with more time:**
- A dedicated time-order validation pass after Step 4 that programmatically checks all confirmed patterns against the timeline and flags reversals
- Embedding-based deduplication before Step 3 to collapse semantically identical symptoms described differently across sessions ("my stomach hurts" vs "abdominal discomfort")
- A feedback loop where rejected patterns are stored and used to improve the extraction prompt over time

---

 