# abtrust v0.3.0 — Manual dashboard acceptance checklist

Test on your Windows laptop in VS Code after `python -m streamlit run app/streamlit_app.py`. Use the Local URL printed in the terminal, usually `http://localhost:8501`.

**18 October 2026:** browser checks at port 8510 verified the sample readout, equal allocation, 40/40 rejection, invalid harm-margin rejection, confidence labels, planning/error recovery, both peeking modes, and the actual Markdown download. File chooser automation timed out, so browser uploads remain pending. See [verification evidence and limits](RELEASE_VERIFICATION.md). Checked boxes below indicate completed browser checks; automated-only coverage does not check a box.

- [x] Sample experiment opens with a table, SRM check, confidence-interval plot, and Markdown download.
- [x] The planned **Equal split** option displays expected equal percentages and SRM does not flag the balanced sample.
- [ ] Custom split **20/80** applies to an actual 20/80-designed sample and does not incorrectly flag SRM solely because the observed counts differ from 50/50.
- [x] Custom split **40/40** is rejected because the planned percentages do not sum to 100.
- [ ] Custom split **0/100**, a negative percentage, or NaN/Infinity is rejected.
- [ ] Upload `data/sample_experiment.csv`; check the result and download button.
- [ ] Upload an empty CSV and a CSV with one column; errors appear without crashing.
- [ ] Try a dataset with missing arm labels, duplicated `user_id`, and missing/infinite numeric values; errors or explicit blocking diagnostics appear.
- [ ] Select `converted` primary, plus `unsubscribed` and `support_contact` as guardrails; blank harm margins correctly produce REVIEW REQUIRED.
- [ ] Enter an invalid margin (`abc`, `-1`, `nan`) and verify it is rejected, not silently interpreted as zero.
- [ ] Enter nonnegative predeclared harm margins; inspect guardrail upper bound and safety_pass. Do **not** interpret a nonsignificant regression as safe.
- [ ] Switch a guardrail to **Higher is better** and verify the harm direction is reflected in the readout.
- [x] Confirm displayed confidence intervals are identified as **unadjusted** while p-values may use Holm/BH correction; change alpha and check that the confidence-level label follows it.
- [x] Plan-sample-size tab displays required users and estimated days; impossible treatment rates show a readable error, and valid inputs restore the plan.
- [x] Peeking tab produces an exploratory method comparison; bounded method and working-normal limitations are clearly labeled.
- [x] Markdown download opens and contains decision, allocation check, results, and safety notes.

Record any failures with a screenshot, selected inputs, and exact terminal error. This checklist complements the automated unit and smoke tests; unchecked cases still require browser acceptance.
