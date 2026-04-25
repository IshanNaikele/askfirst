import json
import os
from datetime import datetime

def load_extracted_user(user_id: str) -> dict:
    path = f"outputs/step1_extracted/{user_id}.json"
    with open(path, "r") as f:
        return json.load(f)

def build_timeline(user_data: dict) -> dict:
    events = user_data["events"]

    # Sort by timestamp
    events = sorted(events, key=lambda x: datetime.fromisoformat(x["timestamp"]))

    first_timestamp = datetime.fromisoformat(events[0]["timestamp"])
    prev_timestamp = first_timestamp

    timeline = []

    for i, event in enumerate(events):
        current_timestamp = datetime.fromisoformat(event["timestamp"])

        days_since_start = (current_timestamp - first_timestamp).days
        days_since_previous = (current_timestamp - prev_timestamp).days

        # Build sliding window of last 3 sessions
        window_start = max(0, i - 2)
        event_window = [
            events[j]["session_id"]
            for j in range(window_start, i + 1)
        ]

        timeline_entry = {
            "session_id": event["session_id"],
            "timestamp": event["timestamp"],
            "days_since_start": days_since_start,
            "days_since_previous": days_since_previous,
            "symptoms": event.get("symptoms", []),
            "behaviors": event.get("behaviors", []),
            "context": event.get("context", []),
            "clary_interpretation": event.get("clary_interpretation", ""),
            "event_window": event_window
        }

        timeline.append(timeline_entry)
        prev_timestamp = current_timestamp

    return {
        "user_id": user_data["user_id"],
        "name": user_data["name"],
        "age": user_data.get("age"),
        "gender": user_data.get("gender"),
        "location": user_data.get("location"),
        "occupation": user_data.get("occupation"),
        "total_sessions": len(timeline),
        "date_range": {
            "first_session": events[0]["timestamp"],
            "last_session": events[-1]["timestamp"],
            "total_days": (
                datetime.fromisoformat(events[-1]["timestamp"]) -
                datetime.fromisoformat(events[0]["timestamp"])
            ).days
        },
        "timeline": timeline
    }

def run_step2():
    user_ids = ["USR001", "USR002", "USR003"]
    os.makedirs("outputs/step2_timeline", exist_ok=True)

    for user_id in user_ids:
        print(f"Building timeline for {user_id}...")
        user_data = load_extracted_user(user_id)
        timeline = build_timeline(user_data)

        output_path = f"outputs/step2_timeline/{user_id}.json"
        with open(output_path, "w") as f:
            json.dump(timeline, f, indent=2)

        print(f"  Sessions: {timeline['total_sessions']}")
        print(f"  Date range: {timeline['date_range']['total_days']} days")
        print(f"  Saved to {output_path}")

if __name__ == "__main__":
    run_step2()
    print("\nStep 2 complete.")