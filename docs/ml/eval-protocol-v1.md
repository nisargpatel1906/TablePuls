# TablePulse ML Evaluation Protocol v1

- **Primary Metric:** Latency-Compensated Table-State Macro-F1 (**TSM-F1**) across active operational classes (`FREE`, `OCCUPIED`, `NEEDS_SERVICE`, `NEEDS_CLEANING`), penalized linearly above a 2.0s latency budget.
- **Confidence Intervals:** Cluster bootstrap (`cluster_bootstrap_ci`) grouped strictly by recording `session_id` (`n >= 1000` resamples in production releases) so frame correlation never understates variance.
- **Zero-Leakage Split Policy (`ml/tablepulse_ml/splits.py`):**
  1. Zero shared `clip_id` across `train`, `val`, and `test`.
  2. Zero shared `session_id` across splits.
  3. Zero duplicate `frame_hash` across splits.
  4. Temporal separation (`>= 300s` gap on same camera).
  5. Optional strict `venue_id` generalization holdout.
- **Release Gate (`G1–G11`, `ml/evaluate_gate.py`):**
  - Promoting to `channel="stable"` requires `dataset_flag == "PRODUCTION_LABELED"`, `TSM-F1 >= 0.90`, `lower95 >= 0.85`, guest count `MAE <= 0.50`, `ECE <= 0.08`, subgroup `TSM-F1 >= 0.80` across lighting conditions, latency `<= 250ms`, 100% face-blur pass, robustness drop `<= 0.08`, beating B0 majority baseline, and verified Apache-2.0 variant (`nano`/`small`/`medium`/`large`).
- **Baseline Truthfulness Rule:** Until real labeled multi-venue CCTV clips exist and a signed `eval_report.json` passes `G1–G11`, every model score is reported strictly as **`NOT YET MEASURED`** (`gate_status: NOT_MEASURED`), and the zero-shot baseline ships strictly in `channel: experimental`.
