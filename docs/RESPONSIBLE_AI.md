# Responsible AI

*Research and educational prototype. Not for clinical use. Do not use for diagnosis, treatment, triage, or emergency decisions.*

## Who this is for

Researchers, educators, and healthcare data teams who want to explore structured MIMIC-IV data more easily. Not clinicians making decisions about actual patients — that's explicitly outside the intended use, both because the challenge itself scopes it that way and because the system just isn't built or tested for that.

## What this isn't for

Diagnosis, treatment planning, triage, or any kind of emergency decision — for anyone, real patient or not. It's also not meant to be generalized beyond this specific 100-patient sample; findings here don't tell you anything reliable about any other hospital, population, or time period. And obviously: no re-identifying patients, no combining this with outside patient data, no treating this as a stand-in for a clinician's judgment.

## Privacy

The dataset was already de-identified and date-shifted by PhysioNet before we ever touched it — we didn't build any de-identification ourselves, and this tool should never be pointed at data that hasn't already gone through that process. There are no free-text clinical notes anywhere in this pipeline, just structured, coded fields. When a question gets sent to the Groq API, only the small set of retrieved evidence rows needed to answer that specific question goes out — not a bulk export of anyone's record.

## Keeping it safe

The research-only warning is on the screen every time the app loads — not just mentioned in a README somewhere. The system never generates a diagnosis, a treatment suggestion, or a risk score; all it does is show existing coded facts and explain them in a sentence. It's read-only — nothing in this app writes to or modifies a patient's record.

## On hallucination, honestly

The model is instructed, by prompt, to only state facts that are actually present in the retrieved evidence, and it's simply not invoked at all when there's no evidence to work from. That cuts the risk down a lot. It doesn't eliminate it — a prompt instruction is a strong nudge, not a hard guarantee, and we haven't run the kind of adversarial testing that would let us say "this can't be broken." What we can say is that in the testing we did, we didn't see it state anything that wasn't backed by the evidence shown next to it. Treat every AI-written sentence as a claim worth checking against its evidence, not as something to take on faith.

## Showing the work

Every piece of evidence carries its source table, its row, and its timestamp, and the app shows this right next to every answer — you don't have to trust the sentence, you can go look at what it's based on. The full timeline works the same way. This is intentional: the actual patient data is the source of truth here, not the model. The model's job is narrowly scoped to interpreting your question and explaining what was found.

## When it won't answer

The system says "cannot answer" — with a specific reason — any time it doesn't have solid ground to stand on: an unrecognized metric or event type, no numeric evidence, evidence that's all flagged as implausible, no matching records, or a question that just doesn't fit anything it knows how to look up. This isn't the model being cautious on its own judgment — these are fixed rules that fire before an answer ever gets generated.

## Humans still need to check this

Nothing here is meant to replace a person looking at the data. Every fact comes with its source so someone can verify or reject it. Flagged lab results are shown as-is, specifically so a human can decide what to make of them — the system never quietly fixes or removes anything.

## The honest limitations list

This is a small, single-hospital sample — 100 patients — and nothing here should be read as clinically valid, fair across subgroups, or generalizable, because it genuinely isn't tested for any of that. Coverage of some data types is partial; not every patient has medication records, for instance, and the app correctly reports that as "nothing found" rather than guessing why.

The one we want to be really clear about: **the app currently doesn't separate a patient's different hospital admissions from each other.** Most patients here were admitted more than once, and viewing a "timeline" without picking one specific visit means events from unrelated hospital stays can appear merged together. We know this, we're saying so here rather than glossing over it, and it's the top thing on the list to fix. We chose not to rush a change into a working app this late in the process — better to be upfront about a known gap than ship a half-tested fix under time pressure.

We also haven't run a formal, numeric evaluation of accuracy or hallucination rate (see `docs/EVALUATION.md`) — what confidence we have comes from manual spot-checking, not statistical testing. And the plausible-value ranges used to flag suspicious lab results are a rough heuristic for seven common tests, not a clinically validated reference — a flag means "worth a second look," not "wrong," and no flag doesn't mean "clinically normal."
