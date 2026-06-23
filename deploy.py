#!/usr/bin/env python3
"""Generate KKAS slideshow HTML.

Renders Korean, Japanese, and Spanish vocab from the same per-photo JSONs and a
header language picker (한국어 · 日本語 · Español). Korean comes from each photo's
`words` array; Japanese from `words_ja`; Spanish from `words_es` — all three are
parallel arrays mirroring the same concepts. Only Korean has audio so far, so the
audio button only shows in Korean mode.

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
    """Build HTML with embedded JSON data. Images are served from docs/photos/."""
    photos_json = json.dumps(photos, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lens — learn from your photos</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: linear-gradient(135deg, #f5ede4 0%, #e8ddd0 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .container {{ max-width: 900px; width: 100%; background: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #8b7355 0%, #a89080 100%); color: white; padding: 24px; text-align: center; }}
        .header .brand {{ font-size: 13px; font-weight: 700; letter-spacing: 0.28em; text-transform: uppercase; opacity: 0.8; margin-bottom: 4px; }}
        .header h1 {{ font-size: 22px; font-weight: 500; letter-spacing: 0.5px; margin-bottom: 16px; opacity: 0.92; }}
        .lang-picker {{ display: inline-flex; gap: 4px; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.35); border-radius: 22px; padding: 4px; backdrop-filter: blur(4px); }}
        .lang-btn {{ background: transparent; color: rgba(255,255,255,0.85); border: none; padding: 7px 16px; border-radius: 18px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; }}
        .lang-btn:hover {{ color: white; background: rgba(255,255,255,0.18); }}
        .lang-btn.active {{ background: white; color: #8b7355; }}
        .slide {{ display: none; padding: 40px; animation: fadeIn 0.3s ease; }}
        .slide.active {{ display: block; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        .photo-container {{ margin-bottom: 32px; text-align: center; }}
        .photo {{ max-width: 100%; max-height: 400px; border-radius: 8px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15); }}
        .scene {{ font-size: 14px; color: #666; font-style: italic; line-height: 1.6; }}
        .vocab-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-top: 32px; }}
        .card {{ background: #f9f8f6; border: 2px solid #e0d9d0; border-radius: 8px; padding: 20px; text-align: center; cursor: pointer; transition: all 0.2s ease; min-height: 140px; display: flex; flex-direction: column; justify-content: center; }}
        .card:hover {{ border-color: #8b7355; background: #fff; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); transform: translateY(-2px); }}
        .card.flipped {{ background: #f0ebe5; border-color: #8b7355; }}
        .word-front {{ font-size: 32px; font-weight: 600; color: #2c2c2c; margin-bottom: 8px; line-height: 1.2; }}
        .card.flipped .word-front {{ display: none; }}
        .reveal {{ display: none; }}
        .card.flipped .reveal {{ display: block; }}
        .romanization {{ font-size: 13px; color: #8b7355; margin-bottom: 8px; font-weight: 500; }}
        .english {{ font-size: 14px; color: #666; margin-bottom: 12px; }}
        .example {{ font-size: 12px; color: #999; line-height: 1.4; margin-bottom: 8px; padding-top: 8px; border-top: 1px solid #e0d9d0; }}
        .card.flipped .example {{ border-top: 1px solid #d4ccc0; }}
        .audio-btn {{ margin-top: 8px; background: white; border: 1px solid #d4ccc0; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; transition: all 0.2s ease; color: #8b7355; font-weight: 500; }}
        .audio-btn:hover {{ background: #f0ebe5; border-color: #8b7355; }}
        .controls {{ display: flex; justify-content: space-between; align-items: center; padding: 0 40px 40px; gap: 16px; }}
        .nav-btn {{ background: #8b7355; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s ease; }}
        .nav-btn:hover {{ background: #a89080; transform: translateY(-1px); }}
        .nav-btn:disabled {{ background: #d4ccc0; cursor: not-allowed; transform: none; }}
        .counter {{ font-size: 14px; color: #8b7355; font-weight: 500; min-width: 60px; text-align: center; }}
        .spacer {{ flex: 1; }}
        @media (max-width: 600px) {{ .slide {{ padding: 24px; }} .controls {{ padding: 0 24px 24px; }} .vocab-cards {{ grid-template-columns: 1fr; }} .photo {{ max-height: 300px; }} .word-front {{ font-size: 28px; }} .header h1 {{ font-size: 19px; }} .lang-btn {{ padding: 6px 11px; font-size: 13px; }} }}

        /* ── Click Quiz ── */
        .quiz-heading {{ text-align: center; font-size: 13px; letter-spacing: 0.13em; text-transform: uppercase; color: #8b7355; font-weight: 600; margin-bottom: 24px; }}
        .click-game {{ display: flex; flex-direction: column; align-items: center; gap: 14px; width: 100%; }}
        .cg-prompt-row {{ display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; justify-content: center; }}
        .cg-find {{ font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase; color: #A09C95; }}
        .cg-prompt-word {{ font-size: 34px; font-weight: 600; color: #3D6B5E; cursor: pointer; transition: color 0.15s; line-height: 1.1; }}
        .cg-prompt-word:hover {{ color: #2A5448; }}
        .cg-prompt-en {{ font-size: 15px; color: #9A9790; font-style: italic; }}
        .photo-target-wrap {{ position: relative; border-radius: 14px; overflow: hidden; cursor: crosshair; border: 2px solid #EDE9E2; box-shadow: 0 4px 20px rgba(0,0,0,0.1); max-width: 560px; width: 100%; }}
        .target-photo {{ display: block; width: 100%; height: auto; pointer-events: none; user-select: none; }}
        @keyframes dotIn {{ from {{ transform: translate(-50%,-50%) scale(0.2); opacity: 0; }} to {{ transform: translate(-50%,-50%) scale(1); opacity: 1; }} }}
        .click-dot {{ position: absolute; width: 20px; height: 20px; border-radius: 50%; transform: translate(-50%,-50%); border: 2.5px solid white; pointer-events: none; z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,0.35); animation: dotIn 0.18s ease; }}
        .click-dot.hit {{ background: #4A8C6A; }}
        .click-dot.miss {{ background: #B85454; }}
        .hotspot-box {{ position: absolute; border: 2.5px dashed #4A8C6A; border-radius: 6px; pointer-events: none; z-index: 9; opacity: 0; background: rgba(74,140,106,0.1); transition: opacity 0.3s ease; }}
        .hotspot-box.show {{ opacity: 1; }}
        .cg-status-row {{ display: flex; align-items: center; gap: 16px; min-height: 38px; flex-wrap: wrap; justify-content: center; }}
        .cg-counter {{ font-size: 12px; letter-spacing: 0.1em; color: #A09C95; text-transform: uppercase; min-width: 48px; }}
        .cg-feedback {{ font-size: 15px; font-style: italic; color: #7A7770; min-width: 180px; text-align: center; }}
        .q-next {{ display: none; }}
        .score-screen {{ text-align: center; padding: 20px; }}
        .q-score-text {{ font-size: 22px; color: #3D6B5E; font-weight: 600; margin-bottom: 18px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">Lens</div>
            <h1 id="title">Korean from Photos</h1>
            <div class="lang-picker" id="langPicker">
                <button class="lang-btn" data-lang="ko">한국어</button>
                <button class="lang-btn" data-lang="ja">日本語</button>
                <button class="lang-btn" data-lang="es">Español</button>
            </div>
        </div>
        <div class="slides-container"></div>
        <div class="controls">
            <button class="nav-btn" id="prevBtn">← Previous</button>
            <div class="spacer"></div>
            <div class="counter"><span id="currentSlide">1</span> / <span id="totalSlides">0</span></div>
            <div class="spacer"></div>
            <button class="nav-btn" id="nextBtn">Next →</button>
        </div>
    </div>

    <script>
        const photos = {photos_json};
        let currentSlide = 0;
        let lang = 'ko';  // 'ko' | 'ja' | 'es'

        const LANG = {{
            ko: {{ title: 'Korean from Photos', words: 'words', front: w => w.hangul, reading: w => w.romanization, example: w => w.example_ko, audio: true, tts: 'ko-KR' }},
            ja: {{ title: 'Japanese from Photos', words: 'words_ja', front: w => w.japanese, reading: w => [w.kana, w.romaji].filter(Boolean).join(' · '), example: w => w.example_ja, audio: false, tts: 'ja-JP' }},
            es: {{ title: 'Spanish from Photos', words: 'words_es', front: w => w.spanish, reading: w => w.gender || '', example: w => w.example_es, audio: false, tts: 'es-ES' }},
        }};

        function wordsFor(photo) {{ return photo[LANG[lang].words] || []; }}

        // ── Click Quiz ──────────────────────────────────────────────
        // A challenge is language-independent: it points at a photo + a word
        // INDEX (shared across ko/ja/es) + that object's hotspot box(es).
        // bbox is a per-photo array parallel to `words`; an entry is either a
        // list of {{x1,y1,x2,y2}} percentage boxes or null/absent (not clickable).
        function buildChallenges() {{
            const list = [];
            photos.forEach((photo, pIdx) => {{
                const boxes = photo.bbox || [];
                boxes.forEach((b, wIdx) => {{
                    if (Array.isArray(b) && b.length) list.push({{ photo: pIdx, word: wIdx, hotspot: b }});
                }});
            }});
            return list;
        }}
        const QUIZ = buildChallenges();
        const hasQuiz = QUIZ.length > 0;
        const QUIZ_INDEX = () => photos.length;            // quiz is the last slide
        function slideTotal() {{ return photos.length + (hasQuiz ? 1 : 0); }}

        let qChallenges = [], qIdx = 0, qScore = 0;

        function speak(text, langCode) {{
            try {{
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance(text);
                u.lang = langCode || 'ko-KR';
                u.rate = 0.9;
                window.speechSynthesis.speak(u);
            }} catch (e) {{}}
        }}

        function qShuffle(arr) {{
            const a = [...arr];
            for (let i = a.length - 1; i > 0; i--) {{
                const j = Math.floor(Math.random() * (i + 1));
                [a[i], a[j]] = [a[j], a[i]];
            }}
            return a;
        }}

        function qWord() {{
            const ch = qChallenges[qIdx];
            if (!ch) return null;
            return (photos[ch.photo][LANG[lang].words] || [])[ch.word] || null;
        }}

        function qSpeak() {{
            const w = qWord();
            if (w) speak(LANG[lang].front(w), LANG[lang].tts);
        }}

        function qRenderPrompt() {{
            const w = qWord();
            if (!w) return;
            document.getElementById('q-word').textContent = LANG[lang].front(w);
            document.getElementById('q-en').textContent = '(' + w.english + ')';
        }}

        function qStart() {{
            if (!hasQuiz) return;
            qChallenges = qShuffle(QUIZ);
            qIdx = 0; qScore = 0;
            const scr = document.getElementById('q-score');
            if (scr) scr.style.display = 'none';
            const main = document.getElementById('q-main');
            if (main) main.style.display = '';
            qLoad();
        }}

        function qLoad() {{
            const ch = qChallenges[qIdx];
            if (!ch) return;
            document.getElementById('q-photo').src = encodeURI(photos[ch.photo].local_image || '');
            qRenderPrompt();
            const fb = document.getElementById('q-feedback');
            fb.textContent = ''; fb.style.color = '#7A7770';
            document.getElementById('q-counter').textContent = (qIdx + 1) + ' / ' + qChallenges.length;
            const nxt = document.getElementById('q-next');
            nxt.style.display = 'none'; nxt.onclick = null;
            const wrap = document.getElementById('q-wrap');
            wrap.querySelectorAll('.click-dot, .hotspot-box').forEach(e => e.remove());
            wrap.style.cursor = 'crosshair';
            wrap.onclick = qClick;
        }}

        function qClick(e) {{
            const ch = qChallenges[qIdx];
            const wrap = document.getElementById('q-wrap');
            const img = document.getElementById('q-photo');
            const rect = img.getBoundingClientRect();
            const xPct = (e.clientX - rect.left) / rect.width * 100;
            const yPct = (e.clientY - rect.top) / rect.height * 100;
            const hit = ch.hotspot.some(hs => xPct >= hs.x1 && xPct <= hs.x2 && yPct >= hs.y1 && yPct <= hs.y2);

            wrap.onclick = null;
            wrap.style.cursor = 'default';

            const dot = document.createElement('div');
            dot.className = 'click-dot ' + (hit ? 'hit' : 'miss');
            dot.style.left = xPct + '%';
            dot.style.top = yPct + '%';
            wrap.appendChild(dot);

            ch.hotspot.forEach(hs => {{
                const box = document.createElement('div');
                box.className = 'hotspot-box';
                box.style.left = hs.x1 + '%';
                box.style.top = hs.y1 + '%';
                box.style.width = (hs.x2 - hs.x1) + '%';
                box.style.height = (hs.y2 - hs.y1) + '%';
                wrap.appendChild(box);
                requestAnimationFrame(() => box.classList.add('show'));
            }});

            const fb = document.getElementById('q-feedback');
            const w = qWord();
            if (hit) {{
                qScore++;
                fb.textContent = '✓ ' + (w ? w.english : 'correct') + '!';
                fb.style.color = '#3D6B5E';
                if (w) speak(LANG[lang].front(w), LANG[lang].tts);
            }} else {{
                fb.textContent = 'not quite — see the green area';
                fb.style.color = '#B85454';
            }}

            const nxt = document.getElementById('q-next');
            nxt.style.display = '';
            if (qIdx >= qChallenges.length - 1) {{
                nxt.textContent = 'see score →';
                nxt.onclick = qFinish;
            }} else {{
                nxt.textContent = 'next →';
                nxt.onclick = () => {{ qIdx++; qLoad(); }};
            }}
        }}

        function qFinish() {{
            document.getElementById('q-main').style.display = 'none';
            const scr = document.getElementById('q-score');
            scr.querySelector('.q-score-text').textContent =
                'You found ' + qScore + ' of ' + qChallenges.length + '!';
            scr.style.display = '';
        }}

        function renderSlides() {{
            const container = document.querySelector('.slides-container');
            container.innerHTML = '';
            document.getElementById('title').textContent = LANG[lang].title;
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.toggle('active', b.dataset.lang === lang));
            photos.forEach((photo, idx) => {{
                const slide = document.createElement('div');
                slide.className = 'slide' + (idx === currentSlide ? ' active' : '');
                const photoUrl = encodeURI(photo.local_image || '');
                const words = wordsFor(photo);
                const html = `
                    <div class="photo-container">
                        <img src="${{photoUrl}}" alt="${{photo.scene}}" class="photo" onerror="this.style.display='none'" />
                        <div class="scene">${{photo.scene}}</div>
                    </div>
                    <div class="vocab-cards">
                        ${{words.map((word, widx) => {{
                            const reading = LANG[lang].reading(word);
                            return `
                            <div class="card" data-word="${{widx}}">
                                <div class="word-front">${{LANG[lang].front(word)}}</div>
                                <div class="reveal">
                                    ${{reading ? `<div class="romanization">${{reading}}</div>` : ''}}
                                    <div class="english">${{word.english}}</div>
                                    <div class="example"><div>${{LANG[lang].example(word)}}</div><div>${{word.example_en}}</div></div>
                                    ${{LANG[lang].audio ? '<button class="audio-btn">🔊 Audio</button>' : ''}}
                                </div>
                            </div>`;
                        }}).join('')}}
                    </div>
                `;
                slide.innerHTML = html;
                container.appendChild(slide);
            }});
            if (hasQuiz) {{
                const qs = document.createElement('div');
                qs.className = 'slide' + (currentSlide === QUIZ_INDEX() ? ' active' : '');
                qs.innerHTML = `
                    <div class="quiz-heading">Click Quiz · tap the object</div>
                    <div id="q-main" class="click-game">
                        <div class="cg-prompt-row">
                            <span class="cg-find">Find</span>
                            <span class="cg-prompt-word" id="q-word" onclick="qSpeak()"></span>
                            <span class="cg-prompt-en" id="q-en"></span>
                        </div>
                        <div class="photo-target-wrap" id="q-wrap">
                            <img id="q-photo" class="target-photo" src="" alt="">
                        </div>
                        <div class="cg-status-row">
                            <span class="cg-counter" id="q-counter"></span>
                            <span class="cg-feedback" id="q-feedback"></span>
                            <button class="nav-btn q-next" id="q-next">next →</button>
                        </div>
                    </div>
                    <div id="q-score" class="score-screen" style="display:none">
                        <div class="q-score-text"></div>
                        <button class="nav-btn" id="q-replay">play again</button>
                    </div>`;
                container.appendChild(qs);
                qs.querySelector('#q-replay').addEventListener('click', qStart);
            }}
            document.getElementById('totalSlides').textContent = slideTotal();
            attachCardListeners();
            // If a quiz is already in progress (e.g. after a language switch),
            // re-render the current challenge in the now-active language.
            if (hasQuiz && currentSlide === QUIZ_INDEX()) {{
                if (qChallenges.length) qLoad(); else qStart();
            }}
            updateNav();
        }}

        function attachCardListeners() {{
            document.querySelectorAll('.card').forEach(card => {{
                card.addEventListener('click', function() {{ this.classList.toggle('flipped'); }});
            }});
        }}

        function showSlide(n) {{
            currentSlide = Math.max(0, Math.min(n, slideTotal() - 1));
            document.querySelectorAll('.slide').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.slide')[currentSlide].classList.add('active');
            document.getElementById('currentSlide').textContent = currentSlide + 1;
            // Landing on the quiz slide: start a fresh session, or repaint the
            // current challenge into a freshly-rebuilt DOM (e.g. after a lang switch).
            if (hasQuiz && currentSlide === QUIZ_INDEX()) {{
                if (qChallenges.length === 0) qStart(); else qLoad();
            }}
            updateNav();
        }}

        function updateNav() {{
            document.getElementById('prevBtn').disabled = currentSlide === 0;
            document.getElementById('nextBtn').disabled = currentSlide === slideTotal() - 1;
        }}

        function setLang(next) {{
            if (!LANG[next] || next === lang) return;
            lang = next;
            renderSlides();
            showSlide(currentSlide);
        }}

        document.getElementById('prevBtn').addEventListener('click', () => showSlide(currentSlide - 1));
        document.getElementById('nextBtn').addEventListener('click', () => showSlide(currentSlide + 1));
        document.getElementById('langPicker').addEventListener('click', (e) => {{
            const btn = e.target.closest('.lang-btn');
            if (btn) setLang(btn.dataset.lang);
        }});
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') showSlide(currentSlide - 1);
            if (e.key === 'ArrowRight') showSlide(currentSlide + 1);
        }});

        renderSlides();
        showSlide(0);
    </script>
</body>
</html>"""

    return html


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
    ja_count = sum(len(p.get("words_ja", [])) for p in photos)
    es_count = sum(len(p.get("words_es", [])) for p in photos)
    print(f"✓ Generated {html_file}")
    print(f"✓ {len(photos)} photo(s) — {sum(len(p['words']) for p in photos)} KO, {ja_count} JA, {es_count} ES word(s)")
    print(f"✓ images: {', '.join(f'{k}={v}' for k, v in sorted(statuses.items()))}")
    return True


if __name__ == "__main__":
    import os
    os.chdir("/Users/ggibson1/Desktop/Kramer-Projects-2026/korean-photo-slideshow")
    if deploy():
        print("\nReady to deploy!")
