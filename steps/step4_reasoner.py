import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def load_timeline(user_id: str) -> dict:
    path = f"outputs/step2_timeline/{user_id}.json"
    with open(path, "r") as f:
        return json.load(f)

def load_candidates(user_id: str) -> dict:
    path = f"outputs/step3_candidates/{user_id}.json"
    with open(path, "r") as f:
        return json.load(f)

def build_timeline_summary(timeline_data: dict) -> str:
    lines = []
    lines.append(f"User: {timeline_data['name']}, Age: {timeline_data['age']}, Occupation: {timeline_data['occupation']}")
    lines.append(f"Observation period: {timeline_data['date_range']['total_days']} days")
    lines.append("")
    lines.append("TIMELINE:")

    for entry in timeline_data["timeline"]:
        symptoms = [s["name"] for s in entry.get("symptoms", []) if s.get("certainty") != "resolved"]
        resolved = [s["name"] for s in entry.get("symptoms", []) if s.get("certainty") == "resolved"]
        behaviors = entry.get("behaviors", [])
        context = entry.get("context", [])

        line = f"Day {entry['days_since_start']} ({entry['session_id']}): "
        if symptoms:
            line += f"Symptoms: {', '.join(symptoms)} | "
        if resolved:
            line += f"Resolved: {', '.join(resolved)} | "
        if behaviors:
            line += f"Behaviors: {', '.join(behaviors)} | "
        if context:
            line += f"Context: {', '.join(context)}"

        lines.append(line)

    return "\n".join(lines)

def build_candidates_summary(candidates_data: dict) -> str:
    lines = []
    lines.append("CANDIDATE PATTERNS DETECTED BY CODE:")
    lines.append("")

    for i, c in enumerate(candidates_data["candidates"]):
        lines.append(f"Candidate {i+1}:")
        lines.append(f"  Type: {c['type']}")
        lines.append(f"  Behavior: {c['behavior']}")
        lines.append(f"  Symptom: {c['symptom']}")
        lines.append(f"  Sessions involved: {', '.join(c['sessions_involved'])}")
        lines.append(f"  Occurrences: {c['occurrences']}")
        lines.append(f"  Consistency score: {c['consistency_score']}")
        lines.append(f"  Counter examples: {c['counter_examples'] if c['counter_examples'] else 'None'}")
        lines.append(f"  Delay tag: {c['delay_tag']}")
        if c.get("time_gaps"):
            lines.append(f"  Time gaps (days): {c['time_gaps']}")
        if c.get("linked_patterns"):
            lines.append(f"  Linked symptoms from same behavior: {', '.join(c['linked_patterns'])}")
        lines.append("")

    return "\n".join(lines)

def get_valid_session_ids(timeline_data: dict) -> set:
    return {entry["session_id"] for entry in timeline_data["timeline"]}

def validate_patterns(patterns: list, valid_session_ids: set) -> list:
    for pattern in patterns:
        # Remove hallucinated session IDs
        pattern["sessions_involved"] = [
            s for s in pattern["sessions_involved"]
            if s in valid_session_ids
        ]
    return patterns

def build_reasoning_prompt(timeline_summary: str, candidates_summary: str, valid_sessions: set) -> str:
    return f"""You are a health pattern reasoning engine.

You will be given:
1. A user's full health timeline with symptoms, behaviors, and context
2. A list of candidate patterns detected by a code algorithm

VALID SESSION IDs you must only use: {sorted(valid_sessions)}

Your job is to reason carefully about each candidate and produce confirmed patterns with confidence scores.

STRICT RULES:
1. Use ONLY the data provided. Do not assume or invent information.
2. ONLY use session IDs from the VALID SESSION IDs list above. Never invent session IDs.
3. Reason about TIME ORDER. A behavior must come BEFORE or concurrent with the symptom to be causal.
4. Check consistency. If behavior appears without symptom in other sessions, lower confidence.
5. Check counter examples. If counter examples exist, explain why or lower confidence.
6. Detect ROOT CAUSE chains. If one behavior causes multiple symptoms, group them and list downstream patterns.
7. REJECT false patterns explicitly with reasoning.
8. Merge duplicate candidates that represent the same underlying pattern into ONE confirmed pattern.
9. Assign confidence as follows:
   - very_high: 3+ occurrences, consistency 1.0, zero counter examples
   - high: 2+ occurrences, consistency >= 0.8, zero or one counter example
   - medium: consistency >= 0.5, limited sessions or some counter examples
   - low: reject these
10. For delayed patterns like hair fall appearing weeks after diet change, explicitly note the delay in reasoning.
11. Return ONLY valid JSON array. No markdown. No explanation outside JSON.

OUTPUT FORMAT - return a JSON array:
[
  {{
    "pattern": "one line description of the pattern",
    "behavior": "the root behavior",
    "symptom": "the resulting symptom",
    "confidence": "low | medium | high | very_high",
    "sessions_involved": ["only valid session ids from the list above"],
    "delay_type": "immediate | short_delay | long_delay | intervention_confirmed",
    "consistency_score": 0.0,
    "counter_examples_found": 0,
    "root_cause": "if this shares a root cause with another pattern name it here, else null",
    "downstream_patterns": ["list of other symptoms caused by same behavior if any"],
    "reasoning_trace": [
      "Step 1: what the code detected",
      "Step 2: time order check",
      "Step 3: consistency check",
      "Step 4: counter example check",
      "Step 5: final verdict with confidence justification"
    ],
    "rejected": false
  }}
]

If you reject a candidate set rejected to true and explain why in reasoning_trace.
Merge all duplicate candidates for the same behavior-symptom pair into a single pattern.

{timeline_summary}

{candidates_summary}

Analyze all candidates. Merge duplicates. Reject false patterns. Use only valid session IDs. Return JSON array only.
"""

def reason_patterns(user_id: str) -> dict:
    timeline_data = load_timeline(user_id)
    candidates_data = load_candidates(user_id)

    valid_session_ids = get_valid_session_ids(timeline_data)
    timeline_summary = build_timeline_summary(timeline_data)
    candidates_summary = build_candidates_summary(candidates_data)
    prompt = build_reasoning_prompt(timeline_summary, candidates_summary, valid_session_ids)

    print(f"  Sending to LLM for reasoning...")

    raw_text = ""
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are a health pattern reasoning engine. Return only valid JSON arrays. No markdown. No explanation outside JSON. Never invent session IDs."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
        max_completion_tokens=4000,
        top_p=1,
        stream=True,
        stop=None
    )

    for chunk in completion:
        raw_text += chunk.choices[0].delta.content or ""

    raw_text = raw_text.strip()

    # Strip markdown if model wraps in ```json
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    # Strip trailing ``` if present
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3].strip()

    patterns = json.loads(raw_text)

    # Validate and clean session IDs
    patterns = validate_patterns(patterns, valid_session_ids)

    # Split confirmed and rejected
    confirmed = [p for p in patterns if not p.get("rejected", False)]
    rejected = [p for p in patterns if p.get("rejected", False)]

    # Print summary per pattern
    print(f"  Confirmed patterns:")
    for p in confirmed:
        print(f"    [{p['confidence']}] {p['pattern']}")
    print(f"  Rejected patterns:")
    for p in rejected:
        print(f"    [REJECTED] {p['pattern']}")

    return {
        "user_id": user_id,
        "name": timeline_data["name"],
        "total_patterns_confirmed": len(confirmed),
        "total_patterns_rejected": len(rejected),
        "confirmed_patterns": confirmed,
        "rejected_patterns": rejected
    }

def run_step4():
    user_ids = ["USR001", "USR002", "USR003"]
    os.makedirs("outputs/step4_reasoned", exist_ok=True)

    for user_id in user_ids:
        print(f"\nReasoning patterns for {user_id}...")
        result = reason_patterns(user_id)

        output_path = f"outputs/step4_reasoned/{user_id}.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        print(f"  Total confirmed: {result['total_patterns_confirmed']}")
        print(f"  Total rejected: {result['total_patterns_rejected']}")
        print(f"  Saved to {output_path}")

if __name__ == "__main__":
    run_step4()
    print("\nStep 4 complete.")