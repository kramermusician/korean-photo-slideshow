#!/usr/bin/env python3
"""Lens bbox editor — local editing server.

Run this to fix the green click-target boxes by hand:

    python3 bbox_editor.py

It serves the Lens site from docs/ at http://localhost:8777/ and opens it in
your browser. Press the 'x' key on the page to enter the hidden bbox editor.
Drag / resize / add / delete the green boxes per word, then click Save — this
server writes your corrections straight back into the matching source JSON in
~/Dropbox/KRAMOS/korean-photo-feedback/. When you're done, run deploy.py to
bake the fixes into the published site.

Saving only works through this server: the editor checks for localhost, so the
public GitHub Pages copy of the page is read-only and can't touch the data.
"""

import json
import os
import socketserver
import webbrowser
from http.server import SimpleHTTPRequestHandler
from pathlib import Path

REPO = Path("/Users/ggibson1/Desktop/Kramer-Projects-2026/korean-photo-slideshow")
DOCS = REPO / "docs"
FEEDBACK = Path.home() / "Dropbox" / "KRAMOS" / "korean-photo-feedback"
PORT = 8777


def find_json_for_photo(photo_name):
    """Return (path, data) for the feedback JSON whose 'photo' field matches."""
    for jf in sorted(FEEDBACK.glob("*.json")):
        if jf.name == "photo-vocab-log.json":
            continue
        try:
            with open(jf) as f:
                data = json.load(f)
        except Exception:
            continue
        if isinstance(data, dict) and data.get("photo") == photo_name:
            return jf, data
    return None, None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DOCS), **kwargs)

    def _send_json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/save":
            self._send_json(404, {"ok": False, "error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send_json(400, {"ok": False, "error": f"bad request: {e}"})
            return

        photo = payload.get("photo")
        bbox = payload.get("bbox")
        if not photo or not isinstance(bbox, list):
            self._send_json(400, {"ok": False, "error": "missing photo or bbox"})
            return

        path, data = find_json_for_photo(photo)
        if path is None:
            self._send_json(404, {"ok": False, "error": f"no JSON for photo '{photo}'"})
            return

        concepts = data.get("concepts", [])
        if len(bbox) != len(concepts):
            self._send_json(
                400,
                {"ok": False, "error": f"bbox length {len(bbox)} != {len(concepts)} concepts"},
            )
            return

        data["bbox"] = bbox
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._send_json(500, {"ok": False, "error": f"write failed: {e}"})
            return

        boxed = sum(1 for b in bbox if b)
        print(f"  saved {path.name}  ({boxed}/{len(bbox)} words boxed)")
        self._send_json(200, {"ok": True, "file": path.name})

    def log_message(self, *args):
        pass  # quiet the default per-request logging


def main():
    if not DOCS.exists():
        raise SystemExit(f"docs not found: {DOCS} (run deploy.py first)")
    if not FEEDBACK.exists():
        raise SystemExit(f"feedback folder not found: {FEEDBACK}")
    os.chdir(DOCS)
    # #edit makes the page drop straight into the editor on load (localhost only);
    # press 'x' to toggle it closed/open from there.
    url = f"http://localhost:{PORT}/#edit"
    print(f"Lens bbox editor → {url}")
    print("Editor opens automatically. Press 'x' to toggle it. Edit boxes, then Save.")
    print("When finished, run:  python3 deploy.py  (then commit/push)")
    print("Ctrl+C to stop.\n")
    webbrowser.open(url)
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


if __name__ == "__main__":
    main()
