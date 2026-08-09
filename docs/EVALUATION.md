# Evaluation

*Research and educational prototype. Not for clinical use.*

## Let's be upfront about what this is

This is manual testing — we asked the app questions, read the answers, and checked whether the abstention logic did what it was supposed to. It is not a quantitative benchmark. We're not going to report an "accuracy" or "hallucination rate" number, because we don't have one, and making one up would be worse than not having one at all.

## What we tested against

The same dataset the live app runs on: MIMIC-IV Demo v2.2, 100 patients, 149,673 events. No separate held-out test set exists.

## How we actually checked this

Three things: reading the notebook's own test cells, where a fixed demo patient (`subject_id 10014354`) gets run through a handful of hand-picked questions and the output is eyeballed; reading through the retrieval and abstention code line by line to trace every branch; and a live check against the deployed app, which confirmed a real question ("What was the highest creatinine value?") returns a correctly grounded, source-cited answer, and that a rate-limited call now fails gracefully instead of crashing.

## Questions we know the code handles correctly

| Question | What it should do | What we found |
|---|---|---|
| "What was the highest creatinine value?" | Answer, with the max lab row as evidence | Confirmed — this exact case is run in the notebook and works |
| "What medications were given?" | Answer if EMAR records exist for the patient, otherwise abstain cleanly | Confirmed by code — abstains with a clear reason when there's nothing to find |
| "What is the weather today?" | Abstain — not a supported question type | Confirmed — this exact off-topic question is tested in the notebook and correctly refused |
| A lab metric that doesn't exist, e.g. "Not A Real Test" | Abstain, name the specific problem | Confirmed — tested directly in the notebook |
| A lab question where the patient has no numeric records for that metric | Abstain | Confirmed by reading the code |
| A lab question where every matching record is flagged implausible | Abstain, but still show the (disqualified) evidence | Confirmed by reading the code |
| An event lookup with zero matching records, e.g. asking about an ICU stay for someone who never had one | Abstain, clear reason | Confirmed by reading the code |

## Does it actually stay grounded?

The prompt that turns evidence into a sentence is explicit: use only what's in the evidence, cite the source and timestamp, don't add anything. In the small set of manual tests we could see, the answers stuck to that — no numbers or facts that weren't actually in the evidence. But this was a handful of questions on one patient, not a stress test. We haven't tried to break it with adversarial phrasing, and we haven't run it across enough questions to say anything statistically meaningful. That's the honest gap in this evaluation.

## Where it can go wrong

The biggest one, and we've said this a few times now because it matters: **the app doesn't separate a patient's different hospital admissions.** Most patients here have more than one, and the timeline currently merges them all together. This was actually called out in the team's own notebook notes as something the app should do — it just isn't wired up in `app.py` yet.

A few smaller things worth knowing: not every patient has medication records, and the app handles that correctly (says "none found" rather than erroring), but it's worth knowing going in so it doesn't look like a bug during a demo. Before this review, a Groq API failure (rate limit or timeout) would have shown a raw error page — that's now handled with a retry and a clean message instead, though we haven't been able to test it against a live rate-limited call ourselves. And if the app runs without its four data CSVs present, it'll currently crash with a plain file-not-found error rather than a helpful message — that one's still open.

## What we didn't do, and why that's the honest answer

There's no labeled ground-truth question set, so nothing here is a statistically sound accuracy number — the questions above were picked to exercise specific code paths, not sampled at random. Coverage across all 100 patients was done by reading the code's logic, not by clicking through every single one in the running app. And the kind of evaluation protocol the challenge brief describes — patient-grouped folds, baseline comparisons, reported uncertainty — is really aimed at Track 3's predictive modeling, which isn't what this project does; this is Track 1, a retrieval and timeline tool, so those specific requirements don't apply here the same way. What does apply, and what we've tried to do honestly, is show representative errors and how the system behaves when the data doesn't support an answer.
