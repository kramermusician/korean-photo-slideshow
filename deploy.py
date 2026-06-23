#!/usr/bin/env python3
"""Generate KKAS slideshow HTML (lightweight, no file copying).

Renders both Korean and Japanese vocab from the same per-photo JSONs and adds a
header toggle ("Japanese mode" / "Korean mode"). Korean comes from each photo's
`words` array; Japanese from the parallel `words_ja` array (mirrors the same
concepts). Japanese audio is not yet generated, so the audio button only shows in
Korean mode.
"""

import json
from pathlib import Path


def build_html(photos):
    """Build HTML with embedded JSON data. References Dropbox for media."""
    photos_json = json.dumps(photos, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Words from Photos</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; background: linear-gradient(135deg, #f5ede4 0%, #e8ddd0 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .container {{ max-width: 900px; width: 100%; background: white; border-radius: 12px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden; }}
        .header {{ position: relative; background: linear-gradient(135deg, #8b7355 0%, #a89080 100%); color: white; padding: 24px; text-align: center; }}
        .header h1 {{ font-size: 24px; font-weight: 600; letter-spacing: 0.5px; }}
        .lang-toggle {{ position: absolute; top: 50%; right: 20px; transform: translateY(-50%); background: rgba(255,255,255,0.18); color: white; border: 1px solid rgba(255,255,255,0.5); padding: 8px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; backdrop-filter: blur(4px); }}
        .lang-toggle:hover {{ background: rgba(255,255,255,0.32); }}
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
        @media (max-width: 600px) {{ .slide {{ padding: 24px; }} .controls {{ padding: 0 24px 24px; }} .vocab-cards {{ grid-template-columns: 1fr; }} .photo {{ max-height: 300px; }} .word-front {{ font-size: 28px; }} .header h1 {{ font-size: 19px; }} .lang-toggle {{ right: 12px; padding: 6px 10px; font-size: 12px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 id="title">Korean from Photos</h1>
            <button class="lang-toggle" id="langToggle">日本語モード →</button>
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
        let lang = 'ko';  // 'ko' or 'ja'

        const LANG = {{
            ko: {{ title: 'Korean from Photos', toggle: '日本語モード →', words: 'words', reading: w => w.romanization, audio: true }},
            ja: {{ title: 'Japanese from Photos', toggle: '← 한국어 모드', words: 'words_ja', reading: w => [w.kana, w.romaji].filter(Boolean).join(' · '), audio: false }},
        }};

        function wordsFor(photo) {{ return photo[LANG[lang].words] || []; }}
        function frontText(w) {{ return lang === 'ja' ? w.japanese : w.hangul; }}
        function exampleNative(w) {{ return lang === 'ja' ? w.example_ja : w.example_ko; }}

        function renderSlides() {{
            const container = document.querySelector('.slides-container');
            container.innerHTML = '';
            document.getElementById('title').textContent = LANG[lang].title;
            document.getElementById('langToggle').textContent = LANG[lang].toggle;
            photos.forEach((photo, idx) => {{
                const slide = document.createElement('div');
                slide.className = 'slide' + (idx === currentSlide ? ' active' : '');
                const photoUrl = `https://dl.dropboxusercontent.com/scl/fi/9a1qh3ci3jxkagn07t0if/KRAMOS/korean-photo-feedback/${{photo.photo}}?rlkey=58m34w34puttjbz2qk3qqi61d&dl=1`.replace(/ /g, '%20');
                const words = wordsFor(photo);
                const html = `
                    <div class="photo-container">
                        <img src="${{photoUrl}}" alt="${{photo.scene}}" class="photo" onerror="this.style.display='none'" />
                        <div class="scene">${{photo.scene}}</div>
                    </div>
                    <div class="vocab-cards">
                        ${{words.map((word, widx) => `
                            <div class="card" data-word="${{widx}}">
                                <div class="word-front">${{frontText(word)}}</div>
                                <div class="reveal">
                                    <div class="romanization">${{LANG[lang].reading(word)}}</div>
                                    <div class="english">${{word.english}}</div>
                                    <div class="example"><div>${{exampleNative(word)}}</div><div>${{word.example_en}}</div></div>
                                    ${{LANG[lang].audio ? '<button class="audio-btn">🔊 Audio</button>' : ''}}
                                </div>
                            </div>
                        `).join('')}}
                    </div>
                `;
                slide.innerHTML = html;
                container.appendChild(slide);
            }});
            document.getElementById('totalSlides').textContent = photos.length;
            attachCardListeners();
            updateNav();
        }}

        function attachCardListeners() {{
            document.querySelectorAll('.card').forEach(card => {{
                card.addEventListener('click', function() {{ this.classList.toggle('flipped'); }});
            }});
        }}

        function showSlide(n) {{
            currentSlide = Math.max(0, Math.min(n, photos.length - 1));
            document.querySelectorAll('.slide').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.slide')[currentSlide].classList.add('active');
            document.getElementById('currentSlide').textContent = currentSlide + 1;
            updateNav();
        }}

        function updateNav() {{
            document.getElementById('prevBtn').disabled = currentSlide === 0;
            document.getElementById('nextBtn').disabled = currentSlide === photos.length - 1;
        }}

        document.getElementById('prevBtn').addEventListener('click', () => showSlide(currentSlide - 1));
        document.getElementById('nextBtn').addEventListener('click', () => showSlide(currentSlide + 1));
        document.getElementById('langToggle').addEventListener('click', () => {{
            lang = lang === 'ko' ? 'ja' : 'ko';
            renderSlides();
            showSlide(currentSlide);
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

    # Generate HTML
    html = build_html(photos)
    html_file = docs_dir / "index.html"
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    ja_count = sum(len(p.get("words_ja", [])) for p in photos)
    print(f"✓ Generated {html_file}")
    print(f"✓ {len(photos)} photo(s) — {sum(len(p['words']) for p in photos)} KO word(s), {ja_count} JA word(s)")
    return True


if __name__ == "__main__":
    import os
    os.chdir("/Users/ggibson1/Desktop/Kramer-Projects-2026/korean-photo-slideshow")
    if deploy():
        print("\nReady to deploy!")
