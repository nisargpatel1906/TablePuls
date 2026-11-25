# TablePulse Frame & Review Queue Labeling Guide

1. **Canonical State Definitions:**
   - `[1] FREE`: Table surface is clean, cleared of serviceware, and zero seated guests are inside the polygon ROI.
   - `[2] OCCUPIED`: One or more guests are seated at the table (or actively dining), with recent staff service within SLA window.
   - `[3] NEEDS_CLEANING`: Guests have departed and dishes/glassware/debris remain on the table requiring bussing before re-seating.
   - `[4] NEEDS_SERVICE`: Guests remain seated awaiting attention beyond the unattended service SLA window (e.g., 300s default) or visibly waiting for service.
2. **Guest Counting:** Count seated patrons inside the calibrated ROI. Exclude standing servers passing through briefly unless stationary for >10s during transition.
3. **Exclusion Rule:** Check **"Exclude from training dataset"** if faces are unblurred (report immediately as privacy defect), camera view is blocked by cleaning equipment, or frame is corrupted.
4. **Prohibited Labels:** Never annotate demographics, gender, age, facial identity, emotions, or individual staff identity/performance scores.
