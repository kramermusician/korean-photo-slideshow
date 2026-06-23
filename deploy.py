#!/usr/bin/env python3
"""
Deploy KKAS photo slideshow to GitHub Pages.

Reads photos + JSON from korean-photo-feedback/, copies them to docs/,
generates index.html with working image/audio paths, then commit & push.

Usage:
    python3 deploy.py
"""

import json
import shutil
import re
from pathlib import Path


def sanitize_filename(filename):
    """Convert unsafe filenames to URL-safe ones."""
    # Remove extension
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
    # Replace spaces, commas, and other unsafe chars with hyphens
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '-', name)
    # Remove consecutive hyphens
    safe_name = re.sub(r'-+', '-', safe_name)
    # Return with extension
    return f"{safe_name}.{ext}" if ext else safe_name


def build_html(photos):
    """Build the HTML slideshow with proper GitHub Pages paths."""
    photos_json = json.dumps(photos)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Korean from Photos</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #f5ede4 0%, #e8ddd0 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}

        .container {{
            max-width: 900px;
            width: 100%;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #8b7355 0%, #a89080 100%);
            color: white;
            padding: 24px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 24px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        .slide {{
            display: none;
            padding: 40px;
            animation: fadeIn 0.3s ease;
        }}

        .slide.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}

        .photo-container {{
            margin-bottom: 32px;
            text-align: center;
        }}

        .photo {{
            max-width: 100%;
            max-height: 400px;
            border-radius: 8px;
            margin-bottom: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}

        .scene {{
            font-size: 14px;
            color: #666;
            font-style: italic;
            line-height: 1.6;
        }}

        .vocab-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px;
            margin-top: 32px;
        }}

        .card {{
            background: #f9f8f6;
            border: 2px solid #e0d9d0;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s ease;
            min-height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .card:hover {{
            border-color: #8b7355;
            background: #fff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            transform: translateY(-2px);
        }}

        .card.flipped {{
            background: #f0ebe5;
            border-color: #8b7355;
        }}

        .hangul {{
            font-size: 32px;
            font-weight: 600;
            color: #2c2c2c;
            margin-bottom: 8px;
            line-height: 1.2;
        }}

        .card.flipped .hangul {{
            display: none;
        }}

        .reveal {{
            display: none;
        }}

        .card.flipped .reveal {{
            display: block;
        }}

        .romanization {{
            font-size: 13px;
            color: #8b7355;
            margin-bottom: 8px;
            font-weight: 500;
        }}

        .english {{
            font-size: 14px;
            color: #666;
            margin-bottom: 12px;
        }}

        .example {{
            font-size: 12px;
            color: #999;
            line-height: 1.4;
            margin-bottom: 8px;
            padding-top: 8px;
            border-top: 1px solid #e0d9d0;
        }}

        .card.flipped .example {{
            border-top: 1px solid #d4ccc0;
        }}

        .exposure {{
            font-size: 11px;
            color: #a89080;
            margin-top: 8px;
            font-style: italic;
        }}

        .audio-btn {{
            margin-top: 8px;
            background: white;
            border: 1px solid #d4ccc0;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            color: #8b7355;
            font-weight: 500;
        }}

        .audio-btn:hover {{
            background: #f0ebe5;
            border-color: #8b7355;
        }}

        .controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 40px 40px;
            gap: 16px;
        }}

        .nav-btn {{
            background: #8b7355;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
        }}

        .nav-btn:hover {{
            background: #a89080;
            transform: translateY(-1px);
        }}

        .nav-btn:disabled {{
            background: #d4ccc0;
            cursor: not-allowed;
            transform: none;
        }}

        .counter {{
            font-size: 14px;
            color: #8b7355;
            font-weight: 500;
            min-width: 60px;
            text-align: center;
        }}

        .spacer {{
            flex: 1;
        }}

        @media (max-width: 600px) {{
            .slide {{
                padding: 24px;
            }}

            .controls {{
                padding: 0 24px 24px;
            }}

            .vocab-cards {{
                grid-template-columns: 1fr;
            }}

            .photo {{
                max-height: 300px;
            }}

            .hangul {{
                font-size: 28px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Korean from Photos</h1>
        </div>

        <div class="slides-container">
            <!-- Slides will be generated here by JS -->
        </div>

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

        function renderSlides() {{
            const container = document.querySelector('.slides-container');
            container.innerHTML = '';

            photos.forEach((photo, idx) => {{
                const slide = document.createElement('div');
                slide.className = 'slide' + (idx === currentSlide ? ' active' : '');

                const photoPath = `photos/${{photo.photo}}`;
                const audioPath = `audio/${{photo.stem}}-audio.mp3`;
                const html = `
                    <div class="photo-container">
                        <img src="${{photoPath}}" alt="${{photo.scene}}" class="photo" />
                        <div class="scene">${{photo.scene}}</div>
                    </div>
                    <div class="vocab-cards">
                        ${{photo.words.map((word, widx) => `
                            <div class="card" data-slide="${{idx}}" data-word="${{widx}}" data-audio="${{audioPath}}">
                                <div class="hangul">${{word.hangul}}</div>
                                <div class="reveal">
                                    <div class="romanization">${{word.romanization}}</div>
                                    <div class="english">${{word.english}}</div>
                                    <div class="example">
                                        <div>${{word.example_ko}}</div>
                                        <div>${{word.example_en}}</div>
                                    </div>
                                    <button class="audio-btn">🔊 Play</button>
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
            attachAudioListeners();
            updateNav();
        }}

        function attachCardListeners() {{
            document.querySelectorAll('.card').forEach(card => {{
                card.addEventListener('click', function() {{
                    this.classList.toggle('flipped');
                }});
            }});
        }}

        function attachAudioListeners() {{
            document.querySelectorAll('.audio-btn').forEach(btn => {{
                btn.addEventListener('click', function(e) {{
                    e.stopPropagation();
                    const audioPath = this.closest('.card').dataset.audio;
                    const audio = new Audio(audioPath);
                    audio.play().catch(err => console.log('Audio error:', err));
                }});
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

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft') showSlide(currentSlide - 1);
            if (e.key === 'ArrowRight') showSlide(currentSlide + 1);
        }});

        // Initial render
        renderSlides();
        showSlide(0);
    </script>
</body>
</html>"""

    return html


def deploy():
    """Copy photos + audio, generate HTML, commit to git."""
    feedback_dir = Path.home() / "Dropbox" / "KRAMOS" / "korean-photo-feedback"
    photo_in_dir = Path.home() / "Dropbox" / "KRAMOS" / "korean-photo"
    repo_dir = Path("/Users/ggibson1/Desktop/Kramer-Projects-2026/korean-photo-slideshow")
    docs_dir = repo_dir / "docs"
    photos_dir = docs_dir / "photos"
    audio_dir = docs_dir / "audio"

    if not feedback_dir.exists():
        print(f"Error: {feedback_dir} not found")
        return False

    if not photo_in_dir.exists():
        print(f"Warning: {photo_in_dir} not found (but continuing anyway)")
        photo_in_dir = None

    # Create directories
    docs_dir.mkdir(exist_ok=True)
    photos_dir.mkdir(exist_ok=True)
    audio_dir.mkdir(exist_ok=True)

    # Read all JSON files and copy photos + audio
    photos = []
    for json_file in sorted(feedback_dir.glob("*.json")):
        if json_file.name == "photo-vocab-log.json":
            continue
        try:
            with open(json_file) as f:
                data = json.load(f)

            # Create safe filenames for web
            original_photo = data["photo"]
            safe_photo = sanitize_filename(original_photo)
            safe_stem = sanitize_filename(data["stem"])
            safe_audio = f"{safe_stem}-audio.mp3"

            # Copy photo with safe filename (from input folder, not feedback)
            photo_src = photo_in_dir / original_photo if photo_in_dir else None
            photo_dst = photos_dir / safe_photo
            if photo_src and photo_src.exists():
                shutil.copy2(photo_src, photo_dst)
                print(f"✓ Copied photo: {original_photo} → {safe_photo}")
            else:
                print(f"⚠ Photo not found: {original_photo} (will reference anyway)")

            # Copy audio with safe filename
            audio_src = feedback_dir / f"{data['stem']}-audio.mp3"
            audio_dst = audio_dir / safe_audio
            if audio_src.exists():
                shutil.copy2(audio_src, audio_dst)
                print(f"✓ Copied audio: {data['stem']}-audio.mp3 → {safe_audio}")

            # Update data to reference safe filenames
            data["photo"] = safe_photo
            data["stem"] = safe_stem

            photos.append(data)

        except Exception as e:
            print(f"Warning: {json_file}: {e}")

    if not photos:
        print("No photos found!")
        return False

    # Generate HTML
    html = build_html(photos)
    html_file = docs_dir / "index.html"
    with open(html_file, "w") as f:
        f.write(html)
    print(f"✓ Generated {html_file}")

    print(f"\n✓ Deployed {len(photos)} photo(s) with {sum(len(p['words']) for p in photos)} word(s) total")
    return True


if __name__ == "__main__":
    import sys
    import os

    os.chdir("/Users/ggibson1/Desktop/Kramer-Projects-2026/korean-photo-slideshow")
    if deploy():
        print("\nReady to push to GitHub Pages!")
