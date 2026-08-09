# AI for Smarter Patient Care

**Track 1 — Structured Patient Timeline & Evidence Retrieval**
Research and educational prototype only. Not for clinical use. Do not use for diagnosis, treatment, triage, or emergency decisions.

## Overview

AI for Smarter Patient Care turns a patient's fragmented, multi-table hospital record into one unified, time-ordered clinical timeline, and lets a user ask plain-language questions about that record. Every answer is generated from evidence retrieved directly from the source data — never from the language model's own knowledge — and the system explicitly says "cannot answer" when the record does not support a question.

## The Problem

A single hospital stay in MIMIC-IV is spread across separate tables: admissions, transfers, laboratory results, medication administrations, diagnoses, and ICU observations. Reconstructing "what happened to this patient, and when" means manually joining six relational tables, reconciling timestamps, and cross-checking units and data-quality issues by hand. This is slow, error-prone, and easy to get wrong — for example, mixing events from two separate hospital admissions into what looks like one continuous story. For researchers and clinical-data teams, that friction makes it hard to trust, verify, or reuse structured hospital data.

## Our Solution

The application ingests six MIMIC-IV Clinical Database Demo v2.2 tables (`admissions`, `transfers`, `icustays`, `labevents`, `emar`, `diagnoses_icd`) and normalizes them into one unified event table (`events_df`) with a common schema: `subject_id`, `hadm_id`, `stay_id`, `event_time`, `event_type`, `description`, `source_table`, `source_id`. A user selects a patient, sees a dashboard-style clinical record (status, demographics, diagnoses, medications, labs, ICU vitals), and can ask a free-text question. The question is parsed into a structured lookup, answered from retrieved evidence rows (never from the model's own knowledge), and every returned fact is traceable back to its exact source table and row.

## Key Features

Only features verified in the current code (`app.py`, the processing notebook) are listed here.

- **Unified patient timeline** — six MIMIC-IV tables merged into one chronological event feed per patient, with `source_table`/`source_id` on every row for traceability.
- **Patient Record dashboard** — status badge (Admitted / In ICU / Discharged), admission-type badge, demographic facts strip, KPI cards (total records, lab tests, flagged labs, ICU stay), diagnoses table, medications table, latest-lab-per-test table, latest-ICU-vitals table.
- **AI-powered clinical question answering** — free-text question → LLM-driven structured-query parser (Groq `llama-3.3-70b-versatile`, forced tool call) → deterministic evidence retrieval → LLM synthesis of the final sentence, constrained to only the retrieved evidence.
- **Evidence-grounded responses** — the parsed query and the exact evidence rows used to answer are shown in an expander next to every answer.
- **Deterministic retrieval for lab values and events** — "latest / highest / lowest" lab questions and medication/diagnosis/ICU/admission/transfer lookups are answered by pandas aggregation functions (`retrieve_lab_metric`, `retrieve_event`), not by LLM generation.
- **Abstention on insufficient evidence** — the system returns "Cannot answer" (rather than guessing) when: the requested metric/event type isn't recognized, no numeric records exist for a metric, all matching lab records are flagged implausible, no matching events exist, or the question doesn't map to a supported query type.
- **Laboratory data-quality flagging** — every lab result is checked for four issues (missing unit, lab-marked-abnormal, duplicate result, implausible value against a hard-coded physiological range) and flagged records are shown in a dedicated, unmodified table — nothing is silently corrected or deleted.
- **Full traceable timeline view** — every event for the selected patient, sorted chronologically, with source table and source row ID visible for verification.
- **Prominent safety banner** — the research-only / not-for-clinical-use disclaimer is shown at the top of every page load.

## How It Works

```mermaid
flowchart TD
    A[MIMIC-IV Demo v2.2 tables<br/>admissions, transfers, icustays,<br/>labevents, emar, diagnoses_icd] --> B[Normalization<br/>timestamp parsing, schema alignment]
    B --> C[Unified Clinical Timeline<br/>events_df: one row per event,<br/>sorted by subject_id + event_time]
    C --> D[Patient Record Dashboard<br/>status, demographics, KPIs,<br/>diagnoses, meds, labs, vitals]
    C --> E[Clinical Question Parser<br/>Groq LLM, forced tool call →<br/>structured_query]
    E --> F[Deterministic Retrieval<br/>retrieve_lab_metric / retrieve_event<br/>pandas filter + aggregate]
    F --> G{Evidence found?}
    G -- No --> H[Abstain:<br/>"Cannot answer — reason"]
    G -- Yes --> I[LLM Synthesis<br/>answers ONLY from evidence JSON,<br/>cites source_table + timestamp]
    I --> J[Grounded Answer + Evidence Table]
    H --> J
    J --> K[User]
    D --> K
```

## AI / Clinical QA Architecture

```
Question
  → Interpretation        (LLM forced tool-call → structured_query: query_type, metric, agg, event_type)
  → Timeline filtering     (subset events_df / lab_qa_flagged by subject_id, metric, or event_type)
  → Deterministic aggregation (max / min / latest lab value, or full event list — pandas, not LLM)
  → Evidence check         (empty or all-implausible → abstain with a stated reason)
  → LLM synthesis          (system prompt restricts the model to facts in the evidence JSON only)
  → Evidence-backed response (answer text + visible parsed query + evidence table)
```

The LLM has two narrow jobs: (1) map a free-text question to one of a fixed, enumerated set of metrics/event types (it cannot invent a metric name — the tool schema's `enum` is built from the real data), and (2) phrase the retrieved evidence into a sentence, under a system prompt that forbids stating any number, date, or fact not present in the evidence JSON. The underlying patient evidence — not the LLM — is the source of truth; the LLM is a synthesis and interpretation layer on top of it.

## Dataset

MIMIC-IV Clinical Database Demo v2.2 (organizer-supplied, de-identified).

| Metric | Value |
|---|---|
| Patients | 100 |
| Total clinical events (unified timeline) | 149,673 |
| Laboratory events | 107,727 |
| Medication events | 35,835 |
| Diagnosis events | 4,506 |
| Transfer events | 1,190 |
| Admission events | 275 |
| ICU Stay events | 140 |

These figures are as supplied for this project; no additional statistics are claimed beyond what is stated above. Note: 100 patients across 275 admissions means most patients have multiple hospital visits (see **Safety & Limitations** for the admission-scoping caveat).

## Technology Stack

- **Python 3** / **pandas** — data loading, normalization, and the unified timeline
- **Streamlit** — web application UI (`app.py`)
- **Groq API** (`llama-3.3-70b-versatile`, via the `groq` Python SDK) — structured-query parsing (forced tool call) and grounded-answer synthesis
- **python-dotenv** — local environment variable loading
- **Jupyter Notebook** — data processing / pipeline development (`AI_for_Smarter_Patient_Care_CORRECTED.ipynb`)

No vector database, embeddings, or RAG framework is used — retrieval is deterministic pandas filtering/aggregation over the unified event table, not similarity search.

## Example Questions

Verified against the implemented query types (`lab_metric` and `event_lookup`):

- "What was the patient's highest recorded creatinine value?"
- "What was the latest hemoglobin result?"
- "What medications was the patient given?"
- "What diagnoses were recorded for this patient?"
- "Did this patient have an ICU stay?"

Questions outside these two categories (e.g., open-ended "what happened during this hospitalization," free-text symptom questions, or anything requiring clinical judgment) are classified `unsupported` and the system abstains rather than guessing.

## Safety & Limitations

- **Research and educational prototype only. Not for clinical use.** Do not use for diagnosis, treatment, triage, or emergency decisions. This banner is shown on every page load in the app.
- **Not validated for clinical accuracy, generalizability, or patient outcomes.** 100 patients is a small, non-representative sample; nothing here should be read as a clinical or operational claim.
- **The LLM never states a fact that isn't in the retrieved evidence** (by system-prompt constraint), and the system abstains outright when no evidence is found — but a system prompt is not a formal guarantee. Manual testing (see `docs/EVALUATION.md`) found no hallucinated values, but no adversarial or quantitative hallucination audit has been run.
- **Known gap — admission (`hadm_id`) scoping is not enforced in the deployed app.** The processing notebook explicitly documents that ~100 patients span 275 admissions and that timelines "must be scoped by `hadm_id` to prevent mixing data from separate hospitalizations." The unified `events_df` carries `hadm_id` on every row, but the current `app.py` selects only by `subject_id` — the Patient Record and full-timeline views merge all of a patient's admissions together. For patients with more than one hospitalization, this can present events from unrelated visits as one continuous story. This is the single highest-priority fix before relying on the timeline view for multi-admission patients (see `docs/EVALUATION.md` and `docs/SUBMISSION_CHECKLIST.md`).
- **EMAR (medication) coverage is partial.** Not every patient has medication records; the app correctly shows "No medication records found" rather than fabricating one, but a user unfamiliar with the dataset could mistake this for a data-loading bug.
- **Procedures are not currently part of the unified timeline** — the event table covers admissions, transfers, ICU stays, labs, medications, and diagnoses, but not `procedures_icd`.
- **De-identification**: performed upstream by PhysioNet as part of the MIMIC-IV Demo release (date-shifted timestamps, removed identifiers); this application does not perform its own de-identification and must not be pointed at non-de-identified data.
- **Human oversight is required.** Every AI-generated answer displays its underlying evidence so a human can verify it before relying on it; the app does not take, recommend, or automate any clinical action.

## Installation

```bash
git clone <your-repo-url>
cd <repo-directory>
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

You also need the processed CSVs in the project root (produced by running the notebook's data pipeline against the MIMIC-IV Demo v2.2 `hosp/` and `icu/` folders):

- `events_df.csv`
- `lab_qa_flagged.csv`
- `patient_info.csv`
- `vitals_df.csv`

Run `AI_for_Smarter_Patient_Care_CORRECTED.ipynb` end-to-end once (with the MIMIC-IV Demo v2.2 data available under `data/mimic-iv-clinical-database-demo-2.2/`) to generate these four files, then place them alongside `app.py`.

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | Yes, for the Q&A tab | Groq API key used for question parsing and grounded-answer synthesis. Without it the app still runs — the Patient Record dashboard works fully — but the "Ask Questions" tab shows a clear warning instead of crashing. |

Set locally via a `.env` file (see `.env.example`) or, on Streamlit Community Cloud, under **Settings → Secrets**. Never commit a real key to the repository.

## Running Locally

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (typically `http://localhost:8501`).

## Deployment

Not verified in the materials supplied for this audit — no deployment platform, build configuration, or live URL was included in the reviewed files. If the app is deployed on Streamlit Community Cloud, document the exact app URL and secret configuration here before submission; otherwise state that the demo will be run locally.

## Project Structure

```
README.md
app.py
requirements.txt
.env.example
AI_for_Smarter_Patient_Care_CORRECTED.ipynb   # data pipeline: load → normalize → unify → QA-flag → retrieval → LLM layer
docs/
  ARCHITECTURE.md
  EVALUATION.md
  RESPONSIBLE_AI.md
  SUBMISSION_CHECKLIST.md
  images/
    dashboard.png
    patient-timeline.png
    ai-answer.png
    evidence.png
data/                                          # MIMIC-IV Demo v2.2 (not included; obtain via PhysioNet)
  mimic-iv-clinical-database-demo-2.2/
    hosp/
    icu/
events_df.csv           # generated by the notebook
lab_qa_flagged.csv       # generated by the notebook
patient_info.csv         # generated by the notebook
vitals_df.csv            # generated by the notebook
```

`tests/` is not included here because no automated test suite exists in the reviewed materials (see `docs/EVALUATION.md` for how the system was actually checked).

## Evaluation

See `docs/EVALUATION.md` for the full write-up. In short: this is **manual, scenario-based testing**, not a quantitative benchmark. The notebook (`Cell 64`) runs three representative questions end-to-end (a supported lab question, a supported medication question, and an out-of-scope question) and confirms the abstention path fires correctly on the unsupported one. No accuracy, precision/recall, or hallucination-rate numbers are reported because no ground-truth answer set or automated evaluation harness currently exists — inventing such numbers would misrepresent the project.

## Future Improvements

Clearly separated from what is implemented today:

- Enforce `hadm_id` (single-admission) scoping in the UI and in the Q&A retrieval functions, so a user explicitly picks one hospitalization before viewing a timeline or asking a question — closing the gap described in **Safety & Limitations**.
- Add `procedures_icd` as a seventh event type in the unified timeline.
- Build a small labeled evaluation set (question → expected metric/event_type → expected evidence rows) to move from manual spot-checks to a repeatable, quantitative evaluation harness.
- Add automated tests around `retrieve_lab_metric` / `retrieve_event` abstention logic.
- Add a visible "last updated" / data-vintage indicator and an explicit cohort/admission picker for Track 2-style exploration.

## Screenshots / Demo

See `docs/SUBMISSION_CHECKLIST.md` and the **Screenshot Plan** provided separately for exactly which screens to capture. Save screenshots to `docs/images/` using the filenames below before publishing this README with images embedded.

### 1. Clinical Dashboard
`docs/images/dashboard.png`

The Patient Record tab: status badge, demographic strip, and the four KPI cards. This is the five-second "what is this product" shot — a judge should immediately see a real clinical record, not a chatbot window.

### 2. Patient Timeline
`docs/images/patient-timeline.png`

The full timeline table in the Ask Questions tab, showing events from six source tables merged into one chronological, traceable list — the core "fragmentation solved" moment.

### 3. AI Clinical Question Answering
`docs/images/ai-answer.png`

A supported question (e.g. "What was the highest creatinine value?") with its grounded answer displayed.

### 4. Evidence / Supporting Records
`docs/images/evidence.png`

The expanded "Show parsed query + evidence" panel for the same question, showing the exact source row(s) the answer is grounded in.

### 5. Additional Analytics
Not included — no additional analytics view beyond the dashboard and timeline currently exists in the implementation.

---

*This project uses the MIMIC-IV Clinical Database Demo v2.2 (https://physionet.org/content/mimic-iv-demo/2.2/, DOI: https://doi.org/10.13026/dp1f-ex47), an openly available, de-identified subset of MIMIC-IV, in accordance with the PhysioNet license and attribution requirements.*
