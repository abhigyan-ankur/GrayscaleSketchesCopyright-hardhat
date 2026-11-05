"""
certificate.py
--------------
Builds a downloadable certificate (A4 landscape) for a certified artwork.

Uses Pillow only (already a dependency): the page is drawn as an image and saved
as PDF or PNG. Nothing is stored; the certificate is rendered from the registry
entry each time it is requested.
"""

import io
import os
import re
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont, ImageOps

from config import IMAGES_DIR

W, H = 1754, 1240                     # A4 landscape at 150 dpi
PAPER = (244, 241, 234)
INK = (17, 17, 17)
MUTED = (96, 96, 96)
GREEN = (187, 247, 208)
WHITE = (255, 255, 255)

CHAIN_NAME = "Hardhat Local (development chain)"

# ── fonts: find a real TTF on any Linux distro, fall back to Pillow's own ────
_FONT_INDEX = None
_FONT_PREFS = {
    "serif_bold": ["DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"],
    "sans":       ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
    "sans_bold":  ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
    "mono":       ["DejaVuSansMono.ttf", "LiberationMono-Regular.ttf"],
}


def _index_fonts() -> dict:
    global _FONT_INDEX
    if _FONT_INDEX is None:
        _FONT_INDEX = {}
        roots = ["/usr/share/fonts", "/usr/local/share/fonts",
                 os.path.expanduser("~/.fonts"), os.path.expanduser("~/.local/share/fonts")]
        for root in roots:
            for d, _, files in os.walk(root):
                for f in files:
                    if f.lower().endswith(".ttf"):
                        _FONT_INDEX.setdefault(f, os.path.join(d, f))
    return _FONT_INDEX


def _font(kind: str, size: int):
    index = _index_fonts()
    for name in _FONT_PREFS[kind]:
        if name in index:
            return ImageFont.truetype(index[name], size)
    try:
        return ImageFont.load_default(size=size)       # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


# ── small drawing helpers ────────────────────────────────────────────────────

def _wrap(draw, text: str, font, max_w: int) -> list:
    """Word-wraps text; very long unbroken strings (hashes) are cut by width."""
    lines, current = [], ""
    for word in str(text).split(" "):
        candidate = word if not current else f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_w:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        while draw.textlength(word, font=font) > max_w:      # break a long token
            cut = len(word)
            while cut > 1 and draw.textlength(word[:cut], font=font) > max_w:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _centered(draw, y, text, font, fill=INK, spacing=0):
    if spacing:
        total = sum(draw.textlength(c, font=font) for c in text) + spacing * (len(text) - 1)
        x = (W - total) / 2
        for c in text:
            draw.text((x, y), c, font=font, fill=fill)
            x += draw.textlength(c, font=font) + spacing
    else:
        draw.text(((W - draw.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)


def _pretty_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %B %Y, %H:%M UTC")
    except Exception:
        return iso or "—"


def _artwork_image(entry: dict, box: tuple):
    name = entry.get("local_image")
    path = os.path.join(IMAGES_DIR, name) if name else None
    if path and os.path.exists(path):
        try:
            img = Image.open(path)
            img = ImageOps.exif_transpose(img).convert("RGB")
            return ImageOps.contain(img, box, Image.LANCZOS)
        except Exception:
            pass
    return None


# ── the certificate ──────────────────────────────────────────────────────────

def certificate_id(entry: dict) -> str:
    return f"ARTCHAIN-{int(entry['id']):06d}"


def render_certificate(entry: dict) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # frame
    d.rectangle([36, 36, W - 36, H - 36], outline=INK, width=8)
    d.rectangle([58, 58, W - 58, H - 58], outline=INK, width=2)

    # header
    _centered(d, 88, "ARTCHAIN", _font("sans_bold", 26), spacing=12)
    _centered(d, 132, "Certificate of Registration", _font("serif_bold", 76))
    _centered(d, 236, "Proof of authorship recorded on the Artchain registry",
              _font("sans", 26), fill=MUTED)
    d.line([120, 292, W - 120, 292], fill=INK, width=3)

    # artwork frame (offset shadow, like the site)
    bx, by, bw, bh = 120, 336, 620, 620
    d.rectangle([bx + 14, by + 14, bx + bw + 14, by + bh + 14], fill=INK)
    d.rectangle([bx, by, bx + bw, by + bh], fill=WHITE, outline=INK, width=6)
    art = _artwork_image(entry, (bw - 36, bh - 36))
    if art:
        img.paste(art, (bx + (bw - art.width) // 2, by + (bh - art.height) // 2))
    else:
        f = _font("sans", 26)
        _t = "Image not stored on this server"
        d.text((bx + (bw - d.textlength(_t, font=f)) / 2, by + bh / 2 - 14), _t, font=f, fill=MUTED)
    cid = certificate_id(entry)
    f = _font("mono", 28)
    d.text((bx + (bw - d.textlength(cid, font=f)) / 2, by + bh + 36), cid, font=f, fill=INK)

    # seal
    cx, cy, r = bx + bw - 10, by + bh - 10, 84
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN, outline=INK, width=6)
    for text, dy, kind, size in (("CERTIFIED", -22, "sans_bold", 22), ("ON", 4, "sans", 18),
                                 ("ARTCHAIN", 26, "sans_bold", 20)):
        f = _font(kind, size)
        d.text((cx - d.textlength(text, font=f) / 2, cy + dy - size / 2), text, font=f, fill=INK)

    # right column
    x0, col_w = 840, W - 120 - 840
    y = 336
    tf = _font("serif_bold", 56)
    title_lines = _wrap(d, entry.get("title") or "Untitled", tf, col_w)
    if len(title_lines) > 2:
        title_lines = title_lines[:2]
        title_lines[1] = title_lines[1].rstrip(" .") + "…"
    for line in title_lines:
        d.text((x0, y), line, font=tf, fill=INK)
        y += 66
    d.text((x0, y + 4), f"by {entry.get('author') or 'Unknown'}", font=_font("sans", 34), fill=MUTED)
    y += 74
    d.line([x0, y, x0 + col_w, y], fill=INK, width=2)
    y += 26

    owner = entry.get("owner_address") or "—"
    onchain = entry.get("onchain_id")
    fields = [
        ("REGISTERED", _pretty_date(entry.get("timestamp"))),
        ("CERTIFICATE ID", cid),
        ("OWNER WALLET", owner),
        ("ARTWORK FINGERPRINT (PHASH)", entry.get("phash") or "—"),
        ("IMAGE ID", entry.get("image_cid") or "—"),
        ("ON-CHAIN ID", f"#{onchain}" if onchain is not None else "—"),
        ("TRANSACTION", entry.get("tx_hash") or "—"),
    ]
    lf, vf = _font("sans_bold", 18), _font("mono", 24)
    for label, value in fields:
        d.text((x0, y), label, font=lf, fill=MUTED)
        y += 24
        for line in _wrap(d, value, vf, col_w):
            d.text((x0, y), line, font=vf, fill=INK)
            y += 30
        y += 9

    # footer
    note = (f"This certificate records that the artwork above was registered on "
            f"{_pretty_date(entry.get('timestamp'))} with the fingerprint shown. "
            f"Network: {CHAIN_NAME}.")
    ff = _font("sans", 22)
    fy = 1112
    for line in _wrap(d, note, ff, W - 400):
        _centered(d, fy, line, ff, fill=MUTED)
        fy += 30
    return img


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "artwork"


def build_certificate(entry: dict, fmt: str = "pdf"):
    """Returns (bytes, media_type, filename) for a certified entry."""
    img = render_certificate(entry)
    buf = io.BytesIO()
    base = f"artchain-certificate-{int(entry['id']):06d}-{_slug(entry.get('title'))}"
    if fmt == "png":
        img.save(buf, "PNG", dpi=(150, 150))
        return buf.getvalue(), "image/png", f"{base}.png"
    img.save(buf, "PDF", resolution=150.0, title=f"Artchain certificate {certificate_id(entry)}")
    return buf.getvalue(), "application/pdf", f"{base}.pdf"
