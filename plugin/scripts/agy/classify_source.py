#!/usr/bin/env python3
"""Classifie une source (fichier local ou URL) pour les skills multimodales du plugin erom-gemini.
Renvoie kind / add_dir / write_file / source. Aucune dépendance hors stdlib."""
import os, re, hashlib, datetime

AUD = (".ogg", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".opus", ".aiff")
VID = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")
IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _slug(s, n):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n]


def _base(src, is_url, n):
    if is_url:
        return _slug(re.sub(r"^https?://(www\.)?", "", src.lower()), n) or "url"
    return _slug(os.path.splitext(os.path.basename(src))[0], n) or "media"


def classify(mode, src, question="", today=None):
    src = src.strip().strip('"')
    low = src.lower()
    is_url = low.startswith("http")
    today = today or datetime.date.today().isoformat()
    if mode == "transcribe":
        kind = "url" if is_url else ("video" if low.endswith(VID) else "audio")
        out = os.path.join("docs", "gemini", "transcripts", f"{_base(src, is_url, 50)}.md")
    elif mode == "video":
        kind = "url" if is_url else "file"
        out = os.path.join("docs", "gemini", "video", f"{_base(src, is_url, 50)}.md")
    elif mode == "media":
        if is_url:
            kind = "url"
        elif low.endswith(VID):
            kind = "video"
        elif low.endswith(AUD):
            kind = "audio"
        elif low.endswith(IMG):
            kind = "image"
        else:
            kind = "file"
        qh = hashlib.sha1(question.encode()).hexdigest()[:6]
        out = os.path.join("docs", "gemini", "media", f"{_base(src, is_url, 40)}-{qh}.md")
    elif mode == "doc-to-md":
        ext = os.path.splitext(low)[1]
        kind = ("pdf" if ext == ".pdf" else "docx" if ext in (".docx", ".doc")
                else "image" if ext in IMG else "html" if ext in (".html", ".htm") else "other")
        base = _slug(os.path.splitext(os.path.basename(src))[0], 60) or "doc"
        out = os.path.join("docs", "gemini", "converted", f"{today}-{base}.md")
    else:
        raise SystemExit(f"unknown mode: {mode}")
    add_dir = "" if is_url else os.path.dirname(os.path.abspath(src))
    return {"kind": kind, "add_dir": add_dir, "write_file": os.path.abspath(out), "source": src}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--question", default="")
    a = ap.parse_args()
    r = classify(a.mode, a.src, a.question)
    print(f"KIND={r['kind']}")
    print(f"ADD_DIR={r['add_dir']}")
    print(f"WRITE_FILE={r['write_file']}")
    print(f"SOURCE={r['source']}")
