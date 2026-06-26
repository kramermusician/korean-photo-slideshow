# Lens

**Lens — learn from your photos.** Take a photo of something in the world, and Lens pulls the most useful words for what's visible, then teaches them as an interactive deck. It is **six languages, any-to-any**: English, Korean, Japanese, Spanish, French, and Mandarin. Pick the language you speak and the language you're learning, and every card teaches the target word with help shown in your home language. A Korean speaker can learn English; a French speaker can learn Japanese; English speakers can learn any of the five.

Live site: **https://kramermusician.github.io/korean-photo-slideshow**

## How it works

1. Drop a photo into `~/Dropbox/KRAMOS/korean-photo/`
2. A watcher notices it and runs the analysis, which generates, for each photo:
   - 3–5 concepts (the most useful, pointable words in the scene)
   - All six languages per concept — word, reading, and an example sentence
   - A `bbox` per concept (where the object sits in the image) for the click game
   - A plain-markdown learner card
3. The deck rebuilds (`deploy.py`) and **auto-pushes to GitHub Pages** — new photos go live hands-free.

## Languages

Every concept carries all six languages as co-equal entries (no single "base" language):

| Code | Language | Reading shown | Article? |
|------|----------|---------------|----------|
| `en` | English  | —             | no  |
| `ko` | Korean   | romanization  | no  |
| `ja` | Japanese | kana · rōmaji | no  |
| `es` | Spanish  | el / la       | yes |
| `fr` | French   | le / la       | yes |
| `zh` | Mandarin | pinyin (tones)| no  |

For Romance languages the article renders **before** the noun (`le chat`, `el pan`). For others the reading shows on the card flip (`빵` → `ppang`).

## Interaction

- **Two pickers** — "I speak" (home) and "I'm learning" (target). The opposite picker's current choice is disabled so you can't pick the same language twice. Your choice is remembered between visits (`localStorage`: `lensHome` / `lensTarget`, default English → Korean).
- **Vocabulary cards** — front shows the target word (+ reading where relevant). Tap to flip: shows the home-language meaning, a target-language example sentence, and a 🔊 button (browser speech, all six languages). If the concept has a bbox, a highlight box appears on the photo marking the object.
- **Click Target game** — shows the **target** word (the one you're learning) and asks you to tap that object in the photo. A correct tap reveals the spot, confirms with the **home-language meaning**, and speaks the target word; a miss shows you where it was. Running counter + score screen with "play again." UI chrome (prompts, buttons) is in the target language for immersion.
- **Navigation** — Previous/Next buttons or arrow keys (← / →).
- **Mobile-friendly** — responsive, works on phones.

## Per-photo JSON schema

Each photo's feedback JSON (`~/Dropbox/KRAMOS/korean-photo-feedback/<stem>.json`):

```json
{
  "photo": "...", "stem": "...", "scene": "...", "local_image": "photos/...",
  "bbox": [ [ {"x1":0,"y1":68,"x2":48,"y2":100} ], null ],
  "concepts": [
    {
      "pos": "noun",
      "langs": {
        "en": { "word": "bread", "reading": "",        "example": "This bread is really delicious." },
        "ko": { "word": "빵",    "reading": "ppang",    "example": "이 빵 정말 맛있어요." },
        "ja": { "word": "パン",  "reading": "パン · pan", "example": "このパンは本当においしいです。" },
        "es": { "word": "pan",   "reading": "el",       "example": "Este pan está muy rico." },
        "fr": { "word": "pain",  "reading": "le",       "example": "Ce pain est vraiment délicieux." },
        "zh": { "word": "面包",  "reading": "miànbāo",  "example": "这个面包真好吃。" }
      }
    }
  ]
}
```

`concepts[i]` aligns with `bbox[i]` by index (`null` for verbs / things you can't point at). Because location doesn't change with language, one `bbox` set drives both the card-flip highlights and the Click Target game in every language.

## Deploy manually (if needed)

The watcher does this automatically, but to rebuild + push by hand:

```bash
cd korean-photo-slideshow
python3 deploy.py
git add docs/
git commit -m "Deploy new photos"
git push origin main
```

## Project structure

- `docs/` — GitHub Pages site
  - `index.html` — the deck (auto-generated; do not hand-edit)
  - `photos/` — downscaled photo images (~1280px), committed and served by Pages
- `deploy.py` — the single Lens builder: downscales source photos from `~/Dropbox/KRAMOS/korean-photo/` into `docs/photos/`, reads the feedback JSONs, and generates the HTML deck

The generation prompt lives at `scripts/korean-pipeline/korean-photo-prompt.md`; the watcher at `scripts/korean-pipeline/korean-photo-watcher.js`.

## Backlog

**bbox editor.** Some click-target bounding boxes are imperfect (wrong position/region). A simple in-browser tool to pull up any photo, see its bbox overlays, drag/resize them, and save corrected values back to the JSON would let these be fixed without touching code.

---

Lens grew out of Kramer's Korean acquisition system and is now a general six-language vocabulary teacher built from real-world photos.
