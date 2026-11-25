# 07b — ML Templates (Model Card, Datasheet, Evaluation Report, Labelling Guide Outline)

> **Quick reference:** copy these into `docs/ml/` when creating a model or dataset. Every field is mandatory unless marked optional. Unknown values are written `NOT YET MEASURED` / `UNKNOWN` — never guessed.

## 1. Model card template (`docs/ml/model-cards/<model>.md`)

```markdown
# Model card — <name> <version>
- **Kind:** detector | staff_classifier | state_calibrator
- **Base model & licence:** <e.g., RF-DETR Small — Apache-2.0 (verified <date> at <url>)>
- **Weights licence:** <Apache-2.0 | other> — reason: <all training data licences permit…>
- **Artifact:** <path>, SHA-256 <hash>, format ONNX <opset>, size <MB>
- **Git commit / config:** <hash> / <config file>
- **Training data:** <dataset id + DVC hash>, n clips, venues, date range, synthetic share
- **Splits:** <splits.json SHA-256>

## Intended use
Estimate table occupancy/cleaning state and counts from fixed restaurant cameras to support staff decisions.
## Out-of-scope / prohibited use
Face recognition or any biometric processing; demographic inference; evaluating or ranking individual employees/customers; covert surveillance; legal decisions about individuals.

## Metrics (all from eval_report.json; **NOT YET MEASURED** if absent)
| Metric | Value | 95% CI | n (intervals/clips) | Dataset/split |
|---|---|---|---|---|
| TSM-F1 (primary) | | | | T-unseen |
| Per-class F1 | | | | |
| Event F1 / timing error | | | | |
| Staff F1 / customer→staff | | | | |
| ECE / coverage | | | | |
| AP50 person / recall in ROI | | | | |
| Latency p50/p95 (hardware) | | | | |

## Baseline comparison
(B0–B4 table with CIs and paired-test result)
## Segment results
(lighting × angle × density × occlusion × resolution × venue × proxy groups; mark n<50 "insufficient data")
## Error analysis
(top-10 failure modes with counts, blurred examples, decisions)
## Known limitations & unsupported conditions
## Fairness/robustness notes (proxy groups; no demographic attributes)
## Calibration & abstention thresholds
## Monitoring plan & retraining triggers
## Environmental/compute note (optional)
## Contact / change log
```

## 2. Datasheet template (`docs/ml/datasheets/<dataset>.md`)

```markdown
# Datasheet — <dataset id> <version>
1. **Motivation:** why created, by whom, funding (optional)
2. **Composition:** venues, cameras, hours, clips, frames; labels; class balance per split; synthetic share; known gaps
3. **Collection process:** devices, sampling, dates, consent mechanism, notices shown to staff/customers, blurring method + verification
4. **Labelling:** tool, guidelines version, annotators (count, training), double-annotation %, κ, adjudication
5. **Preprocessing:** blur, resize, dedup; raw video retained? (must be NO for released data)
6. **Uses:** intended; not suitable for; known risks
7. **Distribution:** licence (CDLA-Permissive-2.0 | CC BY 4.0 | restricted), access method, hash/DOI, takedown & revocation process
8. **Maintenance:** owner, versioning, refresh policy, contact
9. **Privacy & legal review:** reviewer, date, outcome (PROFESSIONAL REVIEW)
10. **Per-source licence table:** source, licence, verified on <date>, permitted uses
```

## 3. Evaluation report (rendered) outline (`docs/ml/reports/<model>.md`, generated)
1. Header: model, dataset id/hash, splits hash, protocol hash, commit, date, hardware.
2. **Verdict box:** `PASS | FAIL | NOT MEASURED` per gate G1–G11 with values and CIs; stretch status.
3. Primary metric with CI and coverage; forest plot across venues.
4. Per-class tables + confusion matrix.
5. Event-level metrics and timing-error distributions.
6. Baseline comparison + paired test.
7. Segment & proxy-group tables (n shown; insufficient-data flags).
8. Calibration reliability diagram; abstention curve (coverage vs selective F1).
9. Robustness table.
10. Latency/throughput tables per hardware profile and model size.
11. Error analysis + blurred gallery.
12. Known limitations; waivers (name, date, reason).
13. Reproduction commands.

## 4. Labelling guide outline (`docs/ml/labeling-guide.md`)
Definitions of the four states with examples/counter-examples; how to mark transitions (the moment the last guest leaves; the moment cleaning cloth touches table); staff vs customer rules (uniform, behaviour, zone) and "unsure" usage; handling occlusion, children, groups standing near but not seated, delivery riders; `UNLABELLED` rules; tool shortcuts; QA process; privacy rules for annotators (no screenshots, no sharing, report identifiable content).

## 5. Experiment log template (`docs/ml/experiments/EXP-<n>.md`)
Hypothesis · config diff · data hashes · seed(s) · Val metrics (with CI) · decision · link to MLflow run. Test-set results are **never** copied here before the official run.

## 6. Related documents
`07-ml-spec-and-evaluation.md` · `10-testing-and-release-criteria.md`
