# Development

Setting up a local environment, running the tests, and using the research and build
scripts outside `qollab_project/`. None of the files in this document are uploaded to
Qollab (`tools/pack_for_qollab.py` leaves them out); they exist to develop, validate and
regenerate what does get uploaded. See [architecture.md](architecture.md) for how the
shipped code fits together and [ui.md § Stub mode](ui.md#stub-mode-local-testing) for
driving the page itself without a backend.

## Setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

`requirements-dev.txt` pins `qiskit==2.5.2` and `qiskit-aer==0.17.2` (the exact versions the
measured numbers in [claims.md](claims.md) were produced with), plus `numpy`, `scipy`,
`pytest`, and the real `qiskit-ibm-runtime` / `qiskit-ionq` provider packages so local checks
exercise the actual backend classes Qollab injects. None of this is uploaded; Qollab brings
its own Pyodide-side qiskit.

## Running the tests

```sh
.venv/bin/python -m pytest -q                                        # the whole suite
.venv/bin/python -m pytest -o addopts= -q tests/test_project_data.py  # one file
```

`pytest.ini` points `testpaths` at `tests/` and registers one marker, `slow` (opt-in with
`FWO_SLOW=1`). The suite is organized by what it covers rather than by source file:

| Test file | Covers |
|---|---|
| `test_observatory.py`, `test_observatory_api.py` | The Observatory engine and its JSON bridge: settings validation, the circuit, bit order, the three readings, the Hoeffding interval, the explanation text, `run_json`/`predict_json`/`profile_json` contracts. |
| `test_integration_fwo.py`, `test_fwo_experiments.py` | End-to-end runs against a real `BasicSimulator`, and the `lab/experiments.py` registry used by `lab/sweep.py`. |
| `test_qk_bounds.py`, `test_qk_estimators.py`, `test_qk_mitigation.py`, `test_qk_primitives.py`, `test_qk_noise.py`, `test_qk_data.py`, `test_qk_cards.py` | The general toolkit modules, independent of the Observatory (shared with the CHSH reference project). |
| `test_runtime.py`, `test_packer.py` | `qk_runtime` (backend classification, the one-job guard, `prepare`) and `qk_packer` (tile/list/tiles packing, canary blocks, unpacking). |
| `test_chsh_e2e.py`, `test_bounds_lp.py` | The CHSH reference experiment end to end, and the linear-programming classical-bound check (`lab/bounds_lp.py`). |
| `test_ui_static.py` | Static contract checks on the JS/HTML: platform rules (no inline scripts, one stylesheet), every control labelled, live regions, computed contrast ratios, and that `profile_json`/`predict_json`/`run_json`/`curves_json` return every field path `main.js` reads. |
| `test_ui_api.py`, `test_ui_dialogue.py`, `test_ui_plate.py` | The stub API contract, the persona dialogue/sprite state machine, and the `ui/plate.js` flat-scene renderer. |
| `test_smoke.py`, `test_tools.py` | `smoke/main.py` (see below) and the `tools/*.py` build scripts. |
| `test_project_data.py` | The three shipped `qollab_project/data/fwo_*.json` files actually exist and validate against the `qk_data` schema. |

## The smoke test (`smoke/`)

`smoke/main.py` is a standalone Qollab platform probe — it is what the team ran *before*
writing `observatory.py`, to settle platform unknowns rather than assume them: library
versions, how the injected `backend` behaves, flat vs. package imports, data-file loading
rules, which types the Run-settings form accepts, count-key format and bit order, one-job
packing (tile vs. list), IonQ debiasing, and in-browser density-matrix speed. It submits
exactly one job per press of Run and prints a `SMOKE SUMMARY` block.

```sh
.venv/bin/python tools/run_smoke_local.py                 # runs smoke/main.py under CPython
.venv/bin/python tools/run_smoke_local.py --fake-ionq      # ...against a one-job-per-run stand-in
```

`smoke/qk_packer.py` and `smoke/qk_runtime.py` are deliberately separate copies used to
smoke-test the packer/runtime contracts in isolation; `smoke/pkgtest/` is a two-file package
used only to confirm Qollab's import scanner prefetches packages as well as flat modules.

## `lab/`: research scripts (off-platform)

`lab/` runs on a workstation, never in the browser, and produces the numbers and datasets
that `qollab_project/` ships or that `docs/claims.md` quotes.

| Script | Purpose |
|---|---|
| `lab/bounds_lp.py` | Confirms the classical (local/macrorealist) CHSH bound by linear programming over the local polytope (`scipy.optimize.linprog`, HiGHS), cross-checking the enumeration-based bound in `qk_bounds.classical_max_enumerate`. |
| `lab/experiments.py` | The experiment registry for `lab/sweep.py`: `fwo_theory` (exact readings vs. `w`), `fwo_noise` (readings vs. noise scale), `fwo_coverage` (empirical Hoeffding-interval coverage from seeded sampling), plus the CHSH reference experiment. |
| `lab/sweep.py` | Runs one experiment over a parameter grid (`--grid name=start:stop:num` or an explicit list, `--fixed name=value`) and writes a `qk_data`-schema JSON file with full provenance. `--shots 0` means exact (density-matrix); `--shots N > 0` adds a seeded sampled estimate. Size-capped at 2 MB by default. |

Regenerate the three shipped datasets with the exact commands in the root README's
[Replicate & extend](../README.md#replicate--extend) section — reproduced here for
convenience:

```sh
.venv/bin/python lab/sweep.py --experiment fwo_theory   --grid w=0:1:101 --shots 0 \
    --out qollab_project/data/fwo_theory.json
.venv/bin/python lab/sweep.py --experiment fwo_noise --shots 0 \
    --grid scale=0,0.5,1,1.5,2,3,4,5,6,8,10,12,15,20,25,30,40,50,60,80 --grid w=0,0.5 \
    --fixed p1=0.0002666666666666667 --fixed p2=0.004949333333333333 \
    --out qollab_project/data/fwo_noise.json
.venv/bin/python lab/sweep.py --experiment fwo_coverage --grid w=0:1:5 \
    --fixed repeats=2000 --shots 1024 --workers 5 --out qollab_project/data/fwo_coverage.json
```

The coverage sweep is seeded (`--seed 1` by default) but not bit-identical across CPU
architectures, since numpy's sampler isn't; a rerun should reproduce the quoted coverage and
resolved fractions within about `2e-4`. If a regenerated file's `params` disagrees with the
commands above, trust the file's own provenance over this document.

## `tools/`: build and packaging scripts

| Script | Purpose |
|---|---|
| `tools/pack_for_qollab.py` | **The pre-submission gate.** Builds `build/upload-<entry>/` (and its zip) from `qollab_project/`, refusing anything the platform would silently break on: missing entry files, >100 files or a file over 2 MB, a `.py` file that doesn't parse, a `data/` file not named by a literal path string anywhere in the uploaded source, or (for the Python entry) a `main.py` signature that wouldn't produce a Run-settings form. Run with `--entry js` (the submission) or `--entry python` (the fallback). |
| `tools/scrub_check.py` | Public-repo hygiene tripwire: scans files (and optionally `--git-log` for the whole git history) against a **private**, locally-configured pattern file (`$QOLLAB_SCRUB_PATTERNS` or `~/.config/qollab-hackathon/scrub-patterns.txt`) and fails closed if that file is missing, unreadable, or invalid — it never reports a false "clean." The pattern list itself is deliberately excluded from the repository. |
| `tools/run_smoke_local.py` | Runs `smoke/main.py` locally the way Qollab would (injects `backend`, `chdir`s into the project folder); see above. |
| `tools/make_ui_stubs.py` | Regenerates `dev/stub_data.js` by calling the real `observatory_api` functions against local stand-in backends (a seeded `BasicSimulator`, an IonQ-shaped one-job wrapper, a failing backend), so stub mode never drifts from the real API. See [ui.md § Stub mode](ui.md#stub-mode-local-testing). |
| `tools/ui_shots.py` | Drives `dev/index.html?auto=...` in a headless Chromium-family browser and captures baseline screenshots for design review (`build/ui-baseline/`), per [design-brief.md](design-brief.md). |
| `tools/build_sprites.py`, `tools/build_eggs.py` | Convert the team's sprite-sheet and GIF art exports into the data-URI JS modules (`ui/sprites.js`, `ui/eggs.js`) the page embeds directly, since JavaScript on Qollab cannot fetch project files at runtime. |

### Packaging for Qollab

```sh
.venv/bin/python tools/pack_for_qollab.py --entry js        # the submission
.venv/bin/python tools/pack_for_qollab.py --entry python     # the console fallback
.venv/bin/python tools/scrub_check.py                        # hygiene (needs the private pattern file)
```

Run both before every upload; see [SUBMIT.md § 3](../SUBMIT.md#3-pre-share-checks-run-from-the-repo-root-all-must-pass)
for the full pre-share checklist, including the placeholder and honesty-wording sweeps.

## The dev/ harness

`dev/` is the non-Qollab way to run the exact same `main.js` in an ordinary browser:
`dev/boot.js` starts `main.js` and injects `dev/index.html`'s fragment 300 ms later (the way
Qollab injects it), with `observatory_api` replaced by `dev/stub_api.js` and `backend` by a
stand-in object. `dev/themes/_tokens-reference.css` is a reference sheet of the CSS custom
properties `main.css` exposes for the four page styles — useful when adjusting a theme
without hunting through `main.css` itself. Full stub-mode usage (query parameters, serving
the repo locally, what gets synthesized vs. replayed) is in
[ui.md § Stub mode](ui.md#stub-mode-local-testing).

## Running the Python console entry locally

The one-liner from the root README, for reference — this is how Qollab's own harness calls
`main.py` (a `backend` global, then the module's top level, then one call to `main(...)`):

```sh
cd qollab_project && ../.venv/bin/python -c '
from qiskit.providers.basic_provider import BasicSimulator
backend = BasicSimulator(); backend.set_options(seed_simulator=11)
exec(open("main.py").read())
main(90.0, 0.0, 0.0, 1024, "self")' && cd ..
```

This prints the backend profile, the Demon's forecast, the four probes' count tables, the
three readings, and the attribution line — the same content the JS page shows, as plain text.

This effort is supported by Qollab & IonQ
