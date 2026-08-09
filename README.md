# Patient Timeline & Evidence Retrieval

A research and educational prototype built on the MIMIC-IV Clinical
Database Demo v2.2, for the "AI for Smarter Patient Care" hackathon,
Track 1: Structured Patient Timeline & Evidence Retrieval.

## What this is

A tool that reconstructs a patient's hospital stay from six separate
relational tables into one time-ordered, source-traced record, and
answers structured questions about it, either with a verifiable answer
or an honest abstain, never a guess.

## Folder structure

```
.
├── app.py                  Streamlit app (the actual prototype)
├── requirements.txt
├── .env.example             Template for the required API key
├── notebooks/
│   └── AI_for_Smarter_Patient_Care.ipynb   Full data pipeline, annotated
├── data/                    Exported CSVs the app reads directly
│   ├── events_df.csv
│   ├── lab_qa_flagged.csv
│   ├── patient_info.csv
│   └── vitals_df.csv
└── docs/
    ├── SAFETY_AND_DATA_STATEMENT.md
    └── evaluation_report.md
```

## Target user

Clinical-data researchers, educators, and healthcare data teams.
Not clinicians making patient-care decisions.

## How it works

1. **Notebook** (`notebooks/`) loads the raw MIMIC-IV demo tables, checks
   referential integrity, normalizes timestamps, and builds one unified,
   time-sorted event table with full source provenance on every row.
2. Lab results get four explainable data-quality flags (missing unit,
   lab-marked abnormal, duplicate entry, implausible value). Nothing is
   ever silently corrected or deleted, only tagged.
3. A set of retrieval functions answer structured questions, constrained
   to a whitelist of metrics and event types that actually exist in the
   data, and abstain by default.
4. An LLM (Llama 3.3 70B via Groq) wraps those functions: it parses a
   free-text question into a structured query and phrases the returned
   evidence into a sentence. It never generates a fact on its own.
5. `app.py` is the Streamlit UI: a per-patient record view and a
   question-answering view, both with visible source citations.

## AI disclosure

LLM: Llama 3.3 70B, via the Groq API, free tier. Used only for question
parsing and answer phrasing, never for retrieving data. See
`docs/SAFETY_AND_DATA_STATEMENT.md` for the full breakdown.

## Run locally

```
pip install -r requirements.txt
```

Create a `.env` file in the project root (copy `.env.example`) with:

```
GROQ_API_KEY=your_key_here
```

Then:

```
streamlit run app.py
```

## Deploy

Push this repository to GitHub, connect it at
[share.streamlit.io](https://share.streamlit.io), and add `GROQ_API_KEY`
under Settings → Secrets.

## Dataset

MIMIC-IV Clinical Database Demo v2.2 (organizer-supplied frozen copy),
100 patients, deidentified, date-shifted, from one tertiary academic
medical center in Boston. Not sufficient to establish clinical validity,
subgroup fairness, or real-world performance. Cite:
https://physionet.org/content/mimic-iv-demo/2.2/
