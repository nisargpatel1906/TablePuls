# 07 — Machine-Learning Specification, Evaluation & Release Gates

> **Quick reference**
> - **What the ML does:** from fixed-camera restaurant video, (M1) detects people, (M2) classifies staff vs customer, (M3) derives each **table's state** (`FREE / OCCUPIED / NEEDS_SERVICE / NEEDS_CLEANING`), (M4) counts guests per table, (M5) counts people in the entrance queue. Wait-time quotes (M6) are statistical, not learned, in v1.0.
> - **Primary metric (`DECIDED` target: ≥ 90%, stretch 95%):** **Table-State Macro-F1 (TSM-F1)** on the frozen **held-out-venue** test set, with a 95% cluster-bootstrap CI.
> - **Honesty rule:** *no score is claimed anywhere until measured by the specified procedure on a specified dataset.* Today every metric is **NOT YET MEASURED**. 90–95% is a **target to be established by experiments**, not a promise. Section 15 lists the data and experiments required.
> - **Safety net:** calibrated confidence → `UNKNOWN` + human review queue + manual overrides; abstentions count as **errors** in the primary metric so they can't be used to game the score.
> - **Release gate:** `ml/evaluate_gate.py` blocks promotion to the `stable` channel unless all criteria in §13 pass.


> **Task Crosswalk (`ML-01`–`ML-04`):** `ML-01` = Person & Tableware Detection (`M1`, RF-DETR Nano/Small/Medium/Large Apache-2.0 via ONNX); `ML-02` = Table State & Guest Count Estimation (`M2`–`M4`, ByteTrack + ROI geometry + temporal debounce/service-SLA state machine); `ML-03` = Table Cleanliness Classifier (ConvNeXt-Tiny/MobileNetV3 ONNX on vacated tabletop crops); `ML-04` = Turnover ETA Predictor (statistical venue-median/IQR baseline in v1.0, optional LightGBM once >= 7 days of venue history exist).

## 1. ML use cases (what each model predicts, who uses it, what "accuracy" means)

| ID | Task | Input | Output | Used by / decision it drives | Impact | "Accuracy" = |
|---|---|---|---|---|---|---|
| M1 | **Person detection** | Frame (sampled 1–5 FPS) | Boxes + confidence for `person` | Feeds M2–M5 | Medium (errors propagate) | AP@IoU0.5 (AP50) and **recall inside table/queue zones** |
| M2 | **Staff vs customer** classification (track-level) | Person-track crops + zone priors | P(staff) per track | Cleaning detection; guest counts; queue | **High** (misclassifying a customer as staff hides a guest; staff as customer blocks cleaning detection) | Staff-class F1; customer→staff confusion rate |
| M3 | **Table-state estimation** (system-level, via M1+M2+state engine) | Per-table observations over time | One of 4 vision states per table per second (+ `UNKNOWN` abstention) | Host floor, seating recommendations, alerts | **High** | **TSM-F1 (primary)**, per-class F1, event-level F1, timing error |
| M4 | **Guest count per table** | Same | Integer count | HUD capacity %, analytics | Medium | Exact-match accuracy, within-±1, MAE |
| M5 | **Entrance queue count** | Same | Integer count | Queue/wait display, alerts | Medium | MAE, within-±1 |
| M6 | **Wait quote** (statistical) | Table states + history | P25–P75 range in minutes | Host quotes to guests | Medium | Coverage of actual wait by the range (target 50% ±10 for an IQR), median absolute error — reported but **no 90% gate** (not a classifier) |
| M7 | Demand forecasting | History | — | Staffing | — | `DEFERRED` (metric when built: WAPE) |

**Users of results:** hosts/managers (live decisions), analysts (aggregates). **Not used for:** identifying people, evaluating individual staff or customers, or any decision with legal effect on an individual.

## 2. Primary metric — definition (frozen; changes after seeing test results are forbidden)

**Table-State Macro-F1 (TSM-F1)**
1. **Ground truth (GT):** human-labelled state *intervals* per table from video, in the four vision-derivable states `FREE, OCCUPIED, NEEDS_SERVICE, NEEDS_CLEANING`. Periods that are `RESERVED` (manual-only) are excluded. Ambiguous periods are labelled `UNLABELLED` and excluded (their share is reported).
2. **Predictions:** the system's **vision-derived** state per table (output of the state engine *before* manual overrides).
3. **Sampling:** one comparison per table per second.
4. **Latency compensation:** exclude from scoring a window after each GT transition equal to the corresponding confirm timer **+ 5 s**: `FREE→OCCUPIED: seat_confirm_s+5 (25 s)`, `OCCUPIED→NEEDS_CLEANING: leave_confirm_s+5 (35 s)` (sits shorter than `min_session_s=60` are not scored as OCCUPIED), `NEEDS_CLEANING→CLEANING: cleaning_confirm_s+5 (20 s)`, `CLEANING→FREE: cleaning_exit_s+5 (15 s)`. (Reaction delay is by design and is measured separately as *timing error*.)
5. **Abstentions:** a prediction of `UNKNOWN` is counted as **incorrect** (strict). A secondary "selective" score (F1 on non-abstained samples) and **coverage** (share not abstained) are reported alongside.
6. **Computation:** pool samples over all test clips; per-class precision/recall/F1 for the four classes; **macro-average = TSM-F1**.
7. **Uncertainty:** 95% percentile **cluster bootstrap** (resample *clips*, stratified by venue; 10,000 resamples). Frames/seconds are highly autocorrelated so naive binomial CIs are invalid.
8. **Why macro-F1:** classes are imbalanced (e.g., `CLEANING` is rare, `FREE`/`OCCUPIED` dominate); raw accuracy would hide failure on rare, operationally important states. F1 balances false alarms and misses, which matters because both a missed dirty table and a phantom one cost staff time. *(Raw accuracy is reported for completeness only, never as the headline.)*

**Targets (`DECIDED`: at least 90%, 95% stretch — to be measured):**
- **Pass:** TSM-F1 point estimate ≥ **0.90** *and* lower 95% CI bound ≥ **0.85** on the **T-unseen** test set.
- **Stretch:** point estimate ≥ **0.95**.
- If not met, the model is **not** promoted to `stable`; it may be published as `experimental` with the measured value and a visible "below target" label.

## 3. Secondary metrics and targets (all `PROPOSED`, to be measured)

| Task | Metric | Target | Notes |
|---|---|---|---|
| M3 | Per-class F1 (each of 4 states) | ≥ 0.85 each | Prevents rare-class neglect |
| M3 | **Event-level F1** for `seat`, `leave`, `clean-complete` events (one-to-one matching, tolerance = confirm timer + 15 s) | ≥ 0.90 | Alerts depend on events |
| M3 | Timing error (median / P90 absolute) of detected event time vs GT minus confirm timer | median ≤ 10 s, P90 ≤ 30 s | |
| M3 | Calibration: Expected Calibration Error of `state_conf` | ≤ 0.05 | Needed for UNKNOWN thresholds |
| M3 | Abstention coverage | ≥ 0.90 (UNKNOWN ≤ 10 % of eval time) | |
| M2 | Staff F1 (track level) | ≥ 0.90 | |
| M2 | Customer→staff confusion rate | ≤ 0.05 | |
| M1 | AP50 (person) | ≥ 0.90 (stretch 0.95) | Domain-specific; generic COCO models are not assumed to reach this |
| M1 | Recall in table zones at operating threshold | ≥ 0.95 | |
| M4 | Exact-match / within ±1 / MAE | ≥ 0.85 / ≥ 0.95 / ≤ 0.3 | Harder than state; honest lower exact target |
| M5 | MAE / within ±1 | ≤ 1.0 / ≥ 0.90 (queues ≤ 6) | |
| Time metrics | Dwell & time-to-clean: median absolute error | ≤ 45 s | Derived from events |
| M6 | Quote coverage | reported | No gate |

## 4. Data

### 4.1 Sources (all must have a recorded licence/consent basis before use)
| Source | Use | Licence/consent status |
|---|---|---|
| **Public pretraining/detection sets** (e.g., COCO, Open Images, Objects365, CrowdHuman) | Pretraining/zero-shot baselines for M1 only | **UNVERIFIED — each licence must be checked** (some are research/non-commercial; image copyrights vary) `PROFESSIONAL REVIEW` |
| **Venue-contributed footage** (primary source of truth for M2–M5) | Fine-tune, validation, test | Written data-contribution agreement with the venue + notice to staff/customers + blurring before leaving the venue; no audio; no identifiers |
| **Project-recorded/staged footage** (volunteers, signed releases) | Test + edge cases | Signed releases; faces blurred in distributed data |
| **Synthetic/rendered scenes** | Augmentation for rare cases (e.g., night, occlusion) | Marked `synthetic`; **never** in test sets |
| **Opt-in corrections from deployments** (`FR-021`) | Retraining flywheel | Opt-in per venue; blurred crops only; revocable (future dataset versions) |

### 4.2 Labelling
- Tooling: CVAT or Label Studio (external); export to COCO / project schema.
- **Labels:** per-frame person boxes (M1) with `staff|customer|unsure` (M2); per-table interval states (M3); counts (M4/M5) derived from boxes; every labelled clip stores `venue_id`, `camera_id`, `capture_time`, conditions tags (lighting, density, occlusion, angle, resolution).
- **Guidelines:** `docs/ml/labeling-guide.md` with decision rules and examples (e.g., "a person standing at the table pouring water is staff → table still OCCUPIED if customers seated").
- **Quality:** ≥ 10 % of clips double-annotated; **Cohen's κ ≥ 0.80** on state intervals and ≥ 0.85 on staff/customer; disagreements adjudicated by a senior annotator; annotator training with a gold set (≥ 95 % pass).
- **Quality checks (automated):** no overlapping intervals per table; no gaps > 5 s unless `UNLABELLED`; box sanity; label-class histograms; per-annotator drift report.

### 4.3 Privacy, consent, licensing of data
Blur faces **at the venue** before any frame leaves it; strip EXIF/metadata; no audio; no screenshots of screens with personal data; store only `venue_id` pseudonyms; retention of contributed data defined in the agreement; revocation process; publish a **datasheet** (template in `07b-ml-templates.md`) for each released dataset; open-release only if every source licence permits (CDLA-Permissive-2.0 or CC BY 4.0 suggested) — else release only the **tooling + a tiny synthetic fixture dataset** and provide instructions for assembling private data. `PROFESSIONAL REVIEW` for consent wording and cross-border transfer.

### 4.4 Representativeness
Collect across: ≥ 5 venues for training; **≥ 3 *different* venues held out for test**; venue types (café, casual dining, fine dining, food court); camera heights/angles (overhead dome, oblique wall-mount); lighting (daylight, evening, low-light, mixed/glare); density (low/mid/high); table shapes/sizes; outdoor/glass storefront reflections; uniform styles (distinct uniform, apron only, none); typical clothing diversity (including head coverings, long garments), children, wheelchairs/mobility aids, high chairs, delivery riders. Target venue geography includes India (`PROPOSED`) plus ≥ 2 other regions for robustness if available.

### 4.5 Bias & fairness approach
- **No demographic labelling by default** (age, gender, skin tone, ethnicity are not inferred or annotated).
- Evaluate **robustness proxies** that are visible and operational: clothing coverage categories, head coverings, mobility aids, child-sized persons, seated vs standing, apron/uniform similarity. Report M1 recall-in-ROI and M2 error rates per proxy group (n ≥ 50 each or flagged "insufficient data").
- Threshold: worst-proxy-group recall-in-ROI ≥ 0.85 and gap to overall ≤ 0.07 (`PROPOSED`), else the model card lists it as a known limitation and the release needs a documented waiver.
- Optional skin-tone-aware evaluation (e.g., annotator-assigned scale on the **test set only**) requires an ethics/legal decision — `PROFESSIONAL REVIEW`; never used for training or inference.

## 5. Splits (reproducible, leakage-proof)

| Split | Purpose | Construction |
|---|---|---|
| **Train** | Fit | Venues V_train, all but the latest 2 weeks of each |
| **Val** | Tune thresholds/hyper-parameters, calibration | Latest 2 weeks of V_train venues (temporal hold-out) |
| **T-seen** (test) | Generalisation over time at known venues | A frozen later period of V_train venues |
| **T-unseen** (test, **headline**) | Generalisation to new venues/cameras | **Entire venues never used in train/val** (≥ 3 venues) |

Rules:
1. **Group-aware:** the split unit is `(venue, camera, calendar-day)`; the unit for T-unseen is the **venue**. No clip, camera or day appears in two splits (except T-seen ⊂ same venues but different days).
2. **Near-duplicate guard:** perceptual hash + embedding cosine ≥ 0.95 within 60 s windows are grouped before splitting.
3. **Deterministic:** `scripts/ml/make_splits.py --seed 20260101` writes `splits.json`; its SHA-256 is recorded in every eval report.
4. **Frozen test:** test labels live in a separate DVC remote with restricted access; hyper-parameter search uses Val only; a test run is logged (who, when, model hash) and limited to **one official run per release candidate**.
5. **Leakage tests (automated, CI):** (a) disjoint group IDs across splits, (b) no hash overlap, (c) temporal ordering Train < Val < T-seen, (d) T-unseen venues absent from train/val manifests, (e) label provenance fields present.
6. **Refresh policy:** T-unseen retired into Val after a release that used it for a gate; new unseen venues acquired for the next cycle (prevents overfitting to the test set).
7. **Minimum sizes (for CI width):** for a proportion near 0.90, ±3 points at 95 % confidence needs ≈ 384 *independent* instances (n = 1.96²·0.9·0.1/0.03²). Therefore T-unseen must contain **≥ 400 independent labelled state intervals per class** (and ≥ 100 per class per venue). Because seconds are autocorrelated, the effective sample size is the number of **intervals/clips**, which is what the cluster bootstrap uses. If smaller, report the wider CI and **do not** claim the target.

## 6. Baselines & comparison (all evaluated on the same splits and the same protocol)

| ID | Baseline | Description |
|---|---|---|
| B0 | Trivial | Always predict majority class; and "occupied if any person-like pixel motion in ROI" heuristic |
| B1 | **Zero-shot** | Off-the-shelf pretrained detector (no fine-tune) + zone-prior staff rule + the same state engine |
| B2 | **Proposed** | Fine-tuned detector (M1) + staff/customer classifier (M2) + state engine + calibration |
| B3 | End-to-end crop classifier | Per-table-crop CNN predicting state directly + temporal smoothing (no explicit person detection) |
| B4 | Alternative detector | Another permissively-licensed detector, same pipeline |
Report: table of TSM-F1 + CI, per-class F1, event F1, latency, model size, licence for each baseline; **paired bootstrap** test for B2 vs best baseline. The proposed model must beat the best baseline by ≥ +0.03 TSM-F1 with paired-bootstrap p < 0.05 (`PROPOSED`) — otherwise prefer the simpler/faster option.

## 7. Error analysis, limitations, human review

**Required error analysis for every release candidate:** confusion matrices (state; staff/customer), top-10 failure modes with counts and blurred example gallery, root cause tags, and a fix/accept decision. Anticipated failure categories: person occluded by plant/pillar; staff standing beside a table mistaken for customer (or vice-versa); delivery riders; children under table; bags/coats on chairs; reflections in glass; TVs/posters showing people; passers-by outside windows; low light; table partly outside frame; very high density; unusual uniforms.
**Known limitations** (living section in each model card): conditions under which accuracy is expected to be lower (night, extreme angles, heavy occlusion, < 720p, camera moved after calibration); stated plainly, with segment results.
**Confidence & abstention:** `state_conf` is calibrated (isotonic on Val; ECE ≤ 0.05). Below `unknown_conf_threshold` (0.60) → `UNKNOWN`. Below `review_conf_threshold` (0.75) → candidate for the **review queue** (sampled to cap labeller load: max 40 items/day/venue by default).

| High-impact output | Risk | Safeguard |
|---|---|---|
| Table shown `FREE` (hosts seat guests) | Seating at a dirty/occupied table | Only `FREE` with `state_conf ≥ 0.75`; else `UNKNOWN`; seating recommendation excludes `UNKNOWN`; host can override |
| `NEEDS_CLEANING` alert | Wasted staff trips / missed cleaning | Alert only if conf ≥ 0.75; cooldown; "Wrong?" button |
| Staff/customer label | Mis-assigns cleaning/guest counts | Track-level smoothing; venue calibration; zone prior; review queue |
| Wait quote | Customer dissatisfaction | Range + "estimate" + fallback "—" |
| Analytics | Business decisions on bad data | `% UNKNOWN` data-quality badge; audited accuracy displayed |
**Human-in-the-loop path:** host/manager corrections (FR-C06) and review queue labels (`FR-020`) → measured correction rate and audited accuracy → retraining data. Humans can always override; the system never takes an action affecting an individual.

## 8. Model versioning & reproducible training
- Registry (`model_versions`, doc 07) + **MLflow** run per training: git commit, `uv.lock` hash, CUDA/driver, config YAML, seed, dataset DVC hash(es), split hash, hardware, wall time, metrics.
- Naming: `tablepulse-<kind>-<semver>+d<datahash8>`; artifacts ONNX (+ PyTorch checkpoint safetensors); SHA-256 recorded; weights loaded only if checksum matches.
- Entry points: `make train CONFIG=packages/ml/configs/detector_rfdetr_small.yaml`, `make eval MODEL=<id> SPLIT=val|t_seen|t_unseen`, `make eval-report`.
- **Determinism:** fixed seeds, deterministic algorithms where available; a **reproducibility test** retrains on the tiny fixture dataset and must reproduce metrics within ±0.01 (CI).
- **Model card** (template in `07b-ml-templates.md`) required for registration: intended use, out-of-scope use (no biometrics, no individual evaluation), data summary, metrics with CIs, segments, limitations, licence, carbon/compute note, contact.
- ONNX **parity test:** PyTorch vs ONNX outputs agree (box IoU > 0.99; score diff < 0.01) and downstream TSM-F1 differs ≤ 0.005. Quantisation (INT8/FP16) allowed only if the full eval passes again.

## 9. Monitoring in production (drift & quality)

| Signal | Needs ground truth? | Warn | Critical |
|---|---|---|---|
| UNKNOWN share per venue (7 d) | No | > 10 % | > 20 % |
| Mean detection/state confidence shift vs baseline week | No | −0.05 | −0.10 |
| Flap rate (transitions/table/hour above baseline) | No | > 6 | > 12 |
| Host **correction rate** (corrections ÷ state changes, 7 d) | Human signal | > 10 % | > 20 % |
| Input drift: PSI on brightness histogram / embedding statistics | No | PSI > 0.1 | PSI > 0.2 (3 days) |
| Camera blur/brightness quality scores | No | below baseline p5 | — |
| **Audited accuracy** (weekly random audit, §9.1) | Yes | lower 95 % CI < 0.88 | lower 95 % CI < 0.85 |
Warnings appear in `SCR-016`; criticals raise `MODEL_QUALITY_DEGRADED`.

### 9.1 Audit sampling design
Weekly stratified random sample (by state × time-of-day) of **200 snapshots/venue** → review queue (blurred crop + predicted state hidden from the labeller until after they choose, to avoid anchoring) → audited accuracy and macro-F1 with Wilson/bootstrap CI. One week at p≈0.9, n=200 gives a CI half-width ≈ ±4–5 points (too wide for decisions); so the **decision window is the trailing 4 weeks (n≈800, ≈ ±2 points)**. Metrics shown only when ≥ 100 reviewed (else "Not enough data").

## 10. Retraining plan
- **Triggers:** audited lower CI < 0.85; PSI critical; new venue/camera onboarded with calibration failing (<0.80 on its 60-s dry-run + audit); new failure mode with ≥ 20 correction examples; **quarterly** scheduled review.
- **Procedure:** assemble new data (labelling QA §4.2) → retrain candidate (config-pinned) → eval on Val → **one** official eval on T-seen/T-unseen → gate (§13) → **shadow ≥ 7 days** → **canary at 1 venue ≥ 7 days** → promote to `stable` or roll back.
- **No-regression:** no segment drops > 3 points vs the current stable; TSM-F1 non-inferior (lower CI ≥ current point − 0.02).
- Corrections flywheel is **opt-in** and never includes raw video.

## 11. Inference performance requirements
Per camera at `target_fps=3`: detector+tracker+state ≤ 250 ms p95 on **P1 (CPU mini-PC)** for RF-DETR Nano/Small ONNX at 1 camera/2 FPS (CPU) and on **P2 (GPU)** for 8 cameras/3 FPS; measured with `make bench`, results dated in `docs/benchmarks.md`. Memory limits per `docs/09-reliability-and-ops.md`. Adaptive FPS floor 1 FPS. **Accuracy–latency tradeoff table** (Nano/Small/Medium/Large × FPS) is part of every model report.

## 12. Automated ML tests (CI; fixture dataset ≤ 50 MB, synthetic, labelled `FIXTURE-NOT-FOR-REPORTING`)

| Test | Asserts |
|---|---|
| Data schema/label validity | No overlapping intervals; allowed enums; required metadata |
| Split leakage (§5.5) | All five checks |
| Metric correctness | TSM-F1, event-F1, ECE, cluster bootstrap match hand-computed fixtures |
| State-engine replay | Golden observation stream → exact events |
| Determinism/reproducibility | Re-train/re-eval within ±0.01 |
| ONNX parity | §8 thresholds |
| Robustness | Brightness ±30 %, Gaussian noise, JPEG q=40, blur, ±5° rotation, 720p downscale: TSM-F1 degradation ≤ 3 points on fixture (and on real Val before release) |
| Privacy | Blur recall ≥ 0.95 on face-containing test frames; blur-failure ⇒ frame dropped; no biometric libs |
| Gate script | PASS/FAIL/NOT_MEASURED fixtures produce the right exit codes |
| Latency smoke | Mock/ONNX nano model within budget on CI runner (loose) |

## 13. Release gates (enforced by `ml/evaluate_gate.py`)

| # | Criterion | Threshold (on T-unseen unless stated) |
|---|---|---|
| G1 | **TSM-F1** (primary) | point ≥ **0.90** and lower 95 % CI ≥ **0.85** |
| G2 | Per-class F1 (4 states) | each ≥ 0.85 |
| G3 | Staff F1 / customer→staff confusion | ≥ 0.90 / ≤ 0.05 |
| G4 | Segment floors | every segment with n ≥ 50 intervals: TSM-F1 ≥ 0.80; gap to overall ≤ 0.10 (else signed waiver in report) |
| G5 | Beats best baseline | ≥ +0.03, paired-bootstrap p < 0.05 |
| G6 | Calibration & coverage | ECE ≤ 0.05; coverage ≥ 0.90 |
| G7 | Latency | ≤ budget on P1 and P2 reference hardware |
| G8 | Robustness | degradation ≤ 3 points |
| G9 | Privacy & licence | privacy tests pass; weights licence + data provenance recorded and on allow-list |
| G10 | No regression vs current stable | no segment −3 points; non-inferiority §10 |
| G11 | Reproducibility | CI repro test passes; split/data hashes recorded |
| Stretch | TSM-F1 ≥ 0.95 | reported as "meets stretch" only if point ≥ 0.95 |

**Channel rules:** `stable` ⇐ G1–G11 all PASS · `experimental` ⇐ report exists + G7 + G9 (UI shows measured value and "below target" if G1 fails) · **no report ⇒ `NOT_MEASURED`: cannot be registered with `stable`; UI/README show "NOT YET MEASURED".** The gate result is immutable once recorded. CI blocks merges that change model artifacts/configs without a new eval report.

### 13.1 `eval_report.json` (schema essentials)
```jsonc
{
  "schema_version": 1,
  "model": {"name":"…","version":"…","sha256":"…","licence":"Apache-2.0","git_commit":"…"},
  "dataset": {"id":"tablepulse-bench-v1","sha256":"…","splits_sha256":"…","split":"t_unseen",
              "venues":3,"clips":0,"intervals_per_class":{"FREE":0,"OCCUPIED":0,"NEEDS_CLEANING":0,"CLEANING":0}},
  "protocol": {"doc":"docs/ml/eval-protocol-v1.md","sha256":"…","bootstrap":{"resamples":10000,"cluster":"clip","seed":1}},
  "primary": {"name":"TSM-F1","value":null,"ci95":[null,null],"coverage":null},
  "secondary": {"per_class_f1":{}, "event_f1":{}, "timing_error_s":{}, "ece":null, "staff_f1":null, "customer_to_staff":null,
                "guest_count":{"exact":null,"within1":null,"mae":null}, "queue":{"mae":null,"within1":null}, "ap50_person":null},
  "segments": [], "proxy_groups": [], "baselines": [], "robustness": {}, "latency": {"p50_ms":null,"p95_ms":null,"hardware":"…"},
  "gate": {"result":"NOT_MEASURED","criteria":[]},
  "created_at": "…"
}
```
Values are `null` until measured; the gate treats any `null` required value as `NOT_MEASURED` (never as PASS).

## 14. Reporting acceptance criteria (what "done" means for ML)
1. `make eval-report` on the registered model + specified dataset produces `eval_report.json` and a rendered `docs/ml/reports/<model>.md` containing **every** number with n, CI, dataset hash, split hash, date, code commit.
2. README badge and `SCR-016`/`SCR-016` values are generated **only** from stored reports; absence ⇒ "NOT YET MEASURED".
3. No document, UI string or commit message states an achieved accuracy that is not traceable to a stored report.
4. A written **evaluation protocol** (`docs/ml/eval-protocol-v1.md`) is committed and hashed **before** the first official test run (pre-registration); later changes create `v2` and re-run baselines.
5. Gate tests in CI prove the gate blocks a failing report and passes a passing fixture.

## 15. What is needed to establish ≥ 90% (experiment plan — nothing here is assumed achieved)

| Exp | Goal | Needs | Exit criterion |
|---|---|---|---|
| E1 | Build **TablePulse-Bench** | ≥ 8 venues of consented, blurred footage; labelling team; κ checks | Datasheet complete; splits frozen; T-unseen sizes per §5.7 |
| E2 | Baselines B0–B4 | Compute (1 GPU) | Baseline table with CIs |
| E3 | Fine-tune M1 + train M2 | Labelled boxes; per-venue staff examples | Val improvements logged |
| E4 | Ablations | Zone priors, tracking, smoothing, thresholds | Contribution table |
| E5 | Calibration | Val set | ECE ≤ 0.05 |
| E6 | **Official eval** on T-seen/T-unseen | Frozen test | `eval_report.json`; gate verdict |
| E7 | **Field shadow** (≥ 7 d) at 2+ venues | Deployments + audit sampling | Audited accuracy with CI vs offline estimate |
**If TSM-F1 < 0.90:** do not lower the bar or redefine the metric after the fact. Options (in order): more diverse venues/data in failure segments; camera-placement guidance (overhead vs oblique); better staff/customer calibration; larger detector; temporal model; per-venue fine-tune for onboarding; then publish honestly as `experimental` with measured values. Camera-angle or lighting segments that cannot reach the bar are documented as **unsupported conditions** in setup guidance.

## 16. Division of work (important for the coding agent)
- **Agent builds:** dataset manifest + schema validators, split generator, metric library, eval harness, report renderer, release-gate script, training scripts/configs, ONNX export + parity test, monitoring jobs, review/audit pipelines, registry integration, fixture dataset, tests.
- **Humans must provide:** real footage + consent agreements, labelling, GPU training runs, legal/licence review, venue pilots.
- **The agent must never:** fabricate data/labels/metrics, hard-code scores, or mark a gate as PASS without a report. When no real data exists the product ships the **zero-shot baseline model (B1) as `experimental` with "NOT YET MEASURED"**.

## 17. Related documents
`05-architecture-and-tech-stack.md` · `07b-ml-templates.md` · `11-security-and-privacy.md` · `10-testing-and-release-criteria.md` · `decision-log-and-reviews.md`
