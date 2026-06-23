# Korean Photo Slideshow

Interactive vocabulary learning from your photos. Take a photo of something in the world, get the most useful Korean words for what's visible, then learn them — Hangul first, click to reveal translations and example sentences. A header language picker flips the whole deck to **Japanese** or **Spanish** mode for the same concepts. The deck ends with a **Click Quiz** that shows a word and asks you to tap the matching object in the photo — in whichever language you have selected.

## How it works

1. Drop a photo into `~/Dropbox/KRAMOS/korean-photo/`
2. The KKAS system analyzes it and generates:
   - Learner card (3–5 most useful Korean words for the scene)
   - Audio reading (gTTS Korean pronunciation)
   - Structured JSON data
3. The slideshow auto-deploys to GitHub Pages (photos are downscaled into the repo; Korean audio streams from Dropbox)

## Interaction

- **Hangul-only cards** — vocabulary words show only Korean Hangul initially
- **Click to reveal** — tap any word to see romanization + English translation + example sentence + audio button
- **Language picker** — segmented control (한국어 · 日本語 · Español) flips every card between languages:
  - **Japanese** — front = kanji/kana, reveal = kana · romaji + English + です/ます example (from `words_ja`)
  - **Spanish** — front = lemma, reveal = el/la article + English + present-tense example (from `words_es`)
  - All three are parallel arrays mirroring the same concepts. Japanese/Spanish audio is a v2 item, so the 🔊 button only appears in Korean mode.
- **Audio playback** — 🔊 button plays the full gTTS recording (Korean)
- **Click Quiz** — the final slide. Shows one vocabulary word and asks you to click that object in the photo. A correct tap reveals the spot in green and speaks the word; a miss shows you where it was. Running counter + a score screen with "play again." The prompt and the spoken word follow the active language picker, so the same photo quizzes you in Korean, Japanese, or Spanish.
  - **Where the targets come from** — each photo's JSON carries a `bbox` array parallel to `words`: per word, either a list of `{x1,y1,x2,y2}` percentage boxes (where the object sits in the image) or `null` for verbs / things you can't point at. Because location doesn't change with language, one `bbox` set drives the quiz in all three languages. The pipeline emits `bbox` automatically for every new photo, so the quiz grows on its own.
- **Navigation** — Previous/Next buttons or arrow keys (← / →); the quiz is the last slide
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

- `docs/` — GitHub Pages site
  - `index.html` — Main slideshow (auto-generated)
  - `photos/` — Downscaled photo images (~1280px, committed to the repo and served by Pages)
- `deploy.py` — Build script: downscales each source photo from `~/Dropbox/KRAMOS/korean-photo/` into `docs/photos/`, then generates the HTML

---

Part of KKAS (Kramer's Korean Acquisition System).
