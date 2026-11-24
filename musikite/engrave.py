"""
Engraving of a music21 score (inside a Score object).

Pipeline (open source only):
  music21 -> MusicXML -> Verovio (SVG pages, font Leland) -> svglib/reportlab
  (lines and texts) + PyMuPDF (SMuFL glyphs as text in the embedded Leland
  font, like MuseScore PDFs) -> one PDF, readable by scoreread.
"""
import io
import os
import re
import tempfile
import warnings

_EMPTY0 = re.compile(r'<text[^>]*font-size="0px"[^>]*/>')
_TEXT0 = re.compile(r'<text([^>]*?)font-size="0px"([^>]*?)(?<!/)>(.*?)</text>', re.S)
_LEAF = re.compile(r'<tspan([^>]*)>([^<]*)</tspan>')
_ATTR = re.compile(r'(\w[\w-]*)="([^"]*)"')


A4_WIDTH_PT = 595.28
_INNER = re.compile(r'<svg class="definition-scale"[^>]*viewBox="([^"]*)"[^>]*>')


def _unwrap(svg):
    """svglib mis-scales Verovio's nested <svg class="definition-scale">:
    move its viewBox to the outer <svg> and drop the inner element."""
    m = _INNER.search(svg)
    if not m:
        return svg
    group = re.sub(r'\s(viewBox|class)="[^"]*"', "", m.group(0)).replace("<svg", "<g", 1)
    svg = svg[:m.start()] + group + svg[m.end():]
    k = svg.rfind("</svg>", 0, svg.rfind("</svg>"))       # closing tag of the inner <svg>
    svg = svg[:k] + "</g>" + svg[k + 6:]
    return svg.replace("<svg ", f'<svg viewBox="{m.group(1)}" ', 1)


def _flatten_texts(svg, note="M.M."):
    """svglib does not handle Verovio's nested <tspan> inside a 0-size <text>
    (used for tempo marks): rebuild them as one plain <text>. The SMuFL note
    glyph of a metronome mark becomes `note` ('M.M.' in PDFs, whose fonts may lack the
    note sign; the staff on screen uses '♩', owner 2026-11-08: "♩ = 120 is better")."""
    def fix(m):
        attrs = dict(_ATTR.findall(m.group(1) + m.group(2)))
        for opening in re.findall(r'<tspan([^>]*)>', m.group(3)):   # position on a tspan (headers)
            for k, v in _ATTR.findall(opening):
                if k in ("x", "y", "text-anchor"):
                    attrs.setdefault(k, v)
        parts, size = [], 0.0
        for tattr, txt in _LEAF.findall(m.group(3)):
            a = dict(_ATTR.findall(tattr))
            if a.get("font-family", "").lower() in ("leipzig", "bravura", "leland", "petaluma"):
                if txt.strip():
                    parts.append(note)
                continue
            if txt.strip():
                parts.append(txt.strip())
                fs = a.get("font-size", "0px").replace("px", "")
                try:
                    size = max(size, float(fs))
                except ValueError:
                    pass
        if not parts or not size:
            return ""
        x, y = attrs.get("x", "0"), attrs.get("y", "0")
        anchor = attrs.get("text-anchor")
        anchor = f' text-anchor="{anchor}"' if anchor else ""
        return (f'<text x="{x}" y="{y}"{anchor} font-size="{size:g}px" font-family="Times, serif">'
                f'{" ".join(parts)}</text>')
    return _TEXT0.sub(fix, _EMPTY0.sub("", svg))


def svg_pages(score, scale=50, page_width=2100, page_height=2970, adjust=False):
    """Verovio SVG pages (raw strings) of a music21 Score."""
    import verovio
    fd, xml = tempfile.mkstemp(suffix=".musicxml")
    os.close(fd)
    try:
        score.write("musicxml", fp=xml)
        tk = verovio.toolkit()
        tk.setOptions({"pageWidth": page_width, "pageHeight": page_height, "scale": scale,
                       "footer": "none", "header": "auto", "breaks": "auto",
                       "adjustPageHeight": adjust, "font": MUSIC_FONT})
        if not tk.loadFile(xml):
            raise RuntimeError("Verovio could not read the MusicXML")
        return [tk.renderToSVG(k) for k in range(1, tk.getPageCount() + 1)]
    finally:
        os.remove(xml)


MUSIC_FONT = "Leland"                     # Verovio layout font = font embedded in PDFs
FONT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "Leland.ttf")
_SVG_NS = "http://www.w3.org/2000/svg"
_XLINK = "{http://www.w3.org/1999/xlink}href"
_TF = re.compile(r"(translate|scale|matrix)\(([^)]*)\)")


def _affine(tf):
    """SVG transform string -> (a, b, c, d, e, f)."""
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for kind, args in _TF.findall(tf or ""):
        v = [float(t) for t in re.split(r"[\s,]+", args.strip()) if t]
        if kind == "translate":
            n = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif kind == "scale":
            n = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        else:
            n = tuple(v)
        m = _mul(m, n)
    return m


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D,
            a * E + c * F + e, b * E + d * F + f)


def split_glyphs(svg):
    """Remove the SMuFL glyphs (<use> of a symbol) from a Verovio SVG page.
    Returns (svg without glyphs, [(codepoint, x, y, em), ...]) in viewBox units:
    (x, y) is the glyph origin (baseline), em the font size. Hidden
    placeholders are dropped too, and open lines get fill="none" (otherwise
    svglib also writes them as filled paths, doubling every staff line)."""
    import xml.etree.ElementTree as ET
    ET.register_namespace("", _SVG_NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    root = ET.fromstring(svg)
    glyphs = []

    def walk(el, m, dots=False):
        for ch in list(el):
            tag = ch.tag.split("}")[-1]
            if "placeholder" in (ch.get("class") or ""):
                el.remove(ch)
                continue
            cm = _mul(m, _affine(ch.get("transform")))
            if tag == "use":
                ref = (ch.get(_XLINK) or ch.get("href") or "").lstrip("#")
                code = ref.split("-")[0]
                try:
                    cp = int(code, 16)
                except ValueError:
                    continue
                x = float(ch.get("x", 0) or 0)
                y = float(ch.get("y", 0) or 0)
                a, b, c, d, e, f = cm
                em = 1000.0 * abs(d)
                w = ch.get("height")
                if w and abs(d - 1) < 1e-9:              # sized by width/height, no scale
                    em = float(w.replace("px", ""))
                glyphs.append((cp, a * x + c * y + e, b * x + d * y + f, em))
                el.remove(ch)
            elif tag == "ellipse" and dots:            # augmentation dot -> SMuFL glyph
                rx = float(ch.get("rx"))
                x, y = float(ch.get("cx")) - rx, float(ch.get("cy"))
                a, b, c, d, e, f = cm
                glyphs.append((0xE1E7, a * x + c * y + e, b * x + d * y + f, 20 * rx * abs(d)))
                el.remove(ch)
            elif tag == "path" and ch.get("fill") is None and not re.search(r"[CcQqZzAa]", ch.get("d", "")):
                ch.set("fill", "none")                 # open line: stroke only (SVG default is fill)
                if ch.get("stroke") is None:
                    ch.set("stroke", "black")          # Verovio sets it only through CSS
            elif tag not in ("defs", "style"):
                walk(ch, cm, dots or "dots" in (ch.get("class") or "").split())

    walk(root, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    return ET.tostring(root, encoding="unicode"), glyphs


def score_to_pdf(score, path, scale=50, page_width=2100, page_height=2970, title=None):
    """Engrave a music21 Score to a PDF file.

    Layout by Verovio; lines, stems, beams, ties and texts are vector shapes /
    text, while noteheads, rests, clefs, accidentals, flags, dots and time
    signatures are written as text in the SMuFL font Leland (embedded), as
    MuseScore does: the PDF can be read back by scoreread (Pdf.to_midi)."""
    import pymupdf
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPDF

    font = pymupdf.Font(fontfile=FONT_FILE)
    out = pymupdf.open()
    for page in svg_pages(score, scale, page_width, page_height):
        svg, glyphs = split_glyphs(_flatten_texts(_unwrap(page)))
        vb = [float(v) for v in re.search(r'viewBox="([^"]*)"', svg).group(1).split()]
        drawing = svg2rlg(io.StringIO(svg))
        f = A4_WIDTH_PT / drawing.width                 # page size: A4 in points
        drawing.scale(f, f)
        drawing.width, drawing.height = drawing.width * f, drawing.height * f
        buf = io.BytesIO()
        renderPDF.drawToFile(drawing, buf)
        out.insert_pdf(pymupdf.open("pdf", buf.getvalue()))
        pg = out[-1]
        k = pg.rect.width / vb[2]                       # viewBox unit -> point
        tw = pymupdf.TextWriter(pg.rect)
        for cp, x, y, em in glyphs:
            tw.append(((x - vb[0]) * k, (y - vb[1]) * k), chr(cp), font=font, fontsize=em * k)
        tw.write_text(pg)
    if title:
        out.set_metadata({"title": title, "creator": "musikite"})
    out.subset_fonts()
    out.save(os.path.expanduser(path), garbage=3, deflate=True)
    return out.page_count
