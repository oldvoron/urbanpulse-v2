"""Auto-generated share card (Addendum 2 §8): one 1200×630 social-preview
image per completed analysis — headline numbers + one representative map,
dark visual system. Reuses the same kaleido PNG path as the PDF export and
doubles as the Open Graph preview image for /analysis/[id] (§6).
"""
import base64
import io

_W, _H = 1200, 630  # standard OG image size
_BG = (11, 15, 22)
_PANEL = (16, 21, 30)
_EDGE = (30, 39, 53)
_INK = (215, 222, 232)
_INK_DIM = (138, 148, 166)
_CYAN = (45, 212, 239)

# Representative chart, first available wins
_PREFERRED_CHARTS = ["poi_dominance_map", "stress_map", "transport_map",
                     "far_heatmap", "poi_density_contour"]


def _fonts():
    """DejaVu via matplotlib when available; else Pillow's scalable built-in
    (Pillow ≥ 10.1) — no hard font dependency either way."""
    from PIL import ImageFont

    def _default(size):
        return ImageFont.load_default(size)

    try:
        import matplotlib
        base = matplotlib.get_data_path() + "/fonts/ttf/"
        return {
            "brand": ImageFont.truetype(base + "DejaVuSansMono-Bold.ttf", 26),
            "city": ImageFont.truetype(base + "DejaVuSans-Bold.ttf", 46),
            "label": ImageFont.truetype(base + "DejaVuSansMono.ttf", 15),
            "value": ImageFont.truetype(base + "DejaVuSansMono-Bold.ttf", 34),
            "foot": ImageFont.truetype(base + "DejaVuSans.ttf", 15),
        }
    except Exception:
        return {"brand": _default(26), "city": _default(46),
                "label": _default(15), "value": _default(34),
                "foot": _default(15)}


def generate_share_card(city_name: str, metrics_summary: dict,
                        figures: dict) -> str | None:
    """Compose the card; returns base64-encoded PNG (or None on failure).

    `figures` maps chart keys to go.Figure objects (as in the PDF path).
    """
    try:
        from PIL import Image, ImageDraw
        from .report import _apply_dark_theme
        import plotly.io as pio

        f = _fonts()
        img = Image.new("RGB", (_W, _H), _BG)
        d = ImageDraw.Draw(img)

        # Right side: representative chart/map
        chart_w, chart_h = 640, 520
        fig = next((figures[k] for k in _PREFERRED_CHARTS if figures.get(k)), None)
        if fig is not None:
            try:
                png = pio.to_image(_apply_dark_theme(fig), format="png",
                                   width=chart_w, height=chart_h, scale=1,
                                   engine="kaleido")
                chart = Image.open(io.BytesIO(png))
                img.paste(chart, (_W - chart_w - 30, (_H - chart_h) // 2))
            except Exception as e:
                print(f"[sharecard] chart render failed: {e}")

        # Left side: brand, city, key figures
        x = 40
        d.text((x, 42), "URBAN", font=f["brand"], fill=_INK)
        d.text((x + 100, 42), "PULSE", font=f["brand"], fill=_CYAN)
        d.line([(x, 88), (x + 420, 88)], fill=_EDGE, width=2)

        city = city_name if len(city_name) <= 24 else city_name[:23] + "…"
        d.text((x, 116), city, font=f["city"], fill=_INK)

        ms = metrics_summary or {}
        stats = [
            ("TOTAL BUILDINGS", f"{int(ms.get('total_buildings', 0)):,}"),
            ("GREEN SPACE", f"{float(ms.get('green_space_pct', 0)):.1f}%"),
            ("DOMINANT MORPHOTYPE", str(ms.get("dominant_morphotype", "N/A"))),
        ]
        y = 230
        for label, value in stats:
            d.rounded_rectangle([x, y, x + 420, y + 92], radius=6,
                                fill=_PANEL, outline=_EDGE, width=1)
            d.text((x + 16, y + 14), label, font=f["label"], fill=_INK_DIM)
            d.text((x + 16, y + 40), value, font=f["value"], fill=_INK)
            y += 108

        # plain hyphen: Pillow's fallback font lacks the em-dash glyph
        d.text((x, _H - 52), "Urban spatial analytics from open data - "
                             "OSM + Overture Maps", font=f["foot"], fill=_INK_DIM)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        print(f"[sharecard] generation failed: {e}")
        return None
