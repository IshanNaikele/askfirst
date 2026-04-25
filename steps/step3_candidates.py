import json
import os
from datetime import datetime
from collections import defaultdict

def load_timeline(user_id: str) -> dict:
    path = f"outputs/step2_timeline/{user_id}.json"
    with open(path, "r") as f:
        return json.load(f)

def get_symptom_names(session: dict) -> list:
    return [
        s["name"] for s in session.get("symptoms", [])
        if s.get("certainty") != "resolved"
    ]

def get_resolved_symptoms(session: dict) -> list:
    return [
        s["name"] for s in session.get("symptoms", [])
        if s.get("certainty") == "resolved"
    ]

def get_behaviors(session: dict) -> list:
    return session.get("behaviors", [])

def normalize_name(name: str) -> str:
    return name.lower().strip()

# ─────────────────────────────────────────────
# A. Repeated Co-occurrence Detection
# ─────────────────────────────────────────────
def detect_repeated_cooccurrence(timeline: list) -> list:
    pair_map = defaultdict(list)

    for session in timeline:
        behaviors = get_behaviors(session)
        symptoms = get_symptom_names(session)

        for b in behaviors:
            for s in symptoms:
                key = (normalize_name(b), normalize_name(s))
                pair_map[key].append(session["session_id"])

    candidates = []
    for (behavior, symptom), session_ids in pair_map.items():
        if len(session_ids) >= 2:
            strength = "strong" if len(session_ids) >= 3 else "weak"
            candidates.append({
                "type": "repeated_cooccurrence",
                "behavior": behavior,
                "symptom": symptom,
                "sessions_involved": session_ids,
                "occurrences": len(session_ids),
                "candidate_strength": strength,
                "time_gaps": [],
                "delay_tag": "immediate",
                "consistency_score": 0.0,
                "counter_examples": [],
                "linked_patterns": []
            })

    return candidates

# ─────────────────────────────────────────────
# B. Delayed Effect Detection
# ─────────────────────────────────────────────
def detect_delayed_effects(timeline: list) -> list:
    candidates = []
    seen_pairs = set()

    for i, session_b in enumerate(timeline):
        behaviors = get_behaviors(session_b)
        t1 = datetime.fromisoformat(session_b["timestamp"])

        for j in range(i + 1, len(timeline)):
            session_s = timeline[j]
            symptoms = get_symptom_names(session_s)
            t2 = datetime.fromisoformat(session_s["timestamp"])
            gap = (t2 - t1).days

            if gap > 60:
                break

            if 0 < gap <= 3:
                delay_tag = "immediate"
            elif 4 <= gap <= 14:
                delay_tag = "short_delay"
            elif 15 <= gap <= 60:
                delay_tag = "long_delay"
            else:
                continue

            for b in behaviors:
                for s in symptoms:
                    key = (
                        normalize_name(b),
                        normalize_name(s),
                        session_b["session_id"],
                        session_s["session_id"]
                    )
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)

                    candidates.append({
                        "type": "delayed_effect",
                        "behavior": normalize_name(b),
                        "symptom": normalize_name(s),
                        "behavior_session": session_b["session_id"],
                        "symptom_session": session_s["session_id"],
                        "sessions_involved": [
                            session_b["session_id"],
                            session_s["session_id"]
                        ],
                        "occurrences": 1,
                        "candidate_strength": "weak",
                        "time_gaps": [gap],
                        "delay_tag": delay_tag,
                        "consistency_score": 0.0,
                        "counter_examples": [],
                        "linked_patterns": []
                    })

    return candidates

# ─────────────────────────────────────────────
# C. Intervention Confirmation
# ─────────────────────────────────────────────
def detect_intervention(timeline: list) -> list:
    candidates = []
    behavior_symptom_sessions = defaultdict(list)

    for session in timeline:
        behaviors = get_behaviors(session)
        symptoms = get_symptom_names(session)
        resolved = get_resolved_symptoms(session)

        for b in behaviors:
            b_norm = normalize_name(b)
            for s in symptoms:
                behavior_symptom_sessions[(b_norm, normalize_name(s))].append({
                    "session_id": session["session_id"],
                    "state": "present"
                })
            for s in resolved:
                behavior_symptom_sessions[(b_norm, normalize_name(s))].append({
                    "session_id": session["session_id"],
                    "state": "resolved"
                })

    for session in timeline:
        resolved = get_resolved_symptoms(session)

        for s in resolved:
            s_norm = normalize_name(s)
            for (b_norm, sym_norm), entries in behavior_symptom_sessions.items():
                if sym_norm != s_norm:
                    continue

                present_sessions = [
                    e["session_id"] for e in entries
                    if e["state"] == "present"
                ]
                resolved_sessions = [
                    e["session_id"] for e in entries
                    if e["state"] == "resolved"
                ]

                if len(present_sessions) >= 1 and len(resolved_sessions) >= 1:
                    candidates.append({
                        "type": "intervention_confirmed",
                        "behavior": b_norm,
                        "symptom": s_norm,
                        "sessions_involved": present_sessions + resolved_sessions,
                        "occurrences": len(present_sessions),
                        "candidate_strength": "strong",
                        "time_gaps": [],
                        "delay_tag": "intervention",
                        "consistency_score": 0.0,
                        "counter_examples": [],
                        "linked_patterns": []
                    })

    return candidates

# ─────────────────────────────────────────────
# D. Cross-Pattern Linking
# ─────────────────────────────────────────────
def detect_cross_pattern_links(candidates: list) -> list:
    behavior_to_symptoms = defaultdict(set)

    for c in candidates:
        behavior_to_symptoms[c["behavior"]].add(c["symptom"])

    for c in candidates:
        linked = []
        all_symptoms = behavior_to_symptoms[c["behavior"]]
        for s in all_symptoms:
            if s != c["symptom"]:
                linked.append(s)
        c["linked_patterns"] = linked

        if len(linked) >= 2:
            c["type"] = "root_cause"
            c["candidate_strength"] = "strong"

    return candidates

# ─────────────────────────────────────────────
# Counter-Example Check + Consistency Score
# ─────────────────────────────────────────────
def check_counter_examples(candidates: list, timeline: list) -> list:
    for c in candidates:
        behavior = c["behavior"]
        symptom = c["symptom"]
        involved_sessions = set(c["sessions_involved"])

        total_behavior_sessions = 0
        symptom_present_count = 0
        counter_examples = []

        for session in timeline:
            session_behaviors = [
                normalize_name(b) for b in get_behaviors(session)
            ]

            if behavior in session_behaviors:
                total_behavior_sessions += 1
                session_symptoms = [
                    normalize_name(s) for s in get_symptom_names(session)
                ]
                if symptom in session_symptoms:
                    symptom_present_count += 1
                else:
                    if session["session_id"] not in involved_sessions:
                        counter_examples.append(session["session_id"])

        if total_behavior_sessions > 0:
            c["consistency_score"] = round(
                symptom_present_count / total_behavior_sessions, 2
            )
        c["counter_examples"] = counter_examples

    return candidates

# ─────────────────────────────────────────────
# Pre-Filter — Remove Noise Before Step 4
# ─────────────────────────────────────────────
def filter_candidates(candidates: list) -> list:
    filtered = []

    for c in candidates:
        keep = False

        # Always keep intervention confirmed
        if c["type"] == "intervention_confirmed":
            keep = True

        # Keep high consistency repeated patterns
        elif c["type"] == "repeated_cooccurrence" and c["occurrences"] >= 3:
            keep = True

        elif c["type"] == "repeated_cooccurrence" and c["occurrences"] >= 2 and c["consistency_score"] >= 0.8:
            keep = True

        # Keep delayed effects only if consistency is strong
        elif c["type"] == "delayed_effect" and c["consistency_score"] >= 0.7:
            keep = True

        # Keep root cause candidates with decent consistency
        elif c["type"] == "root_cause" and c["consistency_score"] >= 0.5:
            keep = True

        # Keep root cause with 0 counter examples even if consistency is lower
        elif c["type"] == "root_cause" and len(c["counter_examples"]) == 0 and c["occurrences"] >= 2:
            keep = True

        if keep:
            filtered.append(c)

    return filtered

# ─────────────────────────────────────────────
# Main Runner
# ─────────────────────────────────────────────
def generate_candidates(user_id: str) -> dict:
    data = load_timeline(user_id)
    timeline = data["timeline"]

    print(f"  Running repeated co-occurrence...")
    repeated = detect_repeated_cooccurrence(timeline)

    print(f"  Running delayed effect detection...")
    delayed = detect_delayed_effects(timeline)

    print(f"  Running intervention confirmation...")
    intervention = detect_intervention(timeline)

    all_candidates = repeated + delayed + intervention

    print(f"  Running cross-pattern linking...")
    all_candidates = detect_cross_pattern_links(all_candidates)

    print(f"  Running counter-example check...")
    all_candidates = check_counter_examples(all_candidates, timeline)

    print(f"  Filtering noise...")
    all_candidates = filter_candidates(all_candidates)

    print(f"  Candidates before filter would have been more.")
    print(f"  Kept: {len(all_candidates)} high quality candidates")

    return {
        "user_id": user_id,
        "name": data["name"],
        "total_candidates": len(all_candidates),
        "candidates": all_candidates
    }

def run_step3():
    user_ids = ["USR001", "USR002", "USR003"]
    os.makedirs("outputs/step3_candidates", exist_ok=True)

    for user_id in user_ids:
        print(f"\nGenerating candidates for {user_id}...")
        result = generate_candidates(user_id)

        output_path = f"outputs/step3_candidates/{user_id}.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        print(f"  Total candidates saved: {result['total_candidates']}")
        print(f"  Saved to {output_path}")

if __name__ == "__main__":
    run_step3()
    print("\nStep 3 complete.")