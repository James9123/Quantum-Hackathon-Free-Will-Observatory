# Submission checklist

**Deadline: Sun 2026-10-11 17:00 MDT.** The captain submits; the **target is 15:00 MDT on
Sunday**, which leaves two hours for surprises. Work through the list top to bottom and
tick each box. Anything left unticked at 14:30 goes to the captain.

This effort is supported by Qollab & IonQ

## 1. Required items (from the rules page)

| ✓ | Requirement | Where it is satisfied | How to check |
|---|---|---|---|
| [ ] | Uses **Qiskit** | every circuit is a Qiskit `QuantumCircuit` | `grep -l "from qiskit" qollab_project/*.py` |
| [ ] | Runs on **Qollab's free simulators, including IonQ's** | built-in simulator (free, local: what judges run) + one IonQ run ([§5](#5-ionq-verification-run)) | Run on Qollab and compare with the local run |
| [ ] | **MIT license**, also for any outside repo it relies on | [LICENSE](LICENSE); libraries in [CREDITS.md](CREDITS.md) | No outside code is vendored. Qiskit (which the rules require) is Apache-2.0, so we read this rule as covering code we pull into the project. TODO(captain): ask the organizers if unsure. |
| [ ] | **Project page**: what it does, the problem, how to run, how to replicate/extend | [README.md](README.md) sections of those names, also pasted into the Qollab project description | No `TODO` left in README.md |
| [ ] | **Built during the event window** (Fri 17:00 to Sun 17:00 MDT), with pre-existing work disclosed and credited | [BUILDLOG.md](BUILDLOG.md); "Pre-existing work: none" in [CREDITS.md](CREDITS.md) | BUILDLOG has a row for every major piece, including the idea work |
| [ ] | **Demo video, 2–3 minutes, at a public no-sign-in link** | [VIDEO.md](VIDEO.md) | Length between 2:00 and 3:00; the link plays in a private browser window |
| [ ] | **Attribution line, verbatim**: "This effort is supported by Qollab & IonQ" | README (top and bottom), main.py output, the JS page, CREDITS, the video | `tools/pack_for_qollab.py` checks the upload; read it once on screen |
| [ ] | **UI accessibility best practice** | README → Accessibility | Keyboard-only run-through; a screen reader announces the result; 200% zoom works; text contrast ≥ 4.5:1; nothing conveyed by color alone |
| [ ] | **Stays on Qollab for 12 months** | the Qollab project | Do not delete, unpublish or rename it after submitting |
| [ ] | **AI assistance and prior work disclosed** (non-disclosure can disqualify) | [CREDITS.md](CREDITS.md) → AI disclosure; README → Credits & AI disclosure | Team names filled in; "what the humans did" confirmed by the team |
| [ ] | **Beyond the tutorial**: a novel application, a technical extension, or an original analytical/educational contribution | README → "Beyond the tutorial"; How it works; Results | TODO(idea): the idea's novelty is stated in one sentence |

## 2. Judging traits (no published weights)

| ✓ | Trait | Evidence a judge will look for |
|---|---|---|
| [ ] | **Novelty & creativity** | TODO(idea): the question nobody's tutorial asks, stated in the first paragraph of README |
| [ ] | **Technical execution** | Runs first time on the built-in simulator; one job on IonQ; the test suite passes; the results reproduce (README → Replicate & extend) |
| [ ] | **Impact potential** | TODO(idea): who would use it (learners, teachers, people who benchmark simulators) and how they would extend it |
| [ ] | **Documentation quality** | README scannable in 2 minutes; [docs/claims.md](docs/claims.md) complete; claims state what they do NOT show; no TODOs left |

Judges press **Run on a free local simulator**. Make sure the default settings
(`shots=1000`, `mode=auto`, `mitigate=True`, or the JS page's defaults) produce clean,
self-explanatory output there. IonQ results neither add nor subtract points.

## 3. Pre-share checks (run from the repo root; all must pass)

```sh
# 1. Tests
.venv/bin/python -m pytest -q

# 2. Public-repo hygiene. The pattern list is PRIVATE: keep it at
#    ~/.config/qollab-hackathon/scrub-patterns.txt (or point QOLLAB_SCRUB_PATTERNS at it).
#    Never commit it. Exit 0 = clean, 1 = hits, 2 = missing/invalid patterns or a file
#    that could not be read.
.venv/bin/python tools/scrub_check.py
.venv/bin/python tools/scrub_check.py --git-log     # if the repo is shared WITH its history

# 3. Build and check the upload (the platform rules + the scrub on the upload folder)
.venv/bin/python tools/pack_for_qollab.py --entry python    # or: --entry js
#    -> build/upload-<entry>/ and build/upload-<entry>.zip

# 4. No placeholders left (TODO(idea), TODO(team), TODO(captain) and bare TODO)
grep -rn "TODO" README.md CREDITS.md VIDEO.md docs/claims.md qollab_project/ || echo "no TODOs"
```

- [ ] `pytest`: all tests pass
- [ ] `scrub_check.py`: **clean** for the files. If the repo is shared with its history,
      `--git-log` must be clean too: it scans every commit on every branch and tag (messages,
      author and committer names and emails, every file path and every old file version),
      because all of that becomes public with the history. If it finds something only in
      the history, share a fresh repository without the history instead of rewriting it
      under time pressure (BUILDLOG.md stays the record of what was built when).
- [ ] `pack_for_qollab.py`: `RESULT: OK` for the entry we submit
- [ ] No `TODO` left anywhere a judge will read
- [ ] The idea's numbers in README / docs/claims.md match what the program prints

## 4. Qollab upload

TODO(captain): match these steps to the exact labels in Qollab's interface.

1. [ ] Build: `tools/pack_for_qollab.py --entry <python|js>` → `RESULT: OK`.
2. [ ] On Qollab, create the project (a Python or JS project, matching the entry) and
       upload the files from `build/upload-<entry>/`, or the zip if Qollab accepts zips.
       Keep the folder structure (`data/`, `ui/`).
3. [ ] Check that the file list on Qollab matches the pack summary (same count, `data/`
       present). For the **Python** entry, make sure no `index.html` + `main.js` pair was
       uploaded, or Qollab runs the JS entry instead.
4. [ ] Run on the **built-in simulator** with the default settings. Compare with a local
       run (`tools/run_smoke_local.py --project qollab_project --mode auto`): same
       structure, S within a few se of 2.83, the canary passes, the attribution line prints.
5. [ ] Run on **one IBM noise model** (optional): it should finish in seconds with
       `mode=auto`.
6. [ ] Fill in the project page: title, the summary, the README sections (what it does,
       the problem, how to run, how to replicate/extend), the video link, the repo link,
       the AI and prior-work disclosure, and the attribution line.
7. [ ] Set the project's visibility as the rules require, and open it once in a private
       window to confirm the page needs no sign-in to view.

## 5. IonQ verification run

One run, recorded once. Do it early (Saturday if possible) so a failure leaves time.

1. [ ] In the Run dialog, choose **IonQ Forte 1 (simulator)** (or Forte Enterprise 1).
       Use `shots=1000`, `mode=auto` (a single tiled circuit = **one job**), `mitigate=True`.
2. [ ] Press **Run once**. Do not press it again while the job is pending; the project
       refuses a second submission anyway.
3. [ ] Record: date and time, backend name, job id, raw S ± se, mitigated S ± se,
       `orientation_ok`, readout flip rates, and the verdict. Take a screenshot showing no
       personal information.
4. [ ] Paste the numbers into [docs/claims.md](docs/claims.md) (Result ± se table) and the
       README Results TODO.
5. [ ] If it fails, record the error message, say so in the README, and move on: IonQ
       results neither add nor subtract points.

## 6. Final submission (captain)

- [ ] **14:30 MDT**: every box above ticked or explicitly waived by the captain.
- [ ] Final `pytest`, `scrub_check.py` and `pack_for_qollab.py` all green on the exact
      files being submitted.
- [ ] BUILDLOG.md has a final row (what changed on Sunday).
- [ ] Video link tested in a private window; length 2:00–3:00; captions on.
- [ ] Submit on the hackathon form: the Qollab project link, the video link, the team
      members, and the disclosures. **Target 15:00 MDT. Hard deadline 17:00 MDT.**
- [ ] Save the confirmation (a screenshot or email) and post in the team chat that it
      is done.
- [ ] After submitting: leave the Qollab project unchanged and published for 12 months.
