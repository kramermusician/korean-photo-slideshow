#!/usr/bin/env python3
"""Generate the Lens slideshow HTML (public GitHub Pages build).

Lens is an any-language -> any-language photo-vocabulary teacher. Each per-photo
JSON carries a `concepts` array; every concept holds the same word in six
co-equal languages (English, Korean, Japanese, Spanish, French, Mandarin) under
`langs`, each with `word`, `reading`, and `example`. The UI exposes two pickers:
"I speak" (home language) and "I'm learning" (target language). Cards teach the
target word with the home-language word shown as the gloss; the click-target
game prompts with the target word (the one being learned) and confirms with the
home-language meaning plus the spoken target word. Audio for every language is
the browser Web Speech API (no pre-generated mp3 needed).

Images: each source photo (from ~/Dropbox/KRAMOS/korean-photo/) is downscaled
into docs/photos/ with a URL-safe name and served as a repo-local file by GitHub
Pages. This is self-contained — no external Dropbox link to break. Each photo's
JSON gets a `local_image` field (e.g. "photos/Photo-Jun-07-2026-14-21-31.jpg").
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

# Where original photos may live, in priority order. The watcher leaves the
# original in the input folder after processing; the feedback folder is a fallback.
SOURCE_DIRS = [
    Path.home() / "Dropbox" / "KRAMOS" / "korean-photo",
    Path.home() / "Dropbox" / "KRAMOS" / "korean-photo-feedback",
]
# Long-edge cap for web images. The UI shows them at <=400px tall, so 1280 is
# plenty crisp while keeping the repo small (~150-300KB/photo vs. ~3MB original).
MAX_EDGE = 1280

# The six co-equal languages, in picker order.
LANG_CODES = ["ko", "ja", "es", "fr", "zh", "en"]


def safe_name(filename):
    """URL-safe .jpg filename derived from the original (spaces/commas -> '-')."""
    stem = Path(filename).stem
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-")
    return f"{slug}.jpg"


def downscale(src, dest):
    """Downscale src into dest as JPEG via sips. Returns True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["sips", "-s", "format", "jpeg",
             "--resampleHeightWidthMax", str(MAX_EDGE),
             str(src), "--out", str(dest)],
            check=True, capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # sips missing or failed (e.g. non-macOS) — fall back to a plain copy so
        # the image still shows, just unoptimized.
        try:
            shutil.copy2(src, dest)
            return True
        except OSError:
            return False


def prepare_image(photo, photos_out_dir):
    """Resolve the source photo, (re)build a downscaled docs/photos/ copy, and
    set photo['local_image']. Returns a one-word status for logging."""
    src_name = photo.get("photo", "")
    dest = photos_out_dir / safe_name(src_name)
    photo["local_image"] = f"photos/{dest.name}"

    src = next((d / src_name for d in SOURCE_DIRS if (d / src_name).exists()), None)
    if src is None:
        # No original available. Keep an already-committed copy if present.
        return "kept" if dest.exists() else "MISSING"
    if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return "cached"
    return "built" if downscale(src, dest) else "MISSING"


def build_html(photos):
    """Build HTML with embedded JSON data. Images are served from docs/photos/.

    Uses a plain templated string (not an f-string) so the large CSS/JS block
    keeps single braces; only the __PHOTOS_JSON__ marker is substituted.
    """
    photos_json = json.dumps(photos, ensure_ascii=False)

    template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lens — learn from your photos</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: linear-gradient(135deg, #f5ede4 0%, #e8ddd0 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { max-width: 900px; width: 100%; background: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.1); overflow: hidden; }

        /* ── Header ── */
        .header { background: linear-gradient(135deg, #8b7355 0%, #a89080 100%); color: white; padding: 24px; text-align: center; }
        .header .brand { font-size: 13px; font-weight: 700; letter-spacing: 0.28em; text-transform: uppercase; opacity: 0.8; margin-bottom: 4px; }
        .header h1 { font-size: 22px; font-weight: 500; letter-spacing: 0.5px; margin-bottom: 16px; opacity: 0.92; }
        .picker-group { display: flex; flex-direction: column; gap: 8px; align-items: center; }
        .picker-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: center; }
        .picker-label { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.85; min-width: 84px; text-align: right; }
        .lang-picker { display: inline-flex; gap: 4px; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.35); border-radius: 22px; padding: 4px; backdrop-filter: blur(4px); flex-wrap: wrap; justify-content: center; }
        .lang-btn { background: transparent; color: rgba(255,255,255,0.85); border: none; padding: 7px 14px; border-radius: 18px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; }
        .lang-btn:hover { color: white; background: rgba(255,255,255,0.18); }
        .lang-btn.active { background: white; color: #8b7355; }
        .lang-btn:disabled { opacity: 0.3; cursor: not-allowed; background: transparent; color: rgba(255,255,255,0.4); }
        .header-actions { margin-top: 14px; }
        .mode-tabs { display: inline-flex; gap: 6px; flex-wrap: wrap; justify-content: center; }
        .mode-tab { background: rgba(255,255,255,0.16); color: rgba(255,255,255,0.85); border: 1px solid rgba(255,255,255,0.4); padding: 7px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; }
        .mode-tab:hover { background: rgba(255,255,255,0.28); color: white; }
        .mode-tab.active { background: white; color: #8b7355; }
        .mode-tab:disabled { opacity: 0.4; cursor: not-allowed; }

        /* ── Random mode (slideshow) ── */
        .slide { display: none; padding: 40px; animation: fadeIn 0.3s ease; }
        .slide.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        .photo-container { margin-bottom: 32px; text-align: center; }
        .photo { max-width: 100%; max-height: 400px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        .vocab-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-top: 32px; }
        .card { background: #f9f8f6; border: 2px solid #e0d9d0; border-radius: 8px; padding: 20px; text-align: center; cursor: pointer; transition: all 0.2s ease; min-height: 140px; display: flex; flex-direction: column; justify-content: center; }
        .card:hover { border-color: #8b7355; background: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateY(-2px); }
        .card.flipped { background: #f0ebe5; border-color: #8b7355; }
        .word-front { font-size: 32px; font-weight: 600; color: #2c2c2c; margin-bottom: 8px; line-height: 1.2; }
        .card.flipped .word-front { display: none; }
        .reveal { display: none; }
        .card.flipped .reveal { display: block; }
        .romanization { font-size: 13px; color: #8b7355; margin-bottom: 8px; font-weight: 500; }
        .english { font-size: 15px; color: #444; margin-bottom: 12px; font-weight: 600; }
        .example { font-size: 12px; color: #999; line-height: 1.4; margin-bottom: 8px; padding-top: 8px; border-top: 1px solid #e0d9d0; }
        .card.flipped .example { border-top: 1px solid #d4ccc0; }
        .audio-btn { margin-top: 8px; background: white; border: 1px solid #d4ccc0; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; transition: all 0.2s ease; color: #8b7355; font-weight: 500; }
        .audio-btn:hover { background: #f0ebe5; border-color: #8b7355; }
        .controls { display: flex; justify-content: space-between; align-items: center; padding: 0 40px 40px; gap: 16px; }
        .nav-btn { background: #8b7355; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s ease; }
        .nav-btn:hover { background: #a89080; transform: translateY(-1px); }
        .nav-btn:disabled { background: #d4ccc0; cursor: not-allowed; transform: none; }
        .counter { font-size: 14px; color: #8b7355; font-weight: 500; min-width: 60px; text-align: center; }
        .spacer { flex: 1; }

        /* ── Gallery mode ── */
        #gallery-panel { display: none; padding: 32px 40px 40px; animation: fadeIn 0.3s ease; }
        .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }
        .gallery-thumb { position: relative; border-radius: 8px; overflow: hidden; cursor: pointer; border: 2px solid transparent; transition: all 0.18s ease; aspect-ratio: 4/3; background: #f0ebe5; }
        .gallery-thumb:hover { border-color: #8b7355; box-shadow: 0 4px 14px rgba(0,0,0,0.18); transform: translateY(-2px); }
        .gallery-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
        .thumb-badge { position: absolute; bottom: 5px; right: 5px; background: rgba(139,115,85,0.88); color: white; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 10px; letter-spacing: 0.04em; }
        .gallery-thumb.no-game { opacity: 0.45; cursor: default; }
        .gallery-thumb.no-game:hover { border-color: transparent; box-shadow: none; transform: none; }

        /* ── Game panel (Click Target + Gallery single-photo) ── */
        #game-panel { display: none; padding: 32px 40px 40px; animation: fadeIn 0.3s ease; }
        .game-exit-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
        .game-exit-btn { background: none; border: 1.5px solid #d4ccc0; color: #8b7355; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; flex-shrink: 0; }
        .game-exit-btn:hover { background: #f0ebe5; border-color: #8b7355; }
        .quiz-heading { font-size: 13px; letter-spacing: 0.13em; text-transform: uppercase; color: #8b7355; font-weight: 600; }
        .streak-badge { font-size: 15px; font-weight: 700; color: #d4662a; margin-left: auto; letter-spacing: 0.02em; }
        .click-game { display: flex; flex-direction: column; align-items: center; gap: 14px; width: 100%; }
        .cg-prompt-row { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; justify-content: center; }
        .cg-find { font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase; color: #A09C95; }
        .cg-prompt-word { font-size: 34px; font-weight: 600; color: #3D6B5E; cursor: pointer; transition: color 0.15s; line-height: 1.1; }
        .cg-prompt-word:hover { color: #2A5448; }
        .photo-target-wrap { position: relative; border-radius: 14px; overflow: hidden; cursor: crosshair; border: 2px solid #EDE9E2; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 560px; width: 100%; }
        .target-photo { display: block; width: 100%; height: auto; pointer-events: none; user-select: none; }
        @keyframes dotIn { from { transform: translate(-50%,-50%) scale(0.2); opacity: 0; } to { transform: translate(-50%,-50%) scale(1); opacity: 1; } }
        .click-dot { position: absolute; width: 20px; height: 20px; border-radius: 50%; transform: translate(-50%,-50%); border: 2.5px solid white; pointer-events: none; z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,0.35); animation: dotIn 0.18s ease; }
        .click-dot.hit { background: #4A8C6A; }
        .click-dot.miss { background: #B85454; }
        .hotspot-box { position: absolute; border: 2.5px dashed #4A8C6A; border-radius: 6px; pointer-events: none; z-index: 9; opacity: 0; background: rgba(74,140,106,0.1); transition: opacity 0.3s ease; }
        .hotspot-box.show { opacity: 1; }
        .cg-status-row { display: flex; align-items: center; gap: 12px; min-height: 48px; flex-wrap: wrap; justify-content: center; }
        .cg-counter { font-size: 12px; letter-spacing: 0.1em; color: #A09C95; text-transform: uppercase; min-width: 48px; }
        .cg-feedback-wrap { text-align: center; min-width: 160px; }
        #q-feedback { font-size: 15px; font-style: italic; }
        .cg-english { font-size: 13px; color: #8b7355; font-weight: 500; margin-top: 3px; }
        #q-next { display: none; }
        .score-screen { text-align: center; padding: 24px 20px; }
        .q-score-text { font-size: 22px; color: #3D6B5E; font-weight: 600; margin-bottom: 20px; }
        .score-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
        .secondary-btn { background: #f0ebe5; color: #8b7355; border: 1.5px solid #d4ccc0; }
        .secondary-btn:hover { background: #e8ddd0; border-color: #8b7355; }

        /* ── Word Hunt mode ── */
        #wordhunt-panel { display: none; padding: 32px 40px 40px; animation: fadeIn 0.3s ease; }
        .wh-prompt { font-size: 16px; color: #5a544c; text-align: center; margin-bottom: 18px; line-height: 1.4; }
        .wh-photo-wrap { text-align: center; margin-bottom: 22px; }
        .wh-photo { max-width: 100%; max-height: 320px; border-radius: 12px; box-shadow: 0 4px 18px rgba(0,0,0,0.12); }
        .wh-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
        .wh-chip { padding: 16px 12px; border-radius: 10px; border: 2px solid #e0d9d0; background: #f9f8f6; cursor: pointer; text-align: center; font-size: 19px; font-weight: 600; color: #2c2c2c; transition: all 0.16s ease; line-height: 1.25; }
        .wh-chip:hover { border-color: #8b7355; background: #fff; transform: translateY(-1px); }
        .wh-chip.green { background: #e6f2ec; border-color: #4A8C6A; color: #2f5d4a; cursor: default; transform: none; }
        .wh-chip.green:hover { background: #e6f2ec; transform: none; }
        .wh-chip.red { background: #f7e6e6; border-color: #B85454; color: #8a3a3a; cursor: default; opacity: 0.75; }
        .wh-chip.red:hover { background: #f7e6e6; transform: none; }
        .wh-gloss { display: block; font-size: 13px; font-weight: 500; color: #4A8C6A; margin-top: 5px; }
        .wh-reading { display: block; font-size: 11px; font-weight: 500; color: #8b7355; margin-top: 2px; }
        .wh-counter { font-size: 13px; letter-spacing: 0.04em; color: #8b7355; font-weight: 600; }
        .wh-done { text-align: center; font-size: 17px; color: #3D6B5E; font-weight: 600; margin-top: 22px; }
        .wh-next-wrap { text-align: center; margin-top: 16px; min-height: 44px; }
        #wh-next { display: none; }

        @media (max-width: 600px) {
            .slide { padding: 24px; }
            .controls { padding: 0 24px 24px; }
            .vocab-cards { grid-template-columns: 1fr; }
            .photo { max-height: 300px; }
            .word-front { font-size: 28px; }
            .header h1 { font-size: 19px; }
            .picker-label { min-width: 0; text-align: center; }
            .lang-btn { padding: 6px 10px; font-size: 13px; }
            .mode-tab { padding: 6px 12px; font-size: 12px; }
            #gallery-panel, #game-panel, #wordhunt-panel { padding: 20px; }
            .gallery-grid { grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 8px; }
            .wh-grid { grid-template-columns: 1fr 1fr; gap: 8px; }
            .wh-chip { font-size: 17px; padding: 13px 8px; }
            .wh-photo { max-height: 240px; }
        }

        /* ── Dev bbox editor (hidden; toggled with the 'x' key) ── */
        #dev-panel { display: none; position: fixed; inset: 0; z-index: 9999; background: #1c1a17; color: #eee; flex-direction: column; font-family: inherit; }
        #dev-panel.active { display: flex; }
        .dev-top { display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: #2a2724; border-bottom: 1px solid #3a3631; flex-wrap: wrap; }
        .dev-title { font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; font-size: 12px; color: #d4a017; }
        .dev-btn { background: #3a3631; color: #eee; border: 1px solid #4a463f; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
        .dev-btn:hover { background: #4a463f; }
        .dev-btn.primary { background: #3D6B5E; border-color: #3D6B5E; }
        .dev-btn.primary:hover { background: #4A8C6A; }
        .dev-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .dev-fname { font-size: 12px; color: #aaa; font-family: monospace; }
        .dev-msg { font-size: 12px; margin-left: auto; min-height: 16px; }
        .dev-body { flex: 1; display: flex; min-height: 0; }
        .dev-stage { flex: 1; display: flex; align-items: center; justify-content: center; padding: 20px; overflow: auto; background: #141210; }
        .dev-imgwrap { position: relative; display: inline-block; user-select: none; line-height: 0; }
        .dev-imgwrap img { display: block; max-width: 100%; max-height: 80vh; }
        .dev-box { position: absolute; border: 2px solid #4A8C6A; background: rgba(74,140,106,0.18); box-sizing: border-box; cursor: move; }
        .dev-box.ghost { border: 1.5px dashed #6a6660; background: transparent; pointer-events: none; opacity: 0.55; }
        .dev-handle { position: absolute; right: -8px; bottom: -8px; width: 15px; height: 15px; background: #fff; border: 2px solid #3D6B5E; border-radius: 50%; cursor: nwse-resize; }
        .dev-del { position: absolute; right: -9px; top: -9px; width: 19px; height: 19px; background: #B85454; color: #fff; border: none; border-radius: 50%; font-size: 12px; line-height: 1; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; }
        .dev-side { width: 270px; background: #211e1b; border-left: 1px solid #3a3631; overflow-y: auto; padding: 12px; }
        .dev-side h4 { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: #888; margin-bottom: 8px; }
        .dev-word { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; background: #2a2724; border: 1px solid transparent; }
        .dev-word:hover { background: #332f2a; }
        .dev-word.sel { border-color: #d4a017; background: #332f2a; }
        .dev-word .dw-label { flex: 1; font-size: 14px; }
        .dev-word .dw-count { font-size: 11px; color: #888; white-space: nowrap; }
        .dev-word .dw-count.zero { color: #B85454; }
        .dev-addbox { width: 100%; margin-top: 10px; }
        .dev-hint { font-size: 11px; color: #777; margin-top: 14px; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">Lens</div>
            <h1 id="title">Learn from your photos</h1>
            <div class="picker-group">
                <div class="picker-row">
                    <span class="picker-label">I speak</span>
                    <div class="lang-picker" id="homePicker"></div>
                </div>
                <div class="picker-row">
                    <span class="picker-label">I'm learning</span>
                    <div class="lang-picker" id="targetPicker"></div>
                </div>
            </div>
            <div class="header-actions">
                <div class="mode-tabs">
                    <button class="mode-tab" data-mode="gallery">🖼 Gallery</button>
                    <button class="mode-tab active" data-mode="random">🔀 Random</button>
                    <button class="mode-tab" data-mode="clicktarget" id="tabClickTarget">🎯 Click Target</button>
                    <button class="mode-tab" data-mode="wordhunt" id="tabWordHunt">🔎 Word Hunt</button>
                </div>
            </div>
        </div>

        <!-- Random mode -->
        <div class="slides-container" id="slides-container"></div>
        <div class="controls" id="nav-controls">
            <button class="nav-btn" id="prevBtn">← Previous</button>
            <div class="spacer"></div>
            <div class="counter"><span id="currentSlide">1</span> / <span id="totalSlides">0</span></div>
            <div class="spacer"></div>
            <button class="nav-btn" id="nextBtn">Next →</button>
        </div>

        <!-- Gallery mode: photo grid -->
        <div id="gallery-panel">
            <div class="gallery-grid" id="gallery-grid"></div>
        </div>

        <!-- Game panel: shared by Click Target (all photos) and Gallery (single photo) -->
        <div id="game-panel">
            <div class="game-exit-bar">
                <button class="game-exit-btn" id="exitGameBtn">← back</button>
                <span class="quiz-heading" id="q-heading"></span>
                <span class="streak-badge" id="q-streak"></span>
            </div>
            <div id="q-main" class="click-game">
                <div class="cg-prompt-row">
                    <span class="cg-find" id="q-find"></span>
                    <span class="cg-prompt-word" id="q-word" onclick="qSpeak()"></span>
                </div>
                <div class="photo-target-wrap" id="q-wrap">
                    <img id="q-photo" class="target-photo" src="" alt="">
                </div>
                <div class="cg-status-row">
                    <span class="cg-counter" id="q-counter"></span>
                    <div class="cg-feedback-wrap">
                        <div id="q-feedback"></div>
                        <div class="cg-english" id="q-english"></div>
                    </div>
                    <button class="nav-btn" id="q-next">next →</button>
                </div>
            </div>
            <div id="q-score" class="score-screen" style="display:none">
                <div class="q-score-text"></div>
                <div class="score-actions">
                    <button class="nav-btn" id="q-replay">play again</button>
                    <button class="nav-btn secondary-btn" id="q-back-gallery" style="display:none">← gallery</button>
                </div>
            </div>
        </div>

        <!-- Word Hunt: photo + 10 word chips (5 in photo, 5 not) -->
        <div id="wordhunt-panel">
            <div class="game-exit-bar">
                <button class="game-exit-btn" id="exitWordHuntBtn">← random</button>
                <span class="quiz-heading" id="wh-heading"></span>
                <span class="wh-counter" id="wh-counter"></span>
            </div>
            <div class="wh-prompt" id="wh-prompt"></div>
            <div class="wh-photo-wrap">
                <img id="wh-photo" class="wh-photo" src="" alt="">
            </div>
            <div class="wh-grid" id="wh-grid"></div>
            <div class="wh-done" id="wh-done" style="display:none"></div>
            <div class="wh-next-wrap">
                <button class="nav-btn" id="wh-next"></button>
            </div>
        </div>
    </div>

    <!-- Dev bbox editor overlay — hidden until the 'x' key is pressed -->
    <div id="dev-panel">
        <div class="dev-top">
            <span class="dev-title">⚙ bbox editor</span>
            <button class="dev-btn" id="dev-prev">← photo</button>
            <span class="dev-fname" id="dev-counter"></span>
            <button class="dev-btn" id="dev-next">photo →</button>
            <span class="dev-fname" id="dev-fname"></span>
            <button class="dev-btn primary" id="dev-save">Save</button>
            <button class="dev-btn" id="dev-exit">Exit (x)</button>
            <span class="dev-msg" id="dev-msg"></span>
        </div>
        <div class="dev-body">
            <div class="dev-stage">
                <div class="dev-imgwrap" id="dev-imgwrap">
                    <img id="dev-img" src="" alt="">
                </div>
            </div>
            <div class="dev-side">
                <h4>Words — click one to edit its target box</h4>
                <div id="dev-words"></div>
                <button class="dev-btn primary dev-addbox" id="dev-addbox">+ add box to this word</button>
                <div class="dev-hint">Drag a green box to move it. Drag the corner dot to resize. ✕ deletes a box. Green = the word you're editing; gray dashed = the other words (for reference). Save writes to this photo's JSON, then run <b>deploy.py</b> to publish.</div>
            </div>
        </div>
    </div>

    <script>
        const photos = __PHOTOS_JSON__;
        let currentSlide = 0;
        let home = 'en';           // home language (the learner already speaks this)
        let target = 'ko';         // target language (the learner is studying this)
        let mode = 'random';       // 'random' | 'gallery' | 'clicktarget'
        let galleryPhotoIdx = -1;  // which photo is active in gallery single-photo game
        let streak = 0;

        // Six co-equal languages. Display label + Web-Speech code + in-language UI chrome.
        const LANG = {
            ko: { display: '한국어', enName: 'Korean', tts: 'ko-KR',
                  heading: '사진 게임 · 눌러보세요', find: '찾기', miss: '아쉬워요',
                  next: '다음 →', seeScore: '점수 보기 →', playAgain: '다시 하기',
                  backGallery: '← 갤러리',
                  huntPrompt: '이 사진에 있는 단어를 모두 찾으세요', found: '찾음',
                  huntDone: '다 찾았어요! 🎉', huntNext: '다음 사진 →',
                  score: (n, t) => n + ' / ' + t + ' 맞췄어요!' },
            ja: { display: '日本語', enName: 'Japanese', tts: 'ja-JP',
                  heading: '写真ゲーム · タップしよう', find: '探そう', miss: 'おしい',
                  next: '次へ →', seeScore: 'スコア →', playAgain: 'もう一度',
                  backGallery: '← ギャラリー',
                  huntPrompt: 'この写真にある単語をすべて見つけよう', found: '正解',
                  huntDone: '全部見つけた！🎉', huntNext: '次の写真 →',
                  score: (n, t) => n + ' / ' + t + ' 正解！' },
            es: { display: 'Español', enName: 'Spanish', tts: 'es-ES', article: true,
                  heading: 'Juego de fotos · toca el objeto', find: 'Busca', miss: 'casi',
                  next: 'siguiente →', seeScore: 'ver puntaje →', playAgain: 'otra vez',
                  backGallery: '← galería',
                  huntPrompt: 'Encuentra todas las palabras que están en la foto', found: 'halladas',
                  huntDone: '¡Las encontraste todas! 🎉', huntNext: 'otra foto →',
                  score: (n, t) => '¡' + n + ' de ' + t + '!' },
            fr: { display: 'Français', enName: 'French', tts: 'fr-FR', article: true,
                  heading: 'Jeu photo · touchez l’objet', find: 'Trouvez', miss: 'presque',
                  next: 'suivant →', seeScore: 'voir le score →', playAgain: 'recommencer',
                  backGallery: '← galerie',
                  huntPrompt: 'Trouvez tous les mots présents sur la photo', found: 'trouvés',
                  huntDone: 'Tout trouvé ! 🎉', huntNext: 'autre photo →',
                  score: (n, t) => n + ' / ' + t + ' trouvés !' },
            zh: { display: '中文', enName: 'Mandarin', tts: 'zh-CN',
                  heading: '照片游戏 · 点一下', find: '找一找', miss: '差一点',
                  next: '下一个 →', seeScore: '查看得分 →', playAgain: '再玩一次',
                  backGallery: '← 图库',
                  huntPrompt: '找出照片里出现的所有词', found: '已找到',
                  huntDone: '全部找到了！🎉', huntNext: '下一张 →',
                  score: (n, t) => n + ' / ' + t + ' 答对了！' },
            en: { display: 'English', enName: 'English', tts: 'en-US',
                  heading: 'Photo game · tap the object', find: 'Find', miss: 'so close',
                  next: 'next →', seeScore: 'see score →', playAgain: 'play again',
                  backGallery: '← gallery',
                  huntPrompt: 'Find all the words that are in the photo', found: 'found',
                  huntDone: 'You found them all! 🎉', huntNext: 'next photo →',
                  score: (n, t) => n + ' / ' + t + ' correct!' },
        };
        const LANG_ORDER = ['ko', 'ja', 'es', 'fr', 'zh', 'en'];

        // Word label: Romance articles (le/la, el/la) sit BEFORE the noun;
        // romanization/pinyin sits AFTER with a separator.
        function wordLabel(code, w) {
            if (!w || !w.word) return w && w.word || '';
            const r = w.reading || '';
            if (!r) return w.word;
            return LANG[code] && LANG[code].article ? (r + ' ' + w.word) : (w.word + ' · ' + r);
        }

        // ── Schema accessors (every concept carries all six languages) ──
        function conceptsFor(photo) { return photo.concepts || []; }
        function tFor(c) { return (c && c.langs && c.langs[target]) || {}; }
        function hFor(c) { return (c && c.langs && c.langs[home]) || {}; }

        // ── Preferences (home/target persist across visits) ──
        function loadPrefs() {
            try {
                const h = localStorage.getItem('lensHome');
                const t = localStorage.getItem('lensTarget');
                if (h && LANG[h]) home = h;
                if (t && LANG[t]) target = t;
            } catch (e) {}
            if (home === target) { home = 'en'; target = (home === 'ko') ? 'ja' : 'ko'; }
        }
        function savePrefs() {
            try { localStorage.setItem('lensHome', home); localStorage.setItem('lensTarget', target); } catch (e) {}
        }

        // Challenges are language-independent: photo index + concept index + hotspot boxes.
        function buildChallenges() {
            const list = [];
            photos.forEach((photo, pIdx) => {
                const boxes = photo.bbox || [];
                boxes.forEach((b, wIdx) => {
                    if (Array.isArray(b) && b.length) list.push({ photo: pIdx, word: wIdx, hotspot: b });
                });
            });
            return list;
        }
        const QUIZ = buildChallenges();
        const hasQuiz = QUIZ.length > 0;

        let qChallenges = [], qIdx = 0, qScore = 0;

        // ── Word Hunt pool ──────────────────────────────────────────
        // Language-independent identity for a concept (English word, falling back
        // to Korean) so a word can never be both a correct answer and a distractor,
        // and dedup survives language switches.
        function conceptId(pIdx, wIdx) {
            const c = (photos[pIdx].concepts || [])[wIdx] || {};
            const en = c.langs && c.langs.en && c.langs.en.word;
            const ko = c.langs && c.langs.ko && c.langs.ko.word;
            return (en || ko || (pIdx + ':' + wIdx)).toLowerCase().trim();
        }
        // Every concept across every photo, as {pIdx, wIdx} — the distractor pool.
        const WH_ALL = [];
        photos.forEach((p, pIdx) => (p.concepts || []).forEach((c, wIdx) => WH_ALL.push({ pIdx, wIdx })));
        // A photo is playable if it has >=2 concepts to hunt for.
        const WH_PHOTOS = photos.map((p, i) => i).filter(i => (photos[i].concepts || []).length >= 2);
        const hasWordHunt = WH_PHOTOS.length >= 1 && WH_ALL.length >= 6;

        const WH_TOTAL = 10, WH_MAX_CORRECT = 5;
        let whOrder = [], whRound = 0, whChips = [], whFound = 0, whTarget = 0;

        // ── Utilities ───────────────────────────────────────────────

        function speak(text, langCode) {
            try {
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance(text);
                u.lang = langCode || 'en-US'; u.rate = 0.9;
                window.speechSynthesis.speak(u);
            } catch (e) {}
        }

        function qShuffle(arr) {
            const a = [...arr];
            for (let i = a.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [a[i], a[j]] = [a[j], a[i]];
            }
            return a;
        }

        function qConcept() {
            const ch = qChallenges[qIdx];
            if (!ch) return null;
            return (photos[ch.photo].concepts || [])[ch.word] || null;
        }

        // The prompt shows the TARGET-language word (the one being learned) to find
        // in the photo. Clicking it pronounces that target word; the home-language
        // meaning is the reward/confirmation on a hit.
        function qSpeak() {
            const c = qConcept();
            if (!c) return;
            const t = tFor(c);
            if (t.word) speak(t.word, LANG[target].tts);
        }

        function qRenderPrompt() {
            const c = qConcept();
            if (!c) return;
            document.getElementById('q-heading').textContent = LANG[target].heading;
            document.getElementById('q-find').textContent = LANG[target].find;
            document.getElementById('q-word').textContent = wordLabel(target, tFor(c));
        }

        function updateStreak(hit) {
            if (hit === null) { streak = 0; }
            else if (hit) { streak++; }
            else { streak = 0; }
            const el = document.getElementById('q-streak');
            el.textContent = streak >= 2 ? '🔥 ' + streak : '';
        }

        // ── Picker rendering ────────────────────────────────────────

        function renderPickers() {
            const fill = (id, current, other) => {
                document.getElementById(id).innerHTML = LANG_ORDER.map(code =>
                    '<button class="lang-btn' + (code === current ? ' active' : '') + '" data-lang="' + code + '"'
                    + (code === other ? ' disabled' : '') + '>' + LANG[code].display + '</button>'
                ).join('');
            };
            fill('homePicker', home, target);
            fill('targetPicker', target, home);
        }

        // ── Panel switching ─────────────────────────────────────────

        function showPanel(which) {
            document.getElementById('slides-container').style.display = which === 'random'  ? '' : 'none';
            document.getElementById('nav-controls').style.display    = which === 'random'  ? '' : 'none';
            document.getElementById('gallery-panel').style.display   = which === 'gallery' ? 'block' : 'none';
            document.getElementById('game-panel').style.display      = which === 'game'    ? 'block' : 'none';
            document.getElementById('wordhunt-panel').style.display  = which === 'wordhunt'? 'block' : 'none';
        }

        function setMode(newMode) {
            if (newMode === 'clicktarget' && !hasQuiz) return;
            if (newMode === 'wordhunt' && !hasWordHunt) return;
            mode = newMode;
            document.querySelectorAll('.mode-tab').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
            try { window.speechSynthesis.cancel(); } catch(e) {}
            if (mode === 'random') {
                showPanel('random');
            } else if (mode === 'gallery') {
                galleryPhotoIdx = -1;
                showPanel('gallery');
                renderGallery();
            } else if (mode === 'clicktarget') {
                showPanel('game');
                document.getElementById('exitGameBtn').textContent = '← random';
                document.getElementById('exitGameBtn').onclick = () => setMode('random');
                streak = 0; updateStreak(null);
                qStartAllPhotos();
            } else if (mode === 'wordhunt') {
                showPanel('wordhunt');
                whStart();
            }
        }

        // ── Gallery ─────────────────────────────────────────────────

        function renderGallery() {
            const grid = document.getElementById('gallery-grid');
            grid.innerHTML = '';
            photos.forEach((photo, idx) => {
                const challenges = QUIZ.filter(ch => ch.photo === idx);
                const div = document.createElement('div');
                div.className = 'gallery-thumb' + (challenges.length === 0 ? ' no-game' : '');
                div.innerHTML = `<img src="${encodeURI(photo.local_image || '')}" alt="${photo.scene || ''}" onerror="this.style.opacity=0.3">
                    ${challenges.length > 0 ? `<span class="thumb-badge">${challenges.length}</span>` : ''}`;
                if (challenges.length > 0) {
                    div.addEventListener('click', () => selectGalleryPhoto(idx));
                }
                grid.appendChild(div);
            });
        }

        function selectGalleryPhoto(pIdx) {
            galleryPhotoIdx = pIdx;
            showPanel('game');
            document.getElementById('exitGameBtn').textContent = '← gallery';
            document.getElementById('exitGameBtn').onclick = returnToGallery;
            streak = 0; updateStreak(null);
            qStartSinglePhoto(pIdx);
        }

        function returnToGallery() {
            galleryPhotoIdx = -1;
            showPanel('gallery');
            try { window.speechSynthesis.cancel(); } catch(e) {}
        }

        // ── Game: start ─────────────────────────────────────────────

        function qStartAllPhotos() {
            qChallenges = qShuffle(QUIZ);
            qIdx = 0; qScore = 0;
            document.getElementById('q-score').style.display = 'none';
            document.getElementById('q-main').style.display = '';
            qLoad();
        }

        function qStartSinglePhoto(pIdx) {
            qChallenges = QUIZ.filter(ch => ch.photo === pIdx);
            if (!qChallenges.length) { returnToGallery(); return; }
            qIdx = 0; qScore = 0;
            document.getElementById('q-score').style.display = 'none';
            document.getElementById('q-main').style.display = '';
            qLoad();
        }

        // ── Game: load & click ──────────────────────────────────────

        function qLoad() {
            const ch = qChallenges[qIdx];
            if (!ch) return;
            document.getElementById('q-photo').src = encodeURI(photos[ch.photo].local_image || '');
            qRenderPrompt();
            document.getElementById('q-feedback').textContent = '';
            document.getElementById('q-feedback').style.color = '#7A7770';
            document.getElementById('q-english').textContent = '';
            document.getElementById('q-counter').textContent = (qIdx + 1) + ' / ' + qChallenges.length;
            const nxt = document.getElementById('q-next');
            nxt.style.display = 'none'; nxt.onclick = null;
            const wrap = document.getElementById('q-wrap');
            wrap.querySelectorAll('.click-dot, .hotspot-box').forEach(e => e.remove());
            wrap.style.cursor = 'crosshair';
            wrap.onclick = qClick;
        }

        function qClick(e) {
            const ch = qChallenges[qIdx];
            const wrap = document.getElementById('q-wrap');
            const img  = document.getElementById('q-photo');
            const rect = img.getBoundingClientRect();
            const xPct = (e.clientX - rect.left) / rect.width  * 100;
            const yPct = (e.clientY - rect.top)  / rect.height * 100;
            const hit  = ch.hotspot.some(hs => xPct >= hs.x1 && xPct <= hs.x2 && yPct >= hs.y1 && yPct <= hs.y2);

            wrap.onclick = null;
            wrap.style.cursor = 'default';

            const dot = document.createElement('div');
            dot.className = 'click-dot ' + (hit ? 'hit' : 'miss');
            dot.style.left = xPct + '%'; dot.style.top = yPct + '%';
            wrap.appendChild(dot);

            ch.hotspot.forEach(hs => {
                const box = document.createElement('div');
                box.className = 'hotspot-box';
                box.style.left   = hs.x1 + '%';  box.style.top    = hs.y1 + '%';
                box.style.width  = (hs.x2 - hs.x1) + '%';
                box.style.height = (hs.y2 - hs.y1) + '%';
                wrap.appendChild(box);
                requestAnimationFrame(() => box.classList.add('show'));
            });

            const c   = qConcept();
            const t   = tFor(c);
            const h   = hFor(c);
            const fb  = document.getElementById('q-feedback');
            const eng = document.getElementById('q-english');
            if (hit) {
                qScore++;
                fb.textContent = h.word ? '✓ ' + h.word : '✓';
                fb.style.color = '#3D6B5E';
            } else {
                fb.textContent = '✗ ' + LANG[target].miss;
                fb.style.color = '#B85454';
            }
            // Reveal the home-language meaning as confirmation; speak the target word.
            eng.textContent = h.word || '';
            if (t.word) speak(t.word, LANG[target].tts);
            updateStreak(hit);

            const nxt = document.getElementById('q-next');
            nxt.style.display = 'inline-block';
            if (qIdx >= qChallenges.length - 1) {
                nxt.textContent = LANG[target].seeScore;
                nxt.onclick = qFinish;
            } else {
                nxt.textContent = LANG[target].next;
                nxt.onclick = () => { qIdx++; qLoad(); };
            }
        }

        function qFinish() {
            document.getElementById('q-main').style.display = 'none';
            const scr = document.getElementById('q-score');
            scr.querySelector('.q-score-text').textContent = LANG[target].score(qScore, qChallenges.length);
            const replayBtn  = document.getElementById('q-replay');
            const galleryBtn = document.getElementById('q-back-gallery');
            replayBtn.textContent = LANG[target].playAgain;
            if (mode === 'gallery') {
                replayBtn.onclick = () => qStartSinglePhoto(galleryPhotoIdx);
                galleryBtn.textContent = LANG[target].backGallery;
                galleryBtn.style.display = 'inline-block';
                galleryBtn.onclick = returnToGallery;
            } else {
                replayBtn.onclick = qStartAllPhotos;
                galleryBtn.style.display = 'none';
            }
            scr.style.display = '';
        }

        // ── Word Hunt ───────────────────────────────────────────────
        // Show a photo + 10 target-language words: WH_MAX_CORRECT belong to the
        // photo, the rest are distractors from other photos. Click a word -> green
        // (in photo) or red (not). When every correct word is found, the greens
        // reveal their home-language translations.

        function whStart() {
            whOrder = qShuffle(WH_PHOTOS);
            whRound = 0;
            whLoad();
        }

        function whLoad() {
            const pIdx = whOrder[whRound];
            const concepts = photos[pIdx].concepts || [];
            const correct = qShuffle(concepts.map((c, wIdx) => ({ pIdx, wIdx }))).slice(0, WH_MAX_CORRECT);
            // Distractors: concepts from OTHER photos, deduped by meaning.
            const seen = new Set(correct.map(ch => conceptId(ch.pIdx, ch.wIdx)));
            const distractors = [];
            for (const ch of qShuffle(WH_ALL.filter(ch => ch.pIdx !== pIdx))) {
                if (distractors.length >= WH_TOTAL - correct.length) break;
                const id = conceptId(ch.pIdx, ch.wIdx);
                if (seen.has(id)) continue;
                seen.add(id);
                distractors.push(ch);
            }
            whTarget = correct.length;
            whFound = 0;
            whChips = qShuffle(
                correct.map(ch => ({ ...ch, correct: true, clicked: false, revealed: false }))
                .concat(distractors.map(ch => ({ ...ch, correct: false, clicked: false, revealed: false }))));
            document.getElementById('wh-photo').src = encodeURI(photos[pIdx].local_image || '');
            document.getElementById('wh-done').style.display = 'none';
            document.getElementById('wh-next').style.display = 'none';
            whRenderStrings();
            whRenderChips();
        }

        function whRenderStrings() {
            document.getElementById('wh-heading').textContent = LANG[target].heading;
            document.getElementById('wh-prompt').textContent = LANG[target].huntPrompt;
            document.getElementById('wh-counter').textContent = whFound + ' / ' + whTarget + ' ' + LANG[target].found;
            document.getElementById('wh-done').textContent = LANG[target].huntDone;
            document.getElementById('wh-next').textContent = LANG[target].huntNext;
        }

        function whRenderChips() {
            const grid = document.getElementById('wh-grid');
            grid.innerHTML = '';
            whChips.forEach((chip, i) => {
                const c = (photos[chip.pIdx].concepts || [])[chip.wIdx];
                const t = (c && c.langs && c.langs[target]) || {};
                const el = document.createElement('div');
                el.className = 'wh-chip' + (chip.clicked ? (chip.correct ? ' green' : ' red') : '');
                let html = '<span class="wh-word">' + wordLabel(target, t) + '</span>';
                if (chip.revealed) {
                    const h = (c && c.langs && c.langs[home]) || {};
                    if (h.word) html += '<span class="wh-gloss">' + h.word + '</span>';
                }
                el.innerHTML = html;
                if (!chip.clicked) el.addEventListener('click', () => whClick(i));
                grid.appendChild(el);
            });
        }

        function whClick(i) {
            const chip = whChips[i];
            if (chip.clicked) return;
            chip.clicked = true;
            const c = (photos[chip.pIdx].concepts || [])[chip.wIdx];
            const t = (c && c.langs && c.langs[target]) || {};
            if (t.word) speak(t.word, LANG[target].tts);
            if (chip.correct) whFound++;
            whRenderStrings();
            whRenderChips();
            if (whFound >= whTarget) whComplete();
        }

        function whComplete() {
            whChips.forEach(ch => { if (ch.correct) ch.revealed = true; });
            whRenderChips();
            document.getElementById('wh-done').style.display = 'block';
            const nxt = document.getElementById('wh-next');
            nxt.style.display = 'inline-block';
            nxt.onclick = () => {
                whRound++;
                if (whRound >= whOrder.length) { whOrder = qShuffle(WH_PHOTOS); whRound = 0; }
                whLoad();
            };
        }

        // ── Slideshow ───────────────────────────────────────────────

        function renderSlides() {
            const container = document.getElementById('slides-container');
            container.innerHTML = '';
            document.getElementById('title').textContent = LANG[target].enName + ' from your photos';
            renderPickers();
            if (!hasQuiz) document.getElementById('tabClickTarget').disabled = true;
            if (!hasWordHunt) document.getElementById('tabWordHunt').disabled = true;
            photos.forEach((photo, idx) => {
                const slide = document.createElement('div');
                slide.className = 'slide' + (idx === currentSlide ? ' active' : '');
                const photoUrl = encodeURI(photo.local_image || '');
                const concepts = conceptsFor(photo);
                slide.innerHTML = `
                    <div class="photo-container">
                        <img src="${photoUrl}" alt="${photo.scene || ''}" class="photo" onerror="this.style.display='none'" />
                    </div>
                    <div class="vocab-cards">
                        ${concepts.map((c, widx) => {
                            const t = c.langs && c.langs[target] || {};
                            const h = c.langs && c.langs[home] || {};
                            const isArt = LANG[target] && LANG[target].article;
                            const front = isArt ? wordLabel(target, t) : (t.word || '');
                            const reading = (!isArt && t.reading) ? t.reading : '';
                            return `<div class="card" data-photo="${idx}" data-word="${widx}">
                                <div class="word-front">${front}</div>
                                <div class="reveal">
                                    ${reading ? `<div class="romanization">${reading}</div>` : ''}
                                    <div class="english">${h.word || ''}</div>
                                    ${t.example ? `<div class="example"><div>${t.example}</div></div>` : ''}
                                    <button class="audio-btn">🔊 Audio</button>
                                </div>
                            </div>`;
                        }).join('')}
                    </div>`;
                container.appendChild(slide);
            });
            document.getElementById('totalSlides').textContent = photos.length;
            attachCardListeners();
            updateNav();
        }

        function attachCardListeners() {
            document.querySelectorAll('.card').forEach(card => {
                card.addEventListener('click', function() { this.classList.toggle('flipped'); });
            });
            document.querySelectorAll('.audio-btn').forEach(btn => {
                btn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const card = this.closest('.card');
                    const c = (photos[+card.dataset.photo].concepts || [])[+card.dataset.word];
                    const t = c && c.langs && c.langs[target];
                    if (t && t.word) speak(t.word, LANG[target].tts);
                });
            });
        }

        function showSlide(n) {
            currentSlide = Math.max(0, Math.min(n, photos.length - 1));
            document.querySelectorAll('.slide').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.slide')[currentSlide].classList.add('active');
            document.getElementById('currentSlide').textContent = currentSlide + 1;
            updateNav();
        }

        function updateNav() {
            document.getElementById('prevBtn').disabled = currentSlide === 0;
            document.getElementById('nextBtn').disabled = currentSlide === photos.length - 1;
        }

        // ── Language changes (home / target) ────────────────────────

        function afterLangChange() {
            renderSlides();
            if (mode === 'random') {
                showSlide(currentSlide);
            } else if (mode === 'clicktarget' || (mode === 'gallery' && galleryPhotoIdx >= 0)) {
                qRenderPrompt();
            } else if (mode === 'wordhunt') {
                whRenderStrings();
                whRenderChips();
            }
        }

        function setHome(next) {
            if (!LANG[next] || next === home) return;
            if (next === target) { target = LANG_ORDER.find(c => c !== next); }
            home = next;
            savePrefs();
            afterLangChange();
        }

        function setTarget(next) {
            if (!LANG[next] || next === target) return;
            if (next === home) { home = LANG_ORDER.find(c => c !== next); }
            target = next;
            savePrefs();
            afterLangChange();
        }

        // ── Event listeners ─────────────────────────────────────────

        document.querySelectorAll('.mode-tab').forEach(tab => {
            tab.addEventListener('click', () => setMode(tab.dataset.mode));
        });
        document.getElementById('exitWordHuntBtn').addEventListener('click', () => setMode('random'));
        document.getElementById('prevBtn').addEventListener('click', () => showSlide(currentSlide - 1));
        document.getElementById('nextBtn').addEventListener('click', () => showSlide(currentSlide + 1));
        document.getElementById('homePicker').addEventListener('click', (e) => {
            const btn = e.target.closest('.lang-btn');
            if (btn && !btn.disabled) setHome(btn.dataset.lang);
        });
        document.getElementById('targetPicker').addEventListener('click', (e) => {
            const btn = e.target.closest('.lang-btn');
            if (btn && !btn.disabled) setTarget(btn.dataset.lang);
        });
        document.addEventListener('keydown', (e) => {
            if (mode !== 'random') return;
            if (e.key === 'ArrowLeft')  showSlide(currentSlide - 1);
            if (e.key === 'ArrowRight') showSlide(currentSlide + 1);
        });

        // ── Dev bbox editor ─────────────────────────────────────────
        // Hidden tool, toggled with the 'x' key. Lets you drag/resize/add/
        // delete the green click-target boxes per word and save them back to
        // the source JSON. Saving only works when the page is served from the
        // local bbox_editor.py server (localhost); on the public site the
        // editor is read-only so nothing here can touch the live data.
        const DEV_CAN_SAVE = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
        let devActive = false, devPhoto = 0, devSel = 0, devBbox = null, devDirty = false;

        function clampPct(v) { return Math.max(0, Math.min(100, v)); }
        function round1(v) { return Math.round(v * 10) / 10; }
        function devClone(b) { return JSON.parse(JSON.stringify(b == null ? null : b)); }
        function devMsg(t, c) { const m = document.getElementById('dev-msg'); m.textContent = t || ''; m.style.color = c || '#888'; }

        function devEnter() {
            devActive = true;
            document.getElementById('dev-panel').classList.add('active');
            try { window.speechSynthesis.cancel(); } catch (e) {}
            const save = document.getElementById('dev-save');
            save.disabled = !DEV_CAN_SAVE;
            devLoadPhoto(devPhoto);
            if (!DEV_CAN_SAVE) devMsg('read-only — run bbox_editor.py to save', '#d4a017');
        }
        function devExit() {
            if (devDirty && !confirm('Unsaved changes on this photo will be lost. Exit anyway?')) return;
            devActive = false;
            document.getElementById('dev-panel').classList.remove('active');
        }

        function devLoadPhoto(idx) {
            devPhoto = Math.max(0, Math.min(idx, photos.length - 1));
            const p = photos[devPhoto];
            const concepts = p.concepts || [];
            // Normalize bbox to concept length: each slot is an array of boxes or null.
            let b = devClone(p.bbox) || [];
            while (b.length < concepts.length) b.push(null);
            b = b.slice(0, concepts.length).map(x =>
                Array.isArray(x) ? x.map(r => ({ x1: +r.x1, y1: +r.y1, x2: +r.x2, y2: +r.y2 })) : null);
            devBbox = b;
            devSel = 0; devDirty = false;
            document.getElementById('dev-img').src = encodeURI(p.local_image || '');
            document.getElementById('dev-counter').textContent = (devPhoto + 1) + ' / ' + photos.length;
            document.getElementById('dev-fname').textContent = p.photo || '';
            devMsg('');
            devRenderWords();
            devRenderBoxes();
        }

        function devWordLabel(i) {
            const c = (photos[devPhoto].concepts || [])[i] || {};
            const en = c.langs && c.langs.en && c.langs.en.word;
            const ko = c.langs && c.langs.ko && c.langs.ko.word;
            return en || ko || ('word ' + (i + 1));
        }

        function devRenderWords() {
            const wrap = document.getElementById('dev-words');
            const concepts = photos[devPhoto].concepts || [];
            wrap.innerHTML = '';
            concepts.forEach((c, i) => {
                const n = Array.isArray(devBbox[i]) ? devBbox[i].length : 0;
                const el = document.createElement('div');
                el.className = 'dev-word' + (i === devSel ? ' sel' : '');
                el.innerHTML = '<span class="dw-label">' + devWordLabel(i) + '</span>'
                    + '<span class="dw-count' + (n === 0 ? ' zero' : '') + '">' + n + (n === 1 ? ' box' : ' boxes') + '</span>';
                el.addEventListener('click', () => { devSel = i; devRenderWords(); devRenderBoxes(); });
                wrap.appendChild(el);
            });
        }

        function devPlace(el, r) {
            el.style.left = r.x1 + '%'; el.style.top = r.y1 + '%';
            el.style.width = (r.x2 - r.x1) + '%'; el.style.height = (r.y2 - r.y1) + '%';
        }

        function devPct(e) {
            const rect = document.getElementById('dev-img').getBoundingClientRect();
            return { x: clampPct((e.clientX - rect.left) / rect.width * 100),
                     y: clampPct((e.clientY - rect.top) / rect.height * 100) };
        }

        function devRenderBoxes() {
            const wrap = document.getElementById('dev-imgwrap');
            wrap.querySelectorAll('.dev-box').forEach(e => e.remove());
            // Ghost boxes: the other words' targets, for reference (non-interactive).
            devBbox.forEach((boxes, wi) => {
                if (wi === devSel || !Array.isArray(boxes)) return;
                boxes.forEach(r => { const g = document.createElement('div'); g.className = 'dev-box ghost'; devPlace(g, r); wrap.appendChild(g); });
            });
            // Selected word's boxes: draggable, resizable, deletable.
            const sel = devBbox[devSel];
            if (Array.isArray(sel)) {
                sel.forEach((r, bi) => {
                    const box = document.createElement('div');
                    box.className = 'dev-box';
                    devPlace(box, r);
                    const del = document.createElement('button');
                    del.className = 'dev-del'; del.textContent = '✕';
                    del.addEventListener('mousedown', e => e.stopPropagation());
                    del.addEventListener('click', e => { e.stopPropagation(); sel.splice(bi, 1); devDirty = true; devRenderWords(); devRenderBoxes(); });
                    const h = document.createElement('div'); h.className = 'dev-handle';
                    box.appendChild(del); box.appendChild(h);
                    devWireBox(box, h, r);
                    wrap.appendChild(box);
                });
            }
        }

        function devWireBox(box, handle, r) {
            // Move: drag the box body.
            box.addEventListener('mousedown', e => {
                if (e.target === handle || e.target.classList.contains('dev-del')) return;
                e.preventDefault();
                const start = devPct(e), ox = start.x - r.x1, oy = start.y - r.y1;
                const w = r.x2 - r.x1, hgt = r.y2 - r.y1;
                function mv(ev) {
                    const p = devPct(ev);
                    let nx1 = Math.min(clampPct(p.x - ox), 100 - w);
                    let ny1 = Math.min(clampPct(p.y - oy), 100 - hgt);
                    r.x1 = nx1; r.y1 = ny1; r.x2 = nx1 + w; r.y2 = ny1 + hgt; devPlace(box, r);
                }
                function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); devDirty = true; }
                document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
            });
            // Resize: drag the corner handle.
            handle.addEventListener('mousedown', e => {
                e.preventDefault(); e.stopPropagation();
                function mv(ev) { const p = devPct(ev); r.x2 = Math.max(r.x1 + 2, p.x); r.y2 = Math.max(r.y1 + 2, p.y); devPlace(box, r); }
                function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); devDirty = true; }
                document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
            });
        }

        function devAddBox() {
            if (!Array.isArray(devBbox[devSel])) devBbox[devSel] = [];
            devBbox[devSel].push({ x1: 38, y1: 38, x2: 62, y2: 62 });
            devDirty = true; devRenderWords(); devRenderBoxes();
        }

        function devSave() {
            if (!DEV_CAN_SAVE) return;
            const payload = {
                photo: photos[devPhoto].photo,
                bbox: devBbox.map(b => (Array.isArray(b) && b.length)
                    ? b.map(r => ({ x1: round1(r.x1), y1: round1(r.y1), x2: round1(r.x2), y2: round1(r.y2) }))
                    : null),
            };
            devMsg('saving…', '#d4a017');
            fetch('/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
                .then(r => r.json())
                .then(d => {
                    if (d.ok) { photos[devPhoto].bbox = devClone(payload.bbox); devDirty = false; devMsg('saved ✓ ' + (d.file || ''), '#4A8C6A'); }
                    else devMsg('save failed: ' + (d.error || '?'), '#B85454');
                })
                .catch(err => devMsg('save failed: ' + err, '#B85454'));
        }

        function devGuardSwitch(delta) {
            if (devDirty && !confirm('Unsaved changes will be lost. Switch photo anyway?')) return;
            devLoadPhoto(devPhoto + delta);
        }

        document.getElementById('dev-prev').addEventListener('click', () => devGuardSwitch(-1));
        document.getElementById('dev-next').addEventListener('click', () => devGuardSwitch(1));
        document.getElementById('dev-addbox').addEventListener('click', devAddBox);
        document.getElementById('dev-save').addEventListener('click', devSave);
        document.getElementById('dev-exit').addEventListener('click', devExit);
        // Re-place boxes once the image has real dimensions.
        document.getElementById('dev-img').addEventListener('load', () => { if (devActive) devRenderBoxes(); });

        document.addEventListener('keydown', e => {
            if (e.key !== 'x' && e.key !== 'X') return;
            const tag = (e.target && e.target.tagName) || '';
            if (tag === 'INPUT' || tag === 'TEXTAREA') return;
            e.preventDefault();
            devActive ? devExit() : devEnter();
        });

        loadPrefs();
        renderSlides();
        showSlide(0);

        // Auto-open the bbox editor when launched from the dashboard's "Edit boxes"
        // button: bbox_editor.py opens this page at #edit. Localhost only, so the
        // public GitHub Pages copy never auto-enters the (read-only) editor.
        if (DEV_CAN_SAVE && /edit/i.test(location.hash)) devEnter();
        // Also handle the case where the tab was already open and bbox_editor.py
        // just re-pointed it at #edit (no reload fires the load-time check above).
        window.addEventListener('hashchange', () => {
            if (DEV_CAN_SAVE && /edit/i.test(location.hash) && !devActive) devEnter();
        });
    </script>
</body>
</html>'''

    return template.replace("__PHOTOS_JSON__", photos_json)


def deploy():
    """Generate HTML from JSON metadata."""
    feedback_dir = Path.home() / "Dropbox" / "KRAMOS" / "korean-photo-feedback"
    repo_dir = Path("/Users/ggibson1/Desktop/Kramer-Projects-2026/korean-photo-slideshow")
    docs_dir = repo_dir / "docs"

    if not feedback_dir.exists():
        print(f"Error: {feedback_dir} not found")
        return False

    docs_dir.mkdir(exist_ok=True)

    # Read all JSON files
    photos = []
    for json_file in sorted(feedback_dir.glob("*.json")):
        if json_file.name == "photo-vocab-log.json":
            continue
        try:
            with open(json_file) as f:
                data = json.load(f)
                # Skip malformed/old-schema photos rather than crashing the build.
                if not isinstance(data, dict) or "concepts" not in data:
                    print(f"Warning: {json_file.name}: no 'concepts' (old schema?) — skipped")
                    continue
                photos.append(data)
        except Exception as e:
            print(f"Warning: {json_file}: {e}")

    if not photos:
        print("No photos found!")
        return False

    # Downscale each source photo into docs/photos/ and set photo['local_image'].
    photos_out_dir = docs_dir / "photos"
    statuses = {}
    for p in photos:
        st = prepare_image(p, photos_out_dir)
        statuses[st] = statuses.get(st, 0) + 1
        if st == "MISSING":
            print(f"  ! no image for: {p.get('photo')}")

    # Generate HTML
    html = build_html(photos)
    html_file = docs_dir / "index.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)

    # Per-language concept counts (every concept carries all six languages, so the
    # count is the same across languages; report total concepts + per-language fill).
    total_concepts = sum(len(p.get("concepts", [])) for p in photos)
    fill = {}
    for code in LANG_CODES:
        fill[code] = sum(
            1 for p in photos for c in p.get("concepts", [])
            if (c.get("langs", {}).get(code, {}) or {}).get("word")
        )
    print(f"✓ Generated {html_file}")
    print(f"✓ {len(photos)} photo(s) — {total_concepts} concept(s)")
    print(f"✓ language fill: {', '.join(f'{k}={fill[k]}' for k in LANG_CODES)}")
    print(f"✓ images: {', '.join(f'{k}={v}' for k, v in sorted(statuses.items()))}")
    return True


if __name__ == "__main__":
    import os
    os.chdir("/Users/ggibson1/Desktop/Kramer-Projects-2026/korean-photo-slideshow")
    if deploy():
        print("\nReady to deploy!")
