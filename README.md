# Korean Photo Slideshow

Interactive vocabulary learning from your photos. Take a photo of something in the world, get the most useful Korean words for what's visible, then learn them — Hangul first, click to reveal translations and example sentences.

## How it works

1. Drop a photo into `~/Dropbox/KRAMOS/korean-photo/`
2. The KKAS system analyzes it and generates:
   - Learner card (3–5 most useful Korean words for the scene)
   - Audio reading (gTTS Korean pronunciation)
   - Structured JSON data
3. The slideshow auto-deploys to GitHub Pages with all photos + audio

## Interaction

- **Hangul-only cards** — vocabulary words show only Korean Hangul initially
- **Click to reveal** — tap any word to see romanization + English translation + example sentence + audio button
- **Audio playback** — 🔊 button plays the full gTTS recording
- **Navigation** — Previous/Next buttons or arrow keys (← / →)
- **Mobile-friendly** — responsive design, works on all devices

## To deploy a new batch

After the KKAS watchers process photos:

```bash
cd korean-photo-slideshow
python3 deploy.py
git add docs/
git commit -m "Deploy new photos"
git push
```

The slideshow updates at: **[your-github-pages-url]**

## Project structure

- `docs/` — GitHub Pages site (index.html + photos + audio)
  - `index.html` — Main slideshow (auto-generated)
  - `photos/` — Photo images
  - `audio/` — gTTS audio files
- `deploy.py` — Build script (copies photos from Dropbox, generates HTML)

---

Part of KKAS (Kramer's Korean Acquisition System).
