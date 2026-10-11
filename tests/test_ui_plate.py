"""The flat drawn scenes (qollab_project/ui/plate.js) that the four design themes select.

Static contract checks, like tests/test_ui_static.py; the drawing itself is checked in a
browser (dev/index.html?theme=a..d).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


PLATE = "qollab_project/ui/plate.js"


def test_plate_keeps_the_scene_mappings():
    code = _read(PLATE)
    assert "const RMAX = 52;" in code and "RMAX * Math.cbrt(" in code       # radius ~ cbrt(p)
    assert "2 + 10 * p[i]" in code                                          # branch 2 + 10 p ...
    assert '"vector-effect": "non-scaling-stroke"' in code                  # ... in screen pixels
    assert "2 + 10 * I" in code and "0.15 + 0.85 * I" in code               # bridge follows connection
    assert "const N_PART = 40;" in code and "Math.round(to.p1 * N_PART)" in code


def test_future_one_is_upper_right_as_the_scene_text_says():
    code = _read(PLATE)
    assert "const FC = [[512, 300], [512, 112]];" in code     # index 0 lower right, 1 upper right
    text = _read("qollab_project/ui/text.js")
    assert "upper right sphere" in text and "lower right sphere" in text


def test_plate_has_the_same_api_and_text_alternative_as_the_3d_view():
    plate = _read(PLATE)
    scene = _read("qollab_project/ui/scene.js")
    for name in ("setResult", "setLabel", "setMotion", "setReducedMotion", "motion", "resize", "dispose", "canvas"):
        assert "api." + name + " =" in plate, name
        assert "api." + name + " =" in scene, name
    assert 'role: "img"' in plate and '"aria-label"' in plate


def test_plate_motion_is_decoration_only():
    code = _read(PLATE)
    assert "requestAnimationFrame" in code and "root.isConnected" in code
    assert "if (reduced) {" in code and "anim = null;" in code          # reduced motion: no transition
    assert "fn(target, narrow)" in code                                  # annotations show the run's numbers
    assert "Math.random" not in code


def test_the_four_styles_exist_and_each_theme_selects_its_own():
    code = _read(PLATE)
    for t in "abcd":
        assert re.search(r"(?m)^  %s\(c\) \{$" % t, code), t
        css = _read("dev/themes/theme-%s.css" % t)
        assert "--fwo-scene-plate: %s;" % t in css, t
        assert '#fwo-app[data-theme="%s"] .fwo-plate text' % t in css, t


def test_main_picks_the_plate_from_the_theme_variable():
    main = _read("qollab_project/main.js")
    assert 'import { createPlate } from "./ui/plate.js";' in main
    assert 'getPropertyValue("--fwo-scene-plate")' in main and "/^[abcd]$/.test(v)" in main
    assert "const scene = plateStyle\n    ? createPlate(dom, el.sceneHost, " in main
    assert ": createScene(THREE, dom, el.sceneHost, " in main            # no theme: the 3D view


def test_main_css_sizes_the_plate_and_stops_its_twinkle():
    css = _read("qollab_project/main.css")
    assert "#fwo-app .fwo-scene .fwo-scene-host.fwo-scene-host--plate { height: auto; aspect-ratio: 660 / 420; }" in css
    assert "#fwo-app .fwo-plate--still .fwo-plate-twinkle { animation: none; }" in css
    assert "@keyframes fwo-plate-twinkle" in css
