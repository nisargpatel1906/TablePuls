name: Bug Report
description: Report a defect in TablePulse
title: "[Bug]: "
labels: ["bug"]
body:
  - type: input
    id: spec_id
    attributes:
      label: Related Spec ID (FR/SCR/API/ML)
      placeholder: "e.g., FR-008, SCR-005, API-013"
  - type: textarea
    id: description
    attributes:
      label: What happened?
    validations:
      required: true
  - type: textarea
    id: repro
    attributes:
      label: Steps to reproduce
    validations:
      required: true
