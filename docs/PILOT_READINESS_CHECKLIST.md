# Pilot readiness checklist — estimator rule validation

Positioning: **AI-assisted Automated Quantity Takeoff and BOQ System.** The deterministic engine is the source of
truth for quantities; the AI layer only reads application data. Nothing in the application claims production
accuracy, time savings, complete automation, real revision-set validation or estimating without human review.

## Baseline (2026-10-08, before the rule-validation changes)

| | Ramzi | Al-Kawari | Al-Sulaiti |
|---|---|---|---|
| BOQ lines | 79 | 82 | 76 |
| Calculated / Estimated | 0 | 0 | 0 |
| Lump Sum / Excluded | 8 | 8 | 8 |
| Measured, needs review | 3 | 3 | 2 |
| Candidate quantities — rule undecided | 26 | 42 | 35 |
| Needs review — no quantity yet | 20 | 8 | 8 |
| Missing information | 22 | 21 | 23 |
| Lines carrying candidates (incl. Missing lines) | 28 | 44 | 37 |
| Historical benchmark | — | Within 1 · Difference 2 · Candidates 24 · Unable 29 | Within 1 · Difference 1 · Candidates 24 · Unable 35 |

Methodology rules: 22 — 18 UNKNOWN, 3 INFERRED (footing volume, ground-beam volume, removal = excavation),
1 ASSUMED (storey level per floor), 0 CONFIRMED. Tests: 84 passing.

Known extraction facts: Ramzi slabs detected, door/window locations detected but sizes not extracted; Al-Kawari
13 slab elements missing thickness; Al-Sulaiti slabs not detected (boundaries too sparse), so both beam-depth options
give 89.29 m³ (explained on the rule card); annex extraction incomplete. Benchmark examples: Al-Kawari ground beams
+1.2 %, Al-Sulaiti footings −4.4 %, footings −4 % to −9 %, Al-Sulaiti ground/tie beams −90.5 %.

## Checklist (verified 2026-10-08)

| Area | Check | Result | How verified |
|---|---|---|---|
| Data | New project can be created | ✅ | New Project page; `test_new_project_from_uploaded_drawings` (an empty user-created project "abc" shows as Not processed) |
| Data | Drawings can be uploaded | ✅ | `/upload/{kind}` endpoint (zip extraction) — UI present; end-to-end upload done by the processing test from a folder |
| Data | Processing completes | ✅ | Processing page + `qto_cli.py run`; 80/80 files on each reference project |
| Data | Failed drawings visible | ✅ | Drawings tab status column (Measured / Inventoried / Failed); processing summary export |
| Data | Missing information visible | ✅ | BOQ "Missing" status + reasons; dashboard Attention list; assistant "What information is missing?" |
| Quantity | Elements extracted / quantities calculated | ✅ | Elements + Quantity takeoff tabs; 84 regression/unit tests |
| Quantity | Candidate quantities visible | ✅ | BOQ evidence panel, Rule Approval option impacts |
| Quantity | Missing dimensions visible | ✅ | Review queue "Missing dimensions"; elements with "n/a" listed first in the BOQ evidence panel |
| Quantity | Evidence available | ✅ | Drawing → element → dimensions → formula → rule → status in panels; Drawing button highlights the element |
| BOQ | Static Group structure reproduced | ✅ | Static Group BOQ tab and `static-boq` export (sections A–F) |
| BOQ | Statuses correct | ✅ | Calculated only when every rule is CONFIRMED (`test_assumed_or_inferred_rule_is_never_calculated`) |
| BOQ | Export works | ✅ | All 5 exports × 3 projects downloaded and re-opened with openpyxl |
| BOQ | No unconfirmed quantity presented as final | ✅ | Candidate-only lines have blank QTY; measured lines carry "Needs Review" in the export and UI |
| Rules | 22 rules visible with question, status, evidence, options, impact, why it matters | ✅ | Rule Approval cards |
| Rules | Approval audited (rule, previous/new status, option, user, time, comment, affected lines) | ✅ | `rule_approve` + `rule_decision_impact` audit events (`test_rule_approval_recalculates_benchmarks_and_audits`) |
| Rules | Recalculation works (BOQ lines, statuses, benchmark, review items) | ✅ | Same test, on an isolated copy of Al-Kawari |
| Rules | "Keep unconfirmed" changes nothing but a note | ✅ | `test_keep_unconfirmed_note_changes_nothing`; wording on the card |
| Review | Approve / Resolve / Reject / Reopen work and are audited | ✅ | Isolated run of the review endpoint (all four states persisted with user/comment; invalid state refused) |
| Review | Corrections audited | ✅ | Slab thickness correction → `override_changed` audit + recalculation (isolated run) |
| AI | Supported questions answer from data with sources | ✅ | Attention, missing information, beam difference, BOQ items needing review, what changed, management summary |
| AI | Unsupported questions are not answered | ✅ | Returns the list of answerable questions, no citations |
| Management | Dashboard, Automation readiness, daily report, benchmark | ✅ | Browser QA at 1440 / 1280 / 1024 px |
| Revision | Revision comparison | ⚠️ | Implemented; **not yet validated on a real revised drawing set** |

## Estimator validation procedure (added 2026-10-08)

1. Rule Approval → **Start validation session** (estimator name, scope). One session open at a time.
2. Work through the cards ("Remaining in session" filter). Each card shows rule ID, question, state
   (Unknown / Inferred / Assumed / Confirmed), historical evidence, options with the quantity on every project,
   lines and projects affected, why it matters and what happens if it stays unconfirmed.
3. For each rule: **Approve rule** (selected option → CONFIRMED), **Keep unconfirmed** (note only, nothing
   changes), **Add note**, or **Reject / Reopen** (back to UNKNOWN). The system never selects an option.
4. Approve / reject recalculates only projects whose BOQ uses the rule, refreshes their benchmarks and records
   `rule_decision` (old/new status and option, user, comment, session) and `rule_decision_impact` (old/new value
   and status of every affected BOQ line, benchmark summary before/after) in the audit trail.
5. **Finish session** freezes the summary: reviewed, confirmed, rejected, kept unconfirmed, still unresolved,
   projects recalculated, BOQ lines changed, benchmark changes, notes.

## Live-pilot measurement (added 2026-10-08)

Project → **Pilot** tab (`data/projects/<pid>/pilot.json`, audited): manual take-off / BOQ / review hours,
manually found missing items and corrections, estimator review hours, accepted / rejected quantities, manual
quantities per BOQ item, revision handling. Automated values are read from the application (processing and
calculation run durations, BOQ generation time, statuses, missing lines, audited corrections). Differences are
shown only where both values exist; no accuracy percentage or time-saving figure is produced. Revision state:
**Implemented — Real Revised Drawing Validation Pending.**

Test data: the empty test project "abc" (no drawings) is **archived** — kept on disk, excluded from KPIs, the
daily report and the assistant, restorable from Projects → Archived projects (audited).

## Final verification (2026-10-08)

- **Current state: READY FOR ESTIMATOR VALIDATION.**
- **Not yet ready for live pilot** because the 22 methodology decisions still require estimator confirmation,
  project inputs remain incomplete, extraction gaps remain, real revised drawing validation is pending and an unseen
  live tender has not yet been measured.
- **Not production ready** because no real estimator validation and no unseen-project accuracy/time study have been
  completed yet.
- Test suite: 98 tests, 82 s under normal conditions (76 s with browser QA running concurrently). The single
  32-minute run was caused by the laptop entering Modern Standby one minute after the run started (Windows
  Kernel-Power events 14:21 → 14:51); not a test or infrastructure problem.
- Estimator session flow (start, open rule, evidence, approve / reject / finish dialogs and their cancellation, real
  approval, keep-unconfirmed, finish) was exercised on a disposable copy of the data; cancelling changes nothing and
  the stored `rule_decision` / `rule_decision_impact` records contain every required field. Real data was
  fingerprinted before and after and is unchanged.
- Fixed during verification: a navigation race (switching project or clicking quickly while a slow page loaded could
  let the older page render over the newer one). Superseded page loads are now discarded.

## Controlled live test (added 2026-10-08) — project → Validation tab

The engine proposes; the estimator decides. Per measurable BOQ line: **ACCEPT** (approves the AI quantity; not
possible when there is no AI quantity, e.g. UNKNOWN rule), **CORRECT** (estimator quantity + comment; AI quantity
and variance stored), **REJECT** (reason required), **KEEP UNCONFIRMED** (no quantity). Decisions never change rules,
engine results, benchmarks or baselines; a decision made on an older AI result is flagged *stale*. Each decision is
audited (`line_decision`: rules and their status/option, user, comment, session, version, line, previous/new
quantity and line status, benchmark before/after) and counted in the open validation session.

* Drawing register: number / title parsed from file names (labelled), revision "not recorded" until entered from
  the title block; upload timestamps recorded for uploaded files. Reading never writes; edits are audited.
* Baselines: created from the Static Group historical BOQ, an imported client BOQ, or estimator-approved
  quantities; written once (exclusive create), never overwritten; carry quantity, revision, source, timestamp.
* Revision comparison: baseline vs latest run per line — baseline qty, new AI qty, delta, estimator qty, variance,
  status, rule, evidence, drawing revisions; additions, omissions, changes and not-comparable lines are listed.
* Metrics (preliminary): proposed / accepted / corrected / rejected / unconfirmed / stale lines, mean / median / max
  absolute variance of CORRECT decisions against an AI quantity, rules validated / UNKNOWN, review hours if entered.
* Validation dependencies are listed per project (live project, revisions, baseline, ground level, tanks,
  boundary wall, rules, manual take-off).

## Open before a live-tender pilot (not blockers for rule validation)

1. Estimator decisions on the 22 methodology rules (Rule Approval page).
2. Real revised drawing set to validate revision comparison.
3. Extraction gaps: annex buildings, parapets, door/window sizes, Al-Sulaiti slab boundaries and tie-beam depths.
4. Project inputs per project: ground level, tank sizes, boundary-wall section.
5. Manual vs automated take-off timing on a live tender (no time-saving claim until measured).
