import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def load_dataset(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

def load_prompt() -> str:
    with open("prompts/extraction_prompt.txt", "r") as f:
        return f.read()

def build_conversation_text(conversation: dict) -> str:
    parts = []

    if conversation.get("user_message"):
        parts.append(f"User: {conversation['user_message']}")

    if conversation.get("user_followup"):
        parts.append(f"User followup: {conversation['user_followup']}")

    if conversation.get("clary_response"):
        parts.append(f"Clary response: {conversation['clary_response']}")

    return "\n".join(parts)

def extract_events_for_session(session: dict, system_prompt: str) -> dict:

    conversation_text = build_conversation_text(session)

    user_message = f"""
Session ID: {session['session_id']}
Timestamp: {session['timestamp']}

Conversation:
{conversation_text}

Extract structured health events from this conversation.
Return ONLY valid JSON. No explanation. No markdown.
"""

    # Collect streamed response
    raw_text = ""
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.2,  # Low temp for structured extraction
        max_completion_tokens=1024,
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

    extracted = json.loads(raw_text)
    return extracted

INTENSITY_MAP = {
    "bad": "severe",
    "low": "mild",
    "high": "severe",
    "very mild": "mild",
    "very severe": "severe"
}

def normalize_extracted(extracted: dict) -> dict:
    for symptom in extracted.get("symptoms", []):
        intensity = symptom.get("intensity", "mild")
        symptom["intensity"] = INTENSITY_MAP.get(intensity, intensity)
    return extracted


def extract_all_users(dataset: dict) -> dict:
    system_prompt = load_prompt()
    all_extracted = {}

    for user in dataset["users"]:
        user_id = user["user_id"]
        user_name = user["name"]
        print(f"\nExtracting events for {user_name} ({user_id})...")

        user_events = []

        for conversation in user["conversations"]:
            print(f"  Processing session {conversation['session_id']}...")
            extracted = extract_events_for_session(conversation, system_prompt)
            extracted = normalize_extracted(extracted)
            user_events.append(extracted)

        all_extracted[user_id] = {
            "user_id": user_id,
            "name": user_name,
            "age": user["age"],
            "gender": user["gender"],
            "location": user["location"],
            "occupation": user["occupation"],
            "events": user_events
        }

        os.makedirs("outputs/step1_extracted", exist_ok=True)
        output_path = f"outputs/step1_extracted/{user_id}.json"
        with open(output_path, "w") as f:
            json.dump(all_extracted[user_id], f, indent=2)

        print(f"  Saved to {output_path}")

    return all_extracted

if __name__ == "__main__":
    dataset = load_dataset("data/askfirst_synthetic_dataset.json")
    result = extract_all_users(dataset)
    print("\nStep 1 complete.")
    print(f"Users processed: {list(result.keys())}")