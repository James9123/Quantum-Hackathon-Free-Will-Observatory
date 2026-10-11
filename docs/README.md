# Documentation map

The Free Will Observatory is a single-page quantum instrument, built for a Qollab/IonQ
hackathon, that stages a two-qubit circuit as a fictional test of "the capacity to reshape
possible futures." A user sets an **Intention**, presses **Run experiment**, and watches a
brain-shaped scene redraw itself from one freshly submitted simulator job; three personas
(The Self, Laplace's Demon, The Observer) read the same four-probe result differently. The
top-level [README.md](../README.md) is the project's front door — start there for what it
does, how to run it on Qollab, and the measured validation numbers. This folder is the
supporting documentation set: the model's derivation, the claims it is willing to stand
behind, the UI's structure, the system's architecture, and how to develop and extend it.

**Why "Laplace's Demon"?** One of the three personas is named for Pierre-Simon Laplace's
1814 thought experiment about a calculating intellect that could predict the whole universe
from one instant's data — the classical picture of determinism that Bell-inequality
experiments are the modern rebuttal to. The Observatory borrows the name because its own
Demon persona *does* compute an exact forecast from the quantum state before any shots are
taken, and the project's central question — is a known probability distribution the same
thing as an open future? — is a dramatized descendant of that older argument. The full story,
with the appropriate caveats about what it does and doesn't prove, is in
[design-brief.md § Inspiration](design-brief.md#inspiration-laplaces-demon-and-the-limits-of-calculation).

## Where to go

| Document | Read this for |
|---|---|
| [architecture.md](architecture.md) | How the pieces fit: the Python engine's module layout, the data flow from circuit to screen, the Qollab JS/Python entry points, and how the shipped datasets are produced and loaded. Start here for "how does this actually work end to end." |
| [model.md](model.md) | The physics and statistics specification: the exact circuit, the closed-form probability, the three readings' definitions, the Hoeffding interval, bit-order conventions, and the noise model. The ground truth the code implements (`model_version = fwo-1`). |
| [claims.md](claims.md) | The project's three claim cards (Claim → Assumptions → Witness → Result → What this does NOT show → Counterarguments), each with measured numbers, seeds and honest limits. Read this before citing any number from the project. |
| [ui.md](ui.md) | The browser-side page: file layout, component responsibilities, the persona/dialogue/sprite system, the four visual design styles, the stub-mode dev harness, and the accessibility checklist. |
| [development.md](development.md) | Setting up a local environment, running the test suite, using the `lab/` research scripts and `tools/` build scripts, and regenerating the shipped datasets. The practical companion to architecture.md. |
| [design-brief.md](design-brief.md) | The visual-design brief for the page (constraints, measurable targets, the design tool workflow) and the project's narrative/philosophical inspiration, including the Laplace's Demon framing. |
| [platform-notes.md](platform-notes.md) | What the code relies on about the Qollab runtime itself (Python vs. JS project rules, backend quirks, IonQ's published noise model) — contributor-facing, not user-facing. |
| [kimi-prompts.md](kimi-prompts.md) | The literal prompts used with an AI design tool during the visual-overhaul pass. Process record, not a specification; `design-brief.md` is the specification. |

## Quick start

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q          # the whole suite
```

See [development.md](development.md) for the full setup, the Qollab-style console entry
point, and how to regenerate the shipped datasets; see the root
[README.md § How to run on Qollab](../README.md#how-to-run-on-qollab) for uploading and
running the page itself.

## A note on honesty

Every document in this set inherits the same rule the project applies to itself: a
simulator computes what quantum theory predicts (and how a noise model degrades it); it does
not test nature. The Self, the World, and the three personas are a designed fiction built on
a reproducible two-qubit circuit — the physics is real and checked against closed forms to
machine precision, but the story about "capacity" and "free will" is deliberately a model,
not a discovery. See [claims.md](claims.md) and the root README's
[Honesty section](../README.md#honesty-what-this-is-and-is-not) for the specifics.

This effort is supported by Qollab & IonQ
