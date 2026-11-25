name: Model Error Report
description: Report false positives, false negatives, or calibration drift in CV inference
title: "[ML-Error]: "
labels: ["ml"]
body:
  - type: input
    id: model_version
    attributes:
      label: Model version & channel
      placeholder: "e.g., tablepulse-detector-b1@0.1.0 (experimental)"
    validations:
      required: true
  - type: textarea
    id: failure_mode
    attributes:
      label: Observed failure mode (never attach unblurred patron/staff images)
    validations:
      required: true
