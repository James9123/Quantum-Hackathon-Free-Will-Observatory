"""The persona dialogue box (qollab_project/ui/dialogue.js): static contract checks."""
import json
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
    tab_handler = MAIN[MAIN.index("const tabs = createTabs("):MAIN.index("function writePoetic(")]
    assert "dialogue.unlock();" in tab_handler and "persona = key; moveDialogue(key); schedulePoetic();" in tab_handler


def test_live_region_written_once_per_show_and_only_there():
    show = DIALOGUE[DIALOGUE.index("function show("):DIALOGUE.index("function clear(")]
    assert show.count("els.live.textContent =") == 1
    step = DIALOGUE[DIALOGUE.index("function step()"):DIALOGUE.index("/** Show")]
    assert "els.live" not in step                      # the typewriter never touches the live region
    assert "aria-live" not in DIALOGUE                 # it relies on the existing region, never adds one
    # main.js hands the line to the box instead of writing the live region twice
    wp = MAIN[MAIN.index("function writePoetic("):MAIN.index("const schedulePoetic")]
    assert "dialogue.show(persona, personaName(persona), now.line" in wp
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


def test_every_action_the_page_asks_for_exists():
    """design/persona-dialogue.md section 6: the page (text.js) and the engine name the action
    each guide plays; every name must be a sheet in sprites.js for that guide."""
    data = _sprites()
    allowed = {"self": {"idle", "happy", "angry"}, "demon": {"idle", "gesture", "anger"},
               "observer": {"idle", "stare", "dance"}}
    for persona, actions in allowed.items():
        for action in actions:
            assert action in data[persona], (persona, action)
    text = _read("qollab_project/ui/text.js")
    scene = text[text.index("export function openingScene("):]
    pairs = re.findall(r'persona: "(\w+)", action: "(\w+)"', scene)
    assert pairs == [("demon", "gesture"), ("self", "idle"), ("demon", "idle"), ("self", "happy"), ("observer", "stare"),
                     ("demon", "anger"), ("observer", "dance"), ("self", "angry"), ("observer", "idle")]
    failure = text[text.index("export const FAILURE"):text.index("export function openingScene(")]
    for persona, action in re.findall(r'(\w+): \{ action: "(\w+)"', failure):
        assert action in allowed[persona], (persona, action)
    reactions = text[text.index("export function inputReactions("):text.index("export const FAILURE")]
    assert set(re.findall(r'action: "(\w+)"', reactions)) <= {"idle", "gesture", "stare"}
    engine = _read("qollab_project/observatory.py")
    lines = engine[engine.index("def _self_line("):engine.index("def explanation(")]
    for name in re.findall(r'(?:return [^\n]*?|action = )"(\w+)"', lines):
        assert any(name in acts for acts in allowed.values()), name


def test_player_honours_hold_ticks_and_reduced_motion():
    assert "if (!sheet.loop) {" in DIALOGUE and "sheet.hold" in DIALOGUE          # play once, then hold
    assert "sheet.ticks[index]" in DIALOGUE                                       # per-frame ticks (the stare's pause)
    assert "if (reduced) {" in DIALOGUE and "sheet.keyFrame" in DIALOGUE          # one still frame, no timers
    assert "whole-number scales only" in DIALOGUE
    assert "image-rendering: pixelated" in CSS
    assert "grid-template-columns: 128px 1fr" in CSS and "grid-template-columns: 64px 1fr" in CSS


def test_main_js_drives_the_guides():
    assert 'import { SPRITES } from "./ui/sprites.js";' in MAIN
    assert "sprites: SPRITES" in MAIN
    assert "setMood" not in MAIN and "MOOD_ACTIONS" not in DIALOGUE
    # each guide keeps its current line and action; a tab switch re-shows it
    assert 'for (const k of PERSONAS) say[k] = { line: txt.INTRO[k], action: "idle" };' in MAIN
    # a released dial: only the guides that can see it react (600 ms, on change)
    assert 'input.addEventListener("change", () => { released.add(key); flushReactions(); });' in MAIN
    assert "}, 600, setTimeout);" in MAIN and "txt.inputReactions(dom, input, d, f)" in MAIN
    # a run in flight: idle, lines kept; the result: the engine's lines and animations; a failure
    assert 'dialogue.setAction("idle");' in MAIN
    assert "say[k] = { line: expl.poetic[k], action: acts[k] || \"idle\" };" in MAIN
    assert "Object.assign(say, txt.FAILURE);" in MAIN
    # the opening cutscene: tabs follow the speaker quietly; the box slides back at the end
    assert "dialogue.play(lines, {" in MAIN and "tabs.select(key, false, true)" in MAIN
    assert "sceneSkip: el.sceneSkip, sceneHint: el.sceneHint," in MAIN
    assert "writePoetic({ slide: true })" in MAIN


def test_opening_cutscene_controls():
    assert re.search(r'id="fwo-scene-skip"[^>]*hidden>Skip intro</button>', HTML)
    assert re.search(r'id="fwo-scene-hint"[^>]*hidden>', HTML)
    play = DIALOGUE[DIALOGUE.index("function play("):DIALOGUE.index("function onSkipEvent(")]
    assert "announce: scene.i > 0" in DIALOGUE                     # nothing is announced on page load
    assert "if (pending) { finish(); return; }" in play             # first press completes the typing
    assert 'if (ev.key === "Escape") { endScene(true); return; }' in play
    assert 'document.removeEventListener("keydown", onDocKey)' in play
    assert "fwo-slide-in" in CSS and "fwo-dialogue--enter" in DIALOGUE
    assert "dialogue.refresh()" in MAIN


def test_easter_egg_stage_in_the_style_panel():
    eggs = _read("qollab_project/ui/eggs.js")
    data = json.loads(eggs[eggs.index("export const EGGS = ") + len("export const EGGS = "):eggs.rindex(";")])
    assert data["angry"]["frames"] == 8 and data["angry"]["cell"] == 128
    assert data["bucket"]["frames"] == 8 and data["bucket"]["cell"] == 62     # 0.65 x 96
    assert all(v["src"].startswith("data:image/png;base64,") for v in data.values())
    assert all(ord(ch) < 128 for ch in eggs) and ("/" + "Users" + "/") not in eggs and "Downloads" not in eggs   # no paths
    panel = HTML[HTML.index('<aside id="fwo-style-panel"'):HTML.index("</aside>")]
    assert '<div class="fwo-egg-stage">' in panel and 'id="fwo-egg-self"' in panel
    assert re.search(r'<button type="button" id="fwo-egg" class="fwo-egg"[^>]*aria-label="Pour a bucket of water on the Self">', panel)
    stage = _read("qollab_project/ui/egg.js")
    assert "if (i === o.landAt) playAngry();" in stage                 # the Self reacts when the water lands
    assert "selfTimer = setT(tick, o.freezeMs);" in stage              # frame 1 held, then on to frame 8
    assert "o.setTimeoutFn(" not in stage                                # never called as a method (Illegal invocation)
    assert "if (o.reducedMotion) {" in stage and "Math.random" not in stage
    assert "if (open) egg.start(); else egg.stop();" in MAIN           # timers only while the panel is open
    assert "data.idle" not in stage and "draw(els.self, angry, 0);" in stage   # rests on the angry strip's frame 1
    call = MAIN[MAIN.index("const egg = createEggStage("):MAIN.index("const styleOptions")]
    assert "SPRITES" not in call                                          # the dialogue box's sheets stay there
    assert "showStyles(false);" not in MAIN[MAIN.index("const egg = createEggStage("):MAIN.index("const styleOptions")]


def test_easter_egg_self_does_not_jitter():
    """Every frame of the angry strip stands on the same ground line with its feet in the same place."""
    import base64
    import io
    from PIL import Image
    eggs = _read("qollab_project/ui/eggs.js")
    data = json.loads(eggs[eggs.index("export const EGGS = ") + len("export const EGGS = "):eggs.rindex(";")])
    sheet = data["angry"]
    im = Image.open(io.BytesIO(base64.b64decode(sheet["src"].split(",", 1)[1]))).convert("RGBA")
    cell, grounds, centres = sheet["cell"], set(), []
    for i in range(sheet["frames"]):
        a = im.crop((i * cell, 0, (i + 1) * cell, cell)).getchannel("A")
        bottom = a.getbbox()[3] - 1
        px = a.load()
        xs = [x for y in range(bottom - 6, bottom + 1) for x in range(cell) if px[x, y]]
        grounds.add(bottom)
        centres.append(sum(xs) / len(xs))
    assert len(grounds) == 1, grounds
    assert max(centres) - min(centres) <= 1.0, centres
