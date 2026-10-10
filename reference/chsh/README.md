# CHSH reference experiment (validation vehicle)

The toolkit in `qollab_project/qk_*.py` was built and validated end to end on CHSH before
the project's own experiment existed. This folder keeps that reference intact for the tests:
`chsh.py` (one packed job → claim card), `main.py` (console entry), `ui_api.py` + `index.html`
+ `main.js` + `ui/` (the first JS shell, with its stub harness in `dev/`), and the precomputed
datasets in `data/`. It is not part of the Qollab upload. See `UI.md` for the shell's design notes.
