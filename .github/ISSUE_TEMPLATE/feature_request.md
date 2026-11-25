name: Feature Request
description: Propose an enhancement to TablePulse
title: "[Feat]: "
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Operational problem to solve
    validations:
      required: true
  - type: checkboxes
    id: privacy_check
    attributes:
      label: Privacy & License Alignment
      options:
        - label: Confirmed this does not introduce facial recognition, audio capture, or per-employee scoring
          required: true
