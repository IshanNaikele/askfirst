import streamlit as st
import json
import os

st.set_page_config(
    page_title="Ask First — Health Pattern Analyzer",
    layout="wide"
)

# ─────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────

def load_timeline(user_id: str) -> dict:
    path = f"outputs/step2_timeline/{user_id}.json"
    with open(path, "r") as f:
        return json.load(f)

def load_patterns(user_id: str) -> dict:
    path = f"outputs/step4_reasoned/{user_id}.json"
    with open(path, "r") as f:
        return json.load(f)

def load_candidates(user_id: str) -> dict:
    path = f"outputs/step3_candidates/{user_id}.json"
    with open(path, "r") as f:
        return json.load(f)

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

CONFIDENCE_COLOR = {
    "very_high": "🟢",
    "high": "🟡",
    "medium": "🟠",
    "low": "🔴"
}

USER_MAP = {
    "Arjun (USR001)": "USR001",
    "Meera (USR002)": "USR002",
    "Priya (USR003)": "USR003"
}

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.title("Ask First — Health Pattern Analyzer")
st.caption("Cross-conversation pattern detection with temporal reasoning")

# User Selector
selected_label = st.selectbox("Select User", list(USER_MAP.keys()))
user_id = USER_MAP[selected_label]

timeline_data = load_timeline(user_id)
patterns_data = load_patterns(user_id)
candidates_data = load_candidates(user_id)

st.divider()

# ─────────────────────────────────────────────
# Section 1 — Timeline View
# ─────────────────────────────────────────────

st.subheader("📅 Health Timeline")

for entry in timeline_data["timeline"]:
    symptoms = [
        s["name"] for s in entry.get("symptoms", [])
        if s.get("certainty") != "resolved"
    ]
    resolved = [
        s["name"] for s in entry.get("symptoms", [])
        if s.get("certainty") == "resolved"
    ]
    behaviors = entry.get("behaviors", [])

    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown(f"**Day {entry['days_since_start']}**")
        st.caption(entry["session_id"])
    with col2:
        if symptoms:
            st.markdown(f"🔴 **Symptoms:** {', '.join(symptoms)}")
        if resolved:
            st.markdown(f"✅ **Resolved:** {', '.join(resolved)}")
        if behaviors:
            st.markdown(f"⚡ **Behaviors:** {', '.join(behaviors)}")

    st.divider()

# ─────────────────────────────────────────────
# Section 2 — Pattern Cards
# ─────────────────────────────────────────────

st.subheader("🔍 Confirmed Patterns")

confirmed = patterns_data.get("confirmed_patterns", [])

if not confirmed:
    st.info("No confirmed patterns found for this user.")
else:
    for i, pattern in enumerate(confirmed):
        confidence = pattern.get("confidence", "low")
        icon = CONFIDENCE_COLOR.get(confidence, "⚪")

        with st.expander(f"{icon} {pattern['pattern']} — [{confidence.upper()}]", expanded=True):

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Confidence", confidence.upper())
            with col2:
                st.metric("Consistency Score", pattern.get("consistency_score", 0))
            with col3:
                st.metric("Counter Examples", pattern.get("counter_examples_found", 0))

            st.markdown(f"**Behavior:** `{pattern.get('behavior')}`")
            st.markdown(f"**Symptom:** `{pattern.get('symptom')}`")
            st.markdown(f"**Delay Type:** `{pattern.get('delay_type')}`")

            sessions = pattern.get("sessions_involved", [])
            if sessions:
                st.markdown(f"**Sessions Involved:** {', '.join(sessions)}")

            downstream = pattern.get("downstream_patterns", [])
            if downstream:
                st.markdown(f"**Downstream Patterns:** {', '.join(downstream)}")

            root = pattern.get("root_cause")
            if root:
                st.markdown(f"**Root Cause Link:** {root}")

            st.markdown("**Reasoning Trace:**")
            trace = pattern.get("reasoning_trace", [])
            for step in trace:
                st.markdown(f"- {step}")

st.divider()

# ─────────────────────────────────────────────
# Section 3 — Rejected Patterns
# ─────────────────────────────────────────────

with st.expander("❌ Rejected Patterns", expanded=False):
    rejected = patterns_data.get("rejected_patterns", [])
    if not rejected:
        st.info("No rejected patterns.")
    else:
        for pattern in rejected:
            st.markdown(f"**{pattern['pattern']}**")
            st.caption(f"Reason: {pattern['reasoning_trace'][-1] if pattern.get('reasoning_trace') else 'No reason provided'}")
            st.divider()

# ─────────────────────────────────────────────
# Section 4 — Raw JSON Output (Mandatory)
# ─────────────────────────────────────────────

st.subheader("📄 Raw JSON Output")

tab1, tab2, tab3 = st.tabs(["Confirmed Patterns", "Rejected Patterns", "All Candidates"])

with tab1:
    st.json(patterns_data.get("confirmed_patterns", []))

with tab2:
    st.json(patterns_data.get("rejected_patterns", []))

with tab3:
    st.json(candidates_data.get("candidates", []))