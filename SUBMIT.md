# Submission checklist: The Free Will Observatory

**Deadline: Sun 2026-10-11 17:00 MDT.** The captain submits; the **target is 15:00 MDT on
Sunday**, which leaves two hours for surprises. Work through the list top to bottom and
tick each box. Anything left unticked at 14:30 goes to the captain.

This effort is supported by Qollab & IonQ

## 1. Required items (from the rules page)

| ✓ | Requirement | Where it is satisfied | How to check |
|---|---|---|---|
| [ ] | Uses **Qiskit** | every probe is a Qiskit `QuantumCircuit` (standard gates only) | `grep -l "from qiskit" qollab_project/*.py` |
| [ ] | Runs on **Qollab's free simulators, including IonQ's** | built-in simulator (free, local: what judges run, [§5](#5-the-judge-run-built-in-simulator)) + one IonQ run ([§6](#6-ionq-verification-run)) | both runs recorded with the same settings |
| [ ] | **MIT license**, also for any outside repo it relies on | [LICENSE](LICENSE); libraries in [CREDITS.md](CREDITS.md) | No outside code is vendored; three.js (MIT) comes from Qollab's import map. Qiskit (which the rules require) is Apache-2.0, so we read this rule as covering code we pull into the project. TODO(captain): ask the organizers if unsure. |
| [ ] | **Project page**: what it does, the problem, how to run, how to replicate/extend | [README.md](README.md) sections of those names, also pasted into the Qollab project description | No `TODO` left in README.md |
| [ ] | **Built during the event window** (Fri 17:00 to Sun 17:00 MDT), with pre-existing work disclosed and credited | [BUILDLOG.md](BUILDLOG.md); "Pre-existing work" in [CREDITS.md](CREDITS.md) (design note and build guide dated 10 Oct, inside the window) | BUILDLOG has a row for every major piece, including the Observatory engine, page, data and docs |
| [ ] | **Demo video, 2–3 minutes, at a public no-sign-in link** | [VIDEO.md](VIDEO.md) | Length between 2:00 and 3:00; the link plays in a private browser window |
| [ ] | **Attribution line, verbatim**: "This effort is supported by Qollab & IonQ" | README (top and bottom), the page footer, `main.py` output, CREDITS, the video | `tools/pack_for_qollab.py` checks the upload; read it once on screen |
| [ ] | **UI accessibility best practice** | README → Accessibility | Keyboard-only run-through of the three acts; a screen reader announces the readings and the "No resolved influence" sentence; 200% zoom works; text contrast ≥ 4.5:1; nothing conveyed by colour alone (teal/amber always labelled); reduced motion honoured |
| [ ] | **Stays on Qollab for 12 months** | the Qollab project | Do not delete, unpublish or rename it after submitting |
| [ ] | **AI assistance and prior work disclosed** (non-disclosure can disqualify) | [CREDITS.md](CREDITS.md) → AI disclosure; README → Credits & AI disclosure | Team names filled in; "what the humans did" confirmed by the team |
| [ ] | **Beyond the tutorial**: a novel application, a technical extension, or an original analytical/educational contribution | README → "Beyond the tutorial" (all three, novelty first) | The one-sentence novelty ("the same 50/50 outcome is high-capacity in one setting and zero-capacity in another") appears in the first paragraph of the project page |

## 2. Judging traits (no published weights; the team's priority is novelty & creativity)

| ✓ | Trait | Evidence a judge will look for |
|---|---|---|
| [ ] | **Novelty & creativity** | The question nobody's tutorial asks (is uncertainty freedom?), the three personas, the brain-shaped scene, the central contrast; stated in README's first screen and shown in the video's three acts |
| [ ] | **Technical execution** | Runs first time on the built-in simulator; one job with four probes and canaries on IonQ; the test suite passes; the closed form matches the statevector; the Hoeffding interval behaves (coverage sweep); the results reproduce (README → Replicate & extend) |
| [ ] | **Impact potential** | Who would use it (educators teaching interference versus decoherence; philosophy-of-mind classes; science communicators; other Qollab projects reusing the one-job toolkit) and how they would extend it (joint control, CHSH on the bridge, a learned intention policy): README → Beyond the tutorial, Replicate & extend |
| [ ] | **Documentation quality** | README scannable in 2 minutes; [docs/model.md](docs/model.md) and [docs/claims.md](docs/claims.md) complete; every claim says what it does NOT show; no TODOs left |

Judges press **Run on a free local simulator**. The page's defaults (intention π/2,
coupling 0, perspective 0, 1,024 shots per probe, mode auto, canary on) must produce a
clean, self-explanatory first run there. IonQ results neither add nor subtract points.

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
.venv/bin/python tools/pack_for_qollab.py --entry js        # the submission
#    -> build/upload-js/ and build/upload-js.zip
.venv/bin/python tools/pack_for_qollab.py --entry python    # the console fallback, if submitted

# 4. No placeholders left (TODO(measure), TODO(team), TODO(captain) and bare TODO)
grep -rn "TODO" README.md CREDITS.md VIDEO.md docs/claims.md docs/model.md qollab_project/ || echo "no TODOs"
```

- [ ] `pytest`: all tests pass
- [ ] `scrub_check.py`: **clean** for the files. If the repo is shared with its history,
      `--git-log` must be clean too: it scans every commit on every branch and tag (messages,
      author and committer names and emails, every file path and every old file version),
      because all of that becomes public with the history. If it finds something only in
      the history, share a fresh repository without the history instead of rewriting it
      under time pressure (BUILDLOG.md stays the record of what was built when).
- [ ] `pack_for_qollab.py --entry js`: `RESULT: OK`; the file list shows `index.html`,
      `main.js`, `main.css`, `ui/`, `observatory_api.py`, the `qk_*.py` modules and the three
      `data/fwo_*.json` files; no script import from a host other than cdn.jsdelivr.net
- [ ] No `TODO` left anywhere a judge will read
- [ ] The numbers in README / docs/claims.md match what the program prints (the
      `TODO(measure)` placeholders are filled from real runs, never typed from memory)
- [ ] Bit-order test (flip q0 only → app outcome `10`) and the orientation canary both pass
      on the backend used for the judge run

## 4. Qollab upload (JS project)

TODO(captain): match these steps to the exact labels in Qollab's interface.

1. [ ] Build: `tools/pack_for_qollab.py --entry js` → `RESULT: OK`.
2. [ ] On Qollab, create the project as a **JS project** and upload the files from
       `build/upload-js/`, or the zip if Qollab accepts zips. Keep the folder structure
       (`data/`, `ui/`).
3. [ ] Check that the file list on Qollab matches the pack summary (same count, `data/`
       and `ui/` present, top-level `index.html` + `main.js` so Qollab runs the page).
4. [ ] First load on the **built-in simulator**: the backend badge names it, the page
       says "Live simulator", the persona tabs and the three sliders respond, and the
       curves section shows the three shipped datasets with their provenance (if it says
       the data was computed in the session, the data files did not ship: fix the literal
       paths in `observatory_api.py` and re-upload).
5. [ ] Run on **one IBM noise model** (optional): it should finish in seconds with
       `mode=auto` (list mode).
6. [ ] Fill in the project page: title, the summary, the README sections (what it does,
       the question, how to run, how to replicate/extend), the video link, the source link,
       the AI and prior-work disclosure, and the attribution line.
7. [ ] Set the project's visibility as the rules require, and open it once in a private
       window to confirm the page needs no sign-in to view.

## 5. The judge run (built-in simulator)

What a judge does, done once by us first, with the result recorded.

1. [ ] Open the project, keep the **built-in simulator**, press Run, wait for the page.
2. [ ] Act 1 (defaults: w = 0, φ = π/2, β = 0): press *Run experiment*. Expect P(Self = 1)
       near 0.5, Capacity near 1.00 and **resolved**, Openness near 1 bit, Connection near 0.
3. [ ] Act 2 (φ = π): rerun. Expect P(Self = 1) near 1, Openness near 0, Capacity near 1.
4. [ ] Act 3 (w = 1, φ = π/2): rerun. Expect P(Self = 1) near 0.5, Connection near 1 bit,
       and the Capacity interval including zero with the sentence *No resolved influence
       at this shot count*.
5. [ ] Demon tab: the forecast matches the ideal values in [docs/model.md](docs/model.md)
       §5; the two baselines are labelled as theoretical classical references. Observer tab:
       change β, rerun, Capacity stays comparable.
6. [ ] Drawer: four count tables that each total the shots requested, the job record, the
       circuit, and the attribution line in the footer.
7. [ ] Record the three acts' readings and intervals into [README.md](README.md)
       (Validation) and [docs/claims.md](docs/claims.md) (Result tables), replacing the
       `TODO(measure)` placeholders.
8. [ ] Console fallback (if submitted): `tools/run_smoke_local.py --project qollab_project
       --mode auto` runs `main.py` the way Qollab does; its positional call must match
       `main()`'s signature.

## 6. IonQ verification run

One run, recorded once. Do it early (Saturday if possible) so a failure leaves time.

1. [ ] In the Run dialog, choose **IonQ Forte 1 (simulator)** (or Forte Enterprise 1).
       Keep the defaults (1,024 shots per probe, `mode=auto` → one tiled circuit, canary on).
2. [ ] Press *Run experiment* **once** for Act 1. Do not press it again while the job is
       pending; on a one-job backend the page refuses a second submission for that run
       anyway.
3. [ ] Record: date and time, backend name, job id, `submitted_as`, wall time, shots
       requested and seen per probe, `orientation_ok`, the flip rates, P(Self = 1),
       Capacity with its interval and `resolved`, Openness, Connection. Take a screenshot
       showing no personal information.
4. [ ] Paste the numbers into [docs/claims.md](docs/claims.md) (the IonQ rows) and the
       README Validation table; note the provider's rounded counts if totals differ from
       the request.
5. [ ] If it fails, record the error message and the `job_returned` flag, say so in the
       README, and move on: IonQ results neither add nor subtract points.

## 7. Video

- [ ] Recorded per [VIDEO.md](VIDEO.md): three acts, Demon and Observer briefly, honesty
      copy, how to run, credits; the attribution line on screen at start and end.
- [ ] Length 2:00–3:00; captions reviewed; transcript pasted into VIDEO.md.
- [ ] Nothing private on screen (watched once end to end just for this).
- [ ] Uploaded public or unlisted; the link plays in a private window without sign-in.

## 8. Final submission (captain)

- [ ] **14:30 MDT**: every box above ticked or explicitly waived by the captain.
- [ ] Final `pytest`, `scrub_check.py` and `pack_for_qollab.py --entry js` all green on the
      exact files being submitted.
- [ ] BUILDLOG.md has a final row (what changed on Sunday).
- [ ] Team names and roles filled in ([CREDITS.md](CREDITS.md)); the AI-assistance and
      prior-work statements confirmed by every member.
- [ ] Video link tested in a private window; length 2:00–3:00; captions on.
- [ ] Submit on the hackathon form: the Qollab project link, the video link, the team
      members, and the disclosures. **Target 15:00 MDT. Hard deadline 17:00 MDT.**
- [ ] Save the confirmation (a screenshot or email) and post in the team chat that it
      is done.
- [ ] After submitting: leave the Qollab project unchanged and published for 12 months.
