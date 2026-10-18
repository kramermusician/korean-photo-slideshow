# LoopGrid Web

The browser edition of LoopGrid, the native macOS video looper that lives in `Owner's Inbox/coding projects/loopgrid/`. Built 2026-10-18 so a friend without a Mac can try the instrument.

Live: `https://kramermusician.github.io/korean-photo-slideshow/looper/` (GitHub Pages serves this repo's `docs/` folder, so a push to `main` is the deploy).

Three files, no build step, no dependencies: `index.html` (UI), `looper.js` (transport, camera frames, grid, keys), `worklet.js` (the audio engine, on the audio thread). Nothing leaves the visitor's computer; there is no server, no login and no analytics.

## Feasibility, in short

A browser can do the core of LoopGrid well: the RC-505 spacebar model, loops locked to one sample clock, the adaptive grid, quantize, tap tempo, click and count-in, per-loop mute, volume, reverse and reverb, and a performance recording. The pieces that were in doubt all have a web API that is good enough:

| Native piece | Web equivalent | Verdict |
| --- | --- | --- |
| AVAudioEngine sample clock | AudioWorklet: the processor counts rendered samples, and the main thread reads the same clock through `AudioContext.currentTime` | Solid. Same design as the Mac app: positions are sample counts, input goes into a 130 s ring, a loop is cut out of the ring after the fact |
| Camera to 960x540 frames with a pre-roll | `requestVideoFrameCallback` on a hidden video element, each frame drawn into an OffscreenCanvas and kept as an ImageBitmap, 3 s pre-roll | Works. Frames are 480x270 by default (320 or 640 in Settings) because browser memory is tighter than a Mac's |
| Metal grid with 250 ms reflow | 2D canvas, drawn on every animation frame, picking each tile's frame from the audio clock | Fine at 9 tiles. The frame picked is the stored frame nearest the audio position, never the other way round |
| Manual camera offset | Same, `[` and `]`, saved in localStorage | Same |
| MP4 performance export | MediaRecorder on the canvas stream plus the loop mix (click excluded) | webm in Chrome and Firefox, mp4 in Safari. Good enough to share; not a 1080p30 master |
| Raw instrument input | `getUserMedia` with echo cancellation, noise suppression and auto gain off | Works, but browsers add 20 to 60 ms of input latency the native app does not have; the offset slider absorbs the picture side of it |

What did not make it, and why:

- Octave down and half speed. Both are offline pitch and time renders in the Mac app (Apple TimePitch). A web version would need a hand-written phase vocoder or a WASM port of a library like SoundTouch. Possible, a day's work, not needed to try the instrument.
- Beat repeat, undo, overlay, cube and the four video effects (Paint, Comic, Ink, Kaleido). Effects would move the renderer to WebGL; the rest is plain work that waits on whether the web version earns it.
- RC-505 Linked mode. Web MIDI exists in Chrome and Edge, so clock follow and CC out are feasible later; Firefox and Safari have no Web MIDI.
- Phones and tablets. The page loads, but it is keyboard-driven and the memory cap is too high for a phone. Laptop or desktop only.

## Browser notes

- Chrome and Edge are the smoothest (full `requestVideoFrameCallback`, OffscreenCanvas, webm recording).
- Firefox works; it took `requestVideoFrameCallback` in 2024, and older versions fall back to polling with `requestAnimationFrame`.
- Safari works and records mp4. Its AudioContext may run at 44.1 kHz; everything is in samples, so nothing cares.
- A background tab stops drawing and stops capturing frames, so the player keeps the tab in front. Audio keeps running.
- HTTPS or localhost is required for the camera. GitHub Pages is HTTPS.

## How it keeps time

Same model as the Mac app, so the two stay comparable:

- Position p is "sample p has been rendered". The worklet posts its start time once, and the main thread computes `now()` from `AudioContext.currentTime`.
- Input is written into a 130 s ring at its render position. When a take closes, the worklet copies what the ring already holds into the loop and fills the tail as the last blocks arrive, so the loop plays from the instant it closes.
- Camera frames are stamped with the clock position at arrival and kept in a 3 s pre-roll; a loop takes the frames in its range plus a quarter second either side, which is what lets `[` and `]` move every loop live.
- The renderer draws for `now() - outputLatency`, then adds the camera offset, and shows the nearest stored frame.
- Snapping mirrors `AppModel.swift`: the first loop sets L; later takes snap to L/4, L/2 or a whole number of L; in tempo mode everything is whole bars; quantize snaps starts and ends to the beat, or to quarter-loops in free mode.

## Memory

Each stored frame is width x height x 4 bytes. At the default 480x270 that is about 15 MB per second of loop at 30 fps, so a 10 s loop is 150 MB and nine of them 1.4 GB. The cap is 1.5 GB and the top bar shows the running total; a take is refused at the cap. Drop to 320x180 for long loops or a small laptop.

## Testing

Headless Chrome with `--use-fake-device-for-media-stream --use-fake-ui-for-media-stream` against a local `python3 -m http.server` in this folder, driven over the DevTools protocol. Checked on 2026-10-18: three free-mode loops snapped to 1x, 0.5x and 2x the master length with frames and audio in place, mute, volume, reverse and reverb flags landed, a 2 s performance recording produced a webm, clear all returned to idle, and a tapped 118.8 BPM tempo with count-in produced a one-bar loop. Not yet checked by a person: the feel of the latency and the camera offset on a real camera.
