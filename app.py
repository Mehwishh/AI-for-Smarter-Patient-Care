"""
Phase 6: Streamlit app.

Run locally:
    streamlit run app.py

Needs, in the same folder:
    - lab_qa_flagged.csv   (from Phase 4's data-quality step)
    - events_df.csv        (from Phase 2/3's unified timeline)
    - GROQ_API_KEY set via .env (local) or st.secrets (Streamlit Cloud)
"""

import os
import re
import json
import difflib
import textwrap
import pandas as pd
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Patient Timeline Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- Light custom styling for a more "product" feel ----
st.markdown("""
<style>
    .kpi-card {
        border-radius: 12px;
        padding: 16px 18px;
        text-align: left;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        height: 100%;
    }
    .kpi-card .kpi-icon { font-size: 22px; }
    .kpi-card .kpi-value { font-size: 26px; font-weight: 700; margin-top: 4px; }
    .kpi-card .kpi-label { font-size: 12.5px; color: #555; margin-top: 2px; }
    .kpi-blue   { background: #EAF2FE; }
    .kpi-green  { background: #E9F8EE; }
    .kpi-amber  { background: #FFF6E5; }
    .kpi-purple { background: #F1ECFB; }
    .table-note {
        font-size: 13px;
        color: #555;
        background: #F7F7F9;
        border-left: 3px solid #9aa0ff;
        padding: 6px 12px;
        border-radius: 4px;
        margin-bottom: 8px;
    }
    .status-badge {
        display: inline-block;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 4px;
    }
    .badge-green  { background: #E6F6EA; color: #1E7B34; }
    .badge-yellow { background: #FFF3D6; color: #8A6100; }
    .badge-red    { background: #FCE8E8; color: #B02A2A; }
    .badge-grey   { background: #EFEFF2; color: #444; }
    h1, h2, h3 { font-family: -apple-system, "Segoe UI", sans-serif; }
</style>
""", unsafe_allow_html=True)

st.error(
    "Research and educational prototype only. Not for clinical use. "
    "Do not use for diagnosis, treatment, triage, or emergency decisions."
)
st.title("Patient Timeline & Evidence Retrieval")
st.caption("MIMIC-IV Clinical Database Demo v2.2 — research/education prototype")

# =========================================================
# LOAD DATA
# =========================================================
@st.cache_data
def load_data():
    lab_qa = pd.read_csv("lab_qa_flagged.csv", parse_dates=["charttime"])
    events = pd.read_csv("events_df.csv", parse_dates=["event_time"])
    patient_info = pd.read_csv("patient_info.csv")
    vitals = pd.read_csv("vitals_df.csv", parse_dates=["charttime"])
    return lab_qa, events, patient_info, vitals

lab_qa_flagged, events_df, patient_info, vitals_df = load_data()

VALID_METRICS = sorted(lab_qa_flagged["label"].dropna().unique().tolist())
VALID_EVENT_TYPES = sorted(events_df["event_type"].dropna().unique().tolist())

# =========================================================
# GROQ CLIENT
# Local dev: reads from .env (via os.environ)
# Streamlit Cloud: reads from st.secrets
# =========================================================
def get_groq_key():
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY")

GROQ_API_KEY = get_groq_key()
client = None
if not GROQ_API_KEY:
    st.warning(
        "No GROQ_API_KEY found. Set it in a local .env file, or in "
        "Streamlit Cloud under Settings -> Secrets. The Q&A box below "
        "will not work until a key is provided."
    )
else:
    client = Groq(api_key=GROQ_API_KEY)

MODEL = "llama-3.3-70b-versatile"

# =========================================================
# PHASE 4: DETERMINISTIC RETRIEVAL (unchanged from notebook)
# =========================================================
def _lab_evidence(df):
    df = df.drop_duplicates(subset=["label", "charttime", "valuenum"])
    return [
        {
            "source_table": "labevents",
            "source_id": str(r.get("labevent_id", r.name)),
            "timestamp": str(r["charttime"]),
            "description": r["label"],
            "value": r["valuenum"],
            "unit": r["valueuom"],
            "quality_flag": bool(r.get("quality_flag", False)),
            "quality_flag_reason": r.get("quality_flag_reason", ""),
        }
        for _, r in df.head(10).iterrows()
    ]

def _event_evidence(df):
    df = df.drop_duplicates(subset=["description", "event_time"])
    return [
        {
            "source_table": r["source_table"],
            "source_id": str(r["source_id"]),
            "timestamp": str(r["event_time"]),
            "description": r["description"],
        }
        for _, r in df.head(10).iterrows()
    ]

def retrieve_lab_metric(subject_id, metric, agg):
    if metric not in VALID_METRICS:
        return {"status": "abstained", "evidence": [],
                "reason": f"'{metric}' is not a recognized lab metric."}

    subset = lab_qa_flagged[
        (lab_qa_flagged["subject_id"] == subject_id) &
        (lab_qa_flagged["label"] == metric)
    ]
    numeric = subset[subset["valuenum"].notna()]

    if numeric.empty:
        return {"status": "abstained", "evidence": [],
                "reason": f"No numeric records for '{metric}' for this patient."}

    if "quality_flag_reason" in subset.columns:
        if subset["quality_flag_reason"].str.contains("implausible_value", na=False).all():
            return {"status": "abstained", "evidence": _lab_evidence(subset),
                    "reason": f"All records for '{metric}' are flagged implausible."}

    if agg == "max":
        row = numeric.loc[numeric["valuenum"].idxmax()]
    elif agg == "min":
        row = numeric.loc[numeric["valuenum"].idxmin()]
    else:
        row = numeric.sort_values("charttime").iloc[-1]

    return {"status": "answered", "evidence": _lab_evidence(pd.DataFrame([row]))}

def retrieve_event(subject_id, event_type):
    if event_type not in VALID_EVENT_TYPES:
        return {"status": "abstained", "evidence": [],
                "reason": f"'{event_type}' is not a recognized event type."}

    subset = events_df[
        (events_df["subject_id"] == subject_id) &
        (events_df["event_type"] == event_type)
    ].sort_values("event_time")

    if subset.empty:
        return {"status": "abstained", "evidence": [],
                "reason": f"No {event_type} records found for this patient."}

    return {"status": "answered", "evidence": _event_evidence(subset)}

# =========================================================
# PHASE 5: LLM LAYER
# =========================================================
QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "structured_query",
        "description": "Convert a clinical question into a structured lookup.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {"type": "string", "enum": ["lab_metric", "event_lookup", "unsupported"]},
                "metric": {"type": "string", "enum": VALID_METRICS + [""]},
                "agg": {"type": "string", "enum": ["max", "min", "latest", ""]},
                "event_type": {"type": "string", "enum": [e for e in VALID_EVENT_TYPES if e != "Laboratory"] + [""]},
            },
            "required": ["query_type"],
        },
    },
}

def parse_question_with_llm(question):
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=300,
        tools=[QUERY_TOOL],
        tool_choice={"type": "function", "function": {"name": "structured_query"}},
        messages=[{
            "role": "user",
            "content": f"Question: {question}\n\n"
                       f"If it asks about a lab/vital numeric value, set query_type='lab_metric' "
                       f"and pick the closest matching metric from the allowed list, plus agg. "
                       f"Never use event_type='Laboratory' for numeric value questions — "
                       f"those must use query_type='lab_metric'. "
                       f"If it asks about medications/admissions/ICU/diagnoses, set "
                       f"query_type='event_lookup' and pick the matching event_type. "
                       f"If neither fits, set query_type='unsupported'."
        }],
    )
    tool_call = resp.choices[0].message.tool_calls[0]
    return json.loads(tool_call.function.arguments)

def generate_grounded_response(question, retrieval_result):
    if retrieval_result["status"] == "abstained" or not retrieval_result["evidence"]:
        return f"Cannot answer — {retrieval_result.get('reason', 'no supporting record found.')}"

    evidence_json = json.dumps(retrieval_result["evidence"], default=str)

    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=200,
        messages=[
            {"role": "system", "content": (
                "You answer using ONLY the facts in the evidence JSON provided. "
                "Never state a number, date, or fact not present in the evidence. "
                "If the evidence is empty, respond exactly: "
                "'Cannot answer — no supporting record found.' "
                "Always mention the source_table and timestamp for traceability."
            )},
            {"role": "user", "content": f"Question: {question}\n\nEvidence: {evidence_json}\n\nAnswer concisely."},
        ],
    )
    return resp.choices[0].message.content

def llm_answer_question(question, subject_id):
    query = parse_question_with_llm(question)

    if query["query_type"] == "lab_metric" and query.get("metric") and query.get("agg"):
        result = retrieve_lab_metric(subject_id, query["metric"], query["agg"])
    elif query["query_type"] == "event_lookup" and query.get("event_type"):
        result = retrieve_event(subject_id, query["event_type"])
    else:
        result = {"status": "abstained", "evidence": [],
                  "reason": "Question doesn't match a supported query type."}

    answer_text = generate_grounded_response(question, result)
    return {"query": query, "retrieval": result, "answer": answer_text}

# =========================================================
# SIDEBAR — patient selector (shared across tabs)
# =========================================================
subject_ids = sorted(lab_qa_flagged["subject_id"].unique().tolist())
subject_id = st.sidebar.selectbox("Patient (subject_id)", subject_ids)

st.sidebar.markdown("---")
timeline_all = events_df[events_df["subject_id"] == subject_id]
lab_all = lab_qa_flagged[lab_qa_flagged["subject_id"] == subject_id]
flagged_pct = lab_all["quality_flag"].mean() if len(lab_all) and "quality_flag" in lab_all.columns else 0

st.sidebar.metric("Events indexed", len(timeline_all))
st.sidebar.metric("Source tables", timeline_all["source_table"].nunique())
st.sidebar.metric("Lab records flagged", f"{flagged_pct:.1%}")

# =========================================================
# TABS
# =========================================================
tab_record, tab_explorer = st.tabs(["Patient Record", "Ask Questions"])

# ---------------------------------------------------------
# TAB 1 — PATIENT RECORD (dashboard-style KPI cards + explained tables)
# ---------------------------------------------------------
with tab_record:
    admission_rows = timeline_all[timeline_all["event_type"] == "Admission"].sort_values("event_time")
    icu_rows = timeline_all[timeline_all["event_type"] == "ICU Stay"].sort_values("event_time")
    transfer_rows = timeline_all[timeline_all["event_type"] == "Transfer"].sort_values("event_time")
    dx_rows = timeline_all[timeline_all["event_type"] == "Diagnosis"]
    med_rows = timeline_all[timeline_all["event_type"] == "Medication"]
    flagged_count = int(lab_all.get("quality_flag", pd.Series(dtype=bool)).sum())
    icu_status = "Yes" if len(icu_rows) else "No"

    # ---- Work out the patient's current status badge ----
    timeline_ordered = timeline_all.sort_values("event_time")
    discharged = False
    if len(transfer_rows):
        last_transfer_desc = str(transfer_rows.iloc[-1]["description"]).lower()
        if "discharge" in last_transfer_desc:
            discharged = True

    if discharged:
        patient_status, status_class = "Discharged", "badge-green"
    elif len(icu_rows) and (not len(timeline_ordered) or timeline_ordered.iloc[-1]["event_type"] == "ICU Stay"):
        patient_status, status_class = "In ICU", "badge-red"
    elif len(admission_rows):
        patient_status, status_class = "Admitted", "badge-yellow"
    else:
        patient_status, status_class = "Status unknown", "badge-grey"

    # ---- Work out the admission type badge ----
    admission_type_text = "Not on record"
    admission_type_class = "badge-grey"
    if len(admission_rows):
        desc = str(admission_rows.iloc[0]["description"]).lower()
        if "emer" in desc or "ew" in desc:
            admission_type_text, admission_type_class = "Emergency", "badge-red"
        elif "elect" in desc:
            admission_type_text, admission_type_class = "Elective", "badge-green"
        elif "urg" in desc:
            admission_type_text, admission_type_class = "Urgent", "badge-yellow"
        else:
            admission_type_text, admission_type_class = admission_rows.iloc[0]["description"], "badge-grey"

    st.subheader(f"Patient {subject_id}")
    st.markdown(
        f'<span class="status-badge {status_class}">{patient_status}</span>'
        f'<span class="status-badge {admission_type_class}">{admission_type_text}</span>',
        unsafe_allow_html=True,
    )
    if len(admission_rows):
        st.caption(f"Admitted {admission_rows.iloc[0]['event_time']}, "
                   f"{admission_rows.iloc[0]['description']}")

    # ---- Patient facts strip, full width, compact horizontal bar ----
    info_row = patient_info[patient_info["subject_id"] == subject_id]

    if len(info_row):
        info_row = info_row.iloc[0]
        fact_items = [
            ("Gender", info_row.get("gender", "Not on record")),
            ("Age", info_row.get("anchor_age", "Not on record")),
            ("Admitted from", info_row.get("admission_location", "Not on record")),
            ("Discharged to", info_row.get("discharge_location", "Not on record")),
            ("Insurance", info_row.get("insurance", "Not on record")),
            ("Marital status", info_row.get("marital_status", "Not on record")),
            ("Race", info_row.get("race", "Not on record")),
            ("Language", info_row.get("language", "Not on record")),
        ]
        if info_row.get("hospital_expire_flag") == 1:
            fact_items.append(("Status", "Deceased during this stay"))

        strip_parts = "".join(
            f'<span style="margin-right:22px;"><span style="color:#8a8a92; font-size:12px;">{label}</span><br>'
            f'<span style="font-size:14px; font-weight:600; color:#1a1a2e;">{value}</span></span>'
            for label, value in fact_items
        )
        strip_html = textwrap.dedent(f"""\
        <div style="background:#F7F8FA; border:1px solid #E8E8EC; border-radius:10px;
                    padding:14px 18px; margin-bottom:18px; display:flex; flex-wrap:wrap; row-gap:12px;">
        {strip_parts}
        </div>
        """)
        st.markdown(strip_html, unsafe_allow_html=True)
    else:
        st.info("No demographic record found for this patient.")

    st.markdown("")

    # ---- KPI cards row (4 cards) ----
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="kpi-card kpi-blue">'
                    f'<div class="kpi-value">{len(timeline_all)}</div>'
                    f'<div class="kpi-label">Total records on file</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="kpi-card kpi-green">'
                    f'<div class="kpi-value">{len(lab_all)}</div>'
                    f'<div class="kpi-label">Lab tests recorded</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="kpi-card kpi-amber">'
                    f'<div class="kpi-value">{flagged_count}</div>'
                    f'<div class="kpi-label">Lab results flagged for review</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="kpi-card kpi-purple">'
                    f'<div class="kpi-value">{icu_status}</div>'
                    f'<div class="kpi-label">ICU stay on record</div></div>', unsafe_allow_html=True)

    st.markdown("")
    st.markdown("**Record types for this patient**")
    st.markdown(
        '<div class="table-note">Every event in this record falls into one of these categories. '
        'The count shows how many events of each type exist for this patient.</div>',
        unsafe_allow_html=True,
    )
    type_breakdown = (
        timeline_all["event_type"].value_counts().reset_index()
    )
    type_breakdown.columns = ["Record Type", "Count"]
    st.dataframe(type_breakdown, use_container_width=True, hide_index=True)

    st.markdown("")
    col_left, col_right = st.columns(2)

    # ---- Diagnoses table, explained ----
    with col_left:
        st.markdown("#### Diagnoses")
        st.markdown(
            '<div class="table-note">What this shows: every condition coded for this patient, '
            'pulled directly from the diagnoses_icd table. Each row is one diagnosis code, '
            'not a doctor\'s note, just the structured record.</div>',
            unsafe_allow_html=True,
        )
        if len(dx_rows):
            dx_table = dx_rows[["description", "source_id"]].drop_duplicates().rename(
                columns={"description": "Diagnosis", "source_id": "ICD Code Ref"}
            )
            st.dataframe(dx_table, use_container_width=True, hide_index=True)
        else:
            st.write("No diagnosis records found for this patient.")

    # ---- Medications table, explained ----
    with col_right:
        st.markdown("#### Medications")
        st.markdown(
            '<div class="table-note">What this shows: medications logged as administered, '
            'from the emar table. This confirms a dose was given, it does not reflect a '
            'prescription plan.</div>',
            unsafe_allow_html=True,
        )
        if len(med_rows):
            med_table = med_rows[["event_time", "description"]].drop_duplicates().rename(
                columns={"event_time": "Time", "description": "Medication"}
            )
            st.dataframe(med_table, use_container_width=True, hide_index=True)
        else:
            st.write("No medication records found for this patient.")

    st.markdown("")

    # ---- Lab results table, explained ----
    st.markdown("#### Latest Lab Results")
    st.markdown(
        '<div class="table-note">What this shows: the most recent recorded value for each lab '
        'test this patient has had, one row per test, sorted by date. Rows marked Flagged '
        'were caught by an automatic data quality check (missing unit, abnormal per the lab\'s '
        'own reference range, duplicate entry, or an implausible number). Flagged does not '
        'mean incorrect, it means it needs a human look before being relied on.</div>',
        unsafe_allow_html=True,
    )
    if len(lab_all):
        latest_labs = (
            lab_all.dropna(subset=["valuenum"])
            .sort_values("charttime")
            .groupby("label")
            .tail(1)
            .sort_values("charttime", ascending=False)
            .head(15)
            .copy()
        )
        def _lab_state(row):
            reason = str(row.get("quality_flag_reason", ""))
            if "implausible_value" in reason:
                return "Critical"
            if "lab_marked_abnormal" in reason:
                return "Abnormal"
            return "Normal"

        latest_labs["Status"] = latest_labs.apply(_lab_state, axis=1)
        display_labs = latest_labs[["label", "valuenum", "valueuom", "charttime", "Status"]].rename(
            columns={"label": "Test", "valuenum": "Value", "valueuom": "Unit", "charttime": "Recorded"}
        )
        st.dataframe(display_labs, use_container_width=True, hide_index=True)
    else:
        st.write("No lab results found for this patient.")

    st.markdown("")

    # ---- ICU vitals, explained ----
    st.markdown("#### Latest ICU Vitals")
    st.markdown(
        '<div class="table-note">What this shows: the most recent bedside reading for each '
        'core vital sign, from the ICU chartevents table. Only present if this patient had an '
        'ICU stay with recorded observations.</div>',
        unsafe_allow_html=True,
    )
    patient_vitals = vitals_df[vitals_df["subject_id"] == subject_id]
    if len(patient_vitals):
        latest_vitals = (
            patient_vitals.dropna(subset=["valuenum"])
            .sort_values("charttime")
            .groupby("label")
            .tail(1)
            .sort_values("charttime", ascending=False)
        )
        display_vitals = latest_vitals[["label", "valuenum", "valueuom", "charttime"]].rename(
            columns={"label": "Vital Sign", "valuenum": "Value", "valueuom": "Unit", "charttime": "Recorded"}
        )
        st.dataframe(display_vitals, use_container_width=True, hide_index=True)
    else:
        st.write("No ICU vitals recorded for this patient.")

# ---------------------------------------------------------
# TAB 2 — ASK QUESTIONS (Q&A + full timeline + flagged records)
# ---------------------------------------------------------
with tab_explorer:
    st.subheader(f"Patient {subject_id}")

    st.markdown("#### Ask a structured-data question")
    question = st.text_input("e.g. What was the highest creatinine value?")

    if question:
        if client is None:
            st.error("Cannot process question — no GROQ_API_KEY configured.")
        else:
            with st.spinner("Parsing question and retrieving evidence..."):
                out = llm_answer_question(question, subject_id)

            if out["retrieval"]["status"] == "answered":
                st.success(out["answer"])
            else:
                st.warning(out["answer"])

            with st.expander("Show parsed query + evidence"):
                st.json(out["query"])
                if out["retrieval"]["evidence"]:
                    st.dataframe(pd.DataFrame(out["retrieval"]["evidence"]))
                else:
                    st.write("No evidence returned.")

    st.markdown("#### Full timeline")
    st.markdown(
        '<div class="table-note">What this shows: every event for this patient, admissions, '
        'transfers, labs, medications, diagnoses, and ICU stays, merged from 6 separate MIMIC-IV '
        'tables into one time ordered list. The last two columns show exactly which source table '
        'and row each event came from, so any entry can be traced back and verified.</div>',
        unsafe_allow_html=True,
    )
    timeline_sorted = timeline_all.sort_values("event_time")
    st.dataframe(
        timeline_sorted[["event_time", "event_type", "description", "source_table", "source_id"]].rename(
            columns={"event_time": "Time", "event_type": "Type", "description": "Description",
                     "source_table": "Source Table", "source_id": "Source Row ID"}
        ),
        use_container_width=True,
    )

    st.markdown("#### Flagged lab records")
    st.markdown(
        '<div class="table-note">What this shows: lab results that failed one of four automatic '
        'quality checks (missing unit, marked abnormal by the lab, duplicate entry, or a value '
        'outside a plausible range). Nothing here has been changed or deleted, these are shown '
        'as is, flagged for a human reviewer to judge.</div>',
        unsafe_allow_html=True,
    )
    flagged = lab_all[lab_all.get("quality_flag", False) == True] if "quality_flag" in lab_all.columns else pd.DataFrame()
    if len(flagged):
        st.dataframe(
            flagged[["charttime", "label", "valuenum", "valueuom", "quality_flag_reason"]].rename(
                columns={"charttime": "Time", "label": "Test", "valuenum": "Value",
                         "valueuom": "Unit", "quality_flag_reason": "Why it's flagged"}
            ),
            use_container_width=True,
        )
    else:
        st.write("No flagged records for this patient.")