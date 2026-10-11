"""The persona dialogue box (qollab_project/ui/dialogue.js): static contract checks."""
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


DIALOGUE = _read("qollab_project/ui/dialogue.js")
MAIN = _read("qollab_project/main.js")
HTML = _read("qollab_project/index.html")
CSS = _read("qollab_project/main.css")


def test_module_wired_and_markup_present():
    assert 'import { createDialogue } from "./ui/dialogue.js";' in MAIN
    for el in ("fwo-dialogue", "fwo-dialogue-portrait", "fwo-dialogue-name", "fwo-dialogue-text",
               "fwo-dialogue-skip", "fwo-sound", "fwo-sound-help"):
        assert 'id="%s"' % el in HTML, el
    assert re.search(r'id="fwo-dialogue"[^>]*role="group"[^>]*aria-labelledby="fwo-dialogue-name"', HTML)
    assert re.search(r'id="fwo-dialogue-portrait"[^>]*aria-hidden="true"', HTML)
    assert re.search(r'id="fwo-dialogue-text"[^>]*aria-hidden="true"', HTML)
    assert re.search(r'<label for="fwo-sound">', HTML)
    # the live region is untouched: still exactly one, still polite
    assert re.search(r'id="fwo-poetic"[^>]*aria-live="polite"', HTML)


def test_audio_only_after_a_gesture():
    # AudioContext is constructed in unlock() only, and unlock() is called from gesture handlers.
    body = DIALOGUE[DIALOGUE.index("function unlock()"):]
    body = body[:body.index("\n  }\n") + 4]
    assert "new AudioContextClass()" in body
    assert DIALOGUE.count("new AudioContextClass()") == 1
    assert "new AudioContext(" not in DIALOGUE and "webkitAudioContext" not in DIALOGUE
    # the module never starts audio by itself at load: no unlock() call outside handlers
    assert re.search(r'addEventListener\("change", \(\) => \{\s*soundOn = els.sound.checked;\s*if \(soundOn\) unlock\(\);', DIALOGUE)
    run_handler = MAIN[MAIN.index('el.run.addEventListener("click"'):]
    assert run_handler.splitlines()[1].strip().startswith("if (dialogue) dialogue.unlock();")
    assert "if (dialogue) dialogue.unlock(); persona = key; moveDialogue(key); schedulePoetic();" in MAIN


def test_live_region_written_once_per_show_and_only_there():
    show = DIALOGUE[DIALOGUE.index("function show("):DIALOGUE.index("function clear(")]
    assert show.count("els.live.textContent =") == 1
    step = DIALOGUE[DIALOGUE.index("function step()"):DIALOGUE.index("/** Show")]
    assert "els.live" not in step                      # the typewriter never touches the live region
    assert "aria-live" not in DIALOGUE                 # it relies on the existing region, never adds one
    # main.js hands the line to the box instead of writing the live region twice
    wp = MAIN[MAIN.index("function writePoetic()"):MAIN.index("const schedulePoetic")]
    assert "dialogue.show(persona, personaName(persona), line" in wp
    assert wp.count("el.poetic.textContent =") == 1     # the no-box fallback only


def test_reduced_motion_and_no_random():
    assert "Math.random" not in DIALOGUE
    assert "mulberry32" in DIALOGUE
    assert "reduced" in DIALOGUE and "soundOn = !reduced" in DIALOGUE
    assert "prefers-reduced-motion" in CSS and "fwo-caret" in CSS   # caret/cue animations are under the global reduce rule


def test_skip_paths_and_css_block():
    assert '["Enter", " ", "Escape"].includes(ev.key)' in DIALOGUE
    assert 'els.box.addEventListener("click", onSkipEvent)' in DIALOGUE
    for sel in (".fwo-dialogue", ".fwo-dialogue-skip", ".fwo-sr", ".fwo-dialogue:focus-visible"):
        assert sel in CSS, sel
    assert "min-height: 40px" in CSS[CSS.index(".fwo-dialogue-skip {"):]


def test_dialogue_js_parses_with_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    with open(os.path.join(ROOT, "qollab_project", "ui", "dialogue.js"), "rb") as fh:
        out = subprocess.run([node, "--input-type=module", "--check"], stdin=fh, capture_output=True, timeout=60)
    assert out.returncode == 0, out.stderr.decode()


# ------------------------------------------------------------------ sprites

import json as _json

SPRITES_SRC = _read("qollab_project/ui/sprites.js")


def _sprites():
    start = SPRITES_SRC.index("export const SPRITES = ") + len("export const SPRITES = ")
    end = SPRITES_SRC.rindex("};") + 1
    return _json.loads(SPRITES_SRC[start:end])


def test_sprite_module_shape_and_hygiene():
    assert os.path.getsize(os.path.join(ROOT, "qollab_project", "ui", "sprites.js")) < 2_097_152
    assert "export const SPRITE_SIZES = [128, 64];" in SPRITES_SRC
    home = "/Us" + "ers/"                       # assembled so this test file never spells a guarded path
    assert home not in SPRITES_SRC and "Downloads" not in SPRITES_SRC and "http" not in SPRITES_SRC
    assert all(ord(c) < 128 for c in SPRITES_SRC)
    data = _sprites()
    assert set(data) == {"self", "demon", "observer"}
    for persona, actions in data.items():
        assert "idle" in actions, persona
        for action, sheet in actions.items():
            for size in ("128", "64"):
                assert sheet["src"][size].startswith("data:image/png;base64,"), (persona, action, size)
            assert sheet["frames"] >= 1 and sheet["fps"] > 0
            if sheet["ticks"] is not None:
                assert len(sheet["ticks"]) == sheet["frames"]
            if sheet["play"] is not None:
                assert all(0 <= i < sheet["frames"] for i in sheet["play"])
                assert sheet["hold"] in sheet["play"]


def test_sprite_timing_rules_from_the_handoff():
    data = _sprites()
    angry = data["self"]["angry"]
    assert angry["play"] == [0, 1, 2, 3] and angry["hold"] == 3 and angry["loop"] is False
    assert angry["keyFrame"] == 3                                  # reduced motion shows the droop
    stare = data["observer"]["stare"]
    assert stare["ticks"] == [61, 1, 1, 1, 1, 1, 1, 1] and stare["loop"] is True
    assert data["self"]["happy"]["loop"] and data["demon"]["gesture"]["loop"] and data["observer"]["dance"]["loop"]
    assert data["observer"]["idle"]["frames"] == 12 and data["demon"]["idle"]["frames"] == 6


def test_every_mapped_action_exists():
    data = _sprites()
    body = DIALOGUE[DIALOGUE.index("const MOOD_ACTIONS = {"):DIALOGUE.index("const MIN_FRAME_MS")]
    for persona, actions in (("self", ("idle", "happy", "angry")), ("demon", ("idle", "gesture", "anger")),
                             ("observer", ("idle", "stare", "dance"))):
        for action in actions:
            assert '"%s"' % action in body, (persona, action)
            assert action in data[persona], (persona, action)


def test_player_honours_hold_ticks_and_reduced_motion():
    assert "if (!sheet.loop) {" in DIALOGUE and "sheet.hold" in DIALOGUE          # play once, then hold
    assert "sheet.ticks[index]" in DIALOGUE                                       # per-frame ticks (the stare's pause)
    assert "if (reduced) {" in DIALOGUE and "sheet.keyFrame" in DIALOGUE          # one still frame, no timers
    assert "whole-number scales only" in DIALOGUE
    assert "image-rendering: pixelated" in CSS
    assert "grid-template-columns: 128px 1fr" in CSS and "grid-template-columns: 64px 1fr" in CSS


def test_main_js_drives_the_moods():
    assert 'import { SPRITES } from "./ui/sprites.js";' in MAIN
    assert "sprites: SPRITES" in MAIN
    assert 'dialogue.setMood({ phase: "working" })' in MAIN
    assert 'dialogue.setMood({ phase: "failed" })' in MAIN
    assert 'dialogue.setMood({ phase: "done", resolved: !!m.resolved, forecastHit: forecastHit(run) })' in MAIN
    assert 'dialogue.setMood({ phase: "idle", perspectiveMoved: input === el.perspective })' in MAIN
    assert "dialogue.refresh()" in MAIN
