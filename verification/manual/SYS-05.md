# SYS-05 — End-to-End Notifications

Before starting the frontend on Windows, run `frontend\configure-smtp.ps1`. Enter the Gmail sending address and a Google App Password when prompted; the password input is hidden and is stored only in the gitignored `backend/.env`. Restart `frontend/run.ps1`, then confirm `/api/health` reports `mode: live`.

Through the actual UI configure controlled email recipients, monitored source, independent thresholds, and high/low messages. Trigger controlled high and low crossings. Correlate the database sample, rule evaluation, episode transition, provider call, destination, and exact message. Confirm both controlled end-to-end emails in the destination inbox without placing credentials in evidence. SMS delivery is out of scope.
