"""PDF report — v2 "situation room" redesign (Addendum 2 §3).

Keeps ReportLab + the kaleido PNG path; changes: dark pages with a branded
header/footer on every page, the web UI's accent palette, monospace key-figure
blocks per section, explanatory captions under every chart (from
engine/captions.py — the same text shown on-screen), every web-UI chart
included, and a hard maximum of 2 charts per page.
"""
import io
import os
import tempfile
from datetime import datetime

import plotly.io as pio

from .captions import CHART_CAPTIONS

# v2 visual system (main brief §6) — mirrors web/tailwind.config.ts
_BG = "#0B0F16"
_PANEL = "#10151E"
_EDGE = "#1E2735"
_INK = "#D7DEE8"
_INK_DIM = "#8A94A6"
_INK_FAINT = "#5A6478"
_ACCENT = {
    "transport": "#2DD4EF",
    "poi": "#E86BF0",
    "risk": "#F5A623",
    "nature": "#3ECF8E",
}


def _apply_dark_theme(fig):
    """Style a figure to match the dark UI before kaleido export — otherwise
    charts render as bright white boxes on the dark page (§3.3)."""
    try:
        fig = fig.__class__(fig)  # copy, don't mutate the caller's figure
        fig.update_layout(
            paper_bgcolor=_BG, plot_bgcolor=_PANEL,
            font=dict(color=_INK),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        fig.update_xaxes(gridcolor=_EDGE, zerolinecolor=_EDGE)
        fig.update_yaxes(gridcolor=_EDGE, zerolinecolor=_EDGE)
        if getattr(fig.layout, "mapbox", None) and fig.layout.mapbox.style:
            fig.update_layout(mapbox_style="carto-darkmatter")
        if getattr(fig.layout, "polar", None):
            fig.update_layout(polar=dict(bgcolor=_PANEL))
    except Exception as e:
        print(f"[report] dark theme failed: {e}")
    return fig


def fig_to_image_bytes(fig, width: int = 1400, height: int = 800) -> str | None:
    """Render a Plotly figure to a high-resolution PNG temp file (dark-themed)."""
    try:
        img_bytes = pio.to_image(
            _apply_dark_theme(fig), format="png", width=width, height=height,
            scale=3, engine="kaleido",
        )
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(img_bytes)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"[fig_to_image_bytes] export failed: {e}")
        return None


# Sections mirror the nine web tabs; every chart key charts.py can produce is
# listed (§3.1 audit). (key, title, width_cm, height_cm)
_SECTIONS = [
    ("Overview", "poi", [
        ("poi_dominance_map",  "POI Functional Zone Dominance", 17, 9.5),
        ("poi_distribution",   "POI Distribution by Category",  17, 9.5),
        ("landuse_composition","Land Use Composition",          17, 9.5),
        ("poi_density_contour","POI Activity Density",          17, 9.5),
        ("nearest_services",   "Nearest Essential Services",    17, 9.5),
    ]),
    ("Morphology", "poi", [
        ("far_heatmap",         "Floor Area Ratio Distribution",   17, 9.5),
        ("morphotype_clusters", "Urban Morphotype Clusters",       17, 9.5),
        ("density_gradient",    "Building Height Cross-Sections",  17, 9.5),
        ("morphological_transition", "Metrics vs Distance from Centre", 17, 9.5),
        ("urban_quality",       "Transport × Nature Quality Index", 17, 9.5),
        ("building_heights",    "Building Height Distribution",    17, 9.5),
    ]),
    ("Street Network", "transport", [
        ("street_orientation", "Street Orientation Wind Rose", 17, 9.5),
        ("street_radar",       "Street Network Radar",         17, 9.5),
        ("street_centrality",  "Street Betweenness Centrality",17, 9.5),
    ]),
    ("Transport", "transport", [
        ("road_hierarchy",  "Road Hierarchy",                17, 9.5),
        ("transit_heatmap", "Transit Stop Density",          17, 9.5),
        ("transport_map",   "Transport Accessibility Index", 17, 9.5),
        ("fifteen_min_map", "15-Minute City Score",          17, 9.5),
    ]),
    ("Nature & Risk", "nature", [
        ("nature_map",        "Green Space Accessibility", 17, 9.5),
        ("flood_risk_map",    "Flood Risk Zones",          17, 9.5),
        ("nature_radar",      "Nature Radar",              17, 9.5),
        ("city_15min",        "15-Minute Service Coverage",17, 9.5),
        ("terrain_elevation", "Terrain Elevation",         17, 9.5),
        ("terrain_flood_risk","Terrain Flood Risk",        17, 9.5),
        ("terrain_cross",     "Density × Elevation",       17, 9.5),
        ("twi_distribution",  "Topographic Wetness Index", 17, 9.5),
        ("slope_elevation",   "Slope × Elevation",         17, 9.5),
        ("heat_island_map",   "Urban Heat Island Proxy",   17, 9.5),
    ]),
    ("Cross-Analysis", "poi", [
        ("opportunity_surface",   "Opportunity Surface (3D)",       17, 10.5),
        ("cross_morph_transport", "Morphology × Transport Matrix",  17, 9.5),
        ("cross_nature_density",  "Nature × Density Matrix",        17, 9.5),
        ("cross_transport_nature","Transport × Nature Matrix",      17, 9.5),
        ("landuse_crossref",      "Land Use Cross-Reference",       17, 9.5),
    ]),
    ("Stress & Risk", "risk", [
        ("stress_map",        "Urban Stress Index",          17, 9.5),
        ("stress_decomp",     "Stress Decomposition",        17, 9.5),
        ("vulnerability_map", "Temporal Vulnerability Index",17, 9.5),
        ("stress_pareto",     "Stress Pareto Analysis",      17, 9.5),
        ("vuln_vs_stress",    "Vulnerability vs Stress",     17, 9.5),
    ]),
    ("Typology", "poi", [
        ("fabric_matrix",    "Urban Fabric Typology Matrix", 17, 9.5),
        ("fabric_map",       "Fabric Types — Spatial",       17, 9.5),
        ("morphotype_radar", "Morphotype DNA Radar",         17, 9.5),
        ("segregation_map",  "Segregation Proxy",            17, 9.5),
    ]),
    ("District Scores", "transport", [
        ("district_scorecard", "District Performance Scorecard", 17, 10.5),
    ]),
]


def _fmt_num(v, kind="int"):
    try:
        if kind == "int":
            return f"{int(v):,}"
        if kind == "pct":
            return f"{float(v):.1f}%"
        if kind == "f3":
            return f"{float(v):.3f}"
        if kind == "f1":
            return f"{float(v):.1f}"
    except Exception:
        pass
    return str(v)


def _section_key_figures(section: str, ms: dict, sc: dict) -> list:
    """Headline numbers per section — same stats the web tabs show up top."""
    ms, sc = ms or {}, sc or {}
    if section == "Overview":
        return [("Total Buildings", _fmt_num(ms.get("total_buildings", 0))),
                ("Total POIs", _fmt_num(ms.get("total_pois", 0))),
                ("Green Space", _fmt_num(ms.get("green_space_pct", 0), "pct")),
                ("Dominant Morphotype", str(ms.get("dominant_morphotype", "N/A")))]
    if section == "Morphology":
        return [("Median Building Height", f"{_fmt_num(ms.get('median_height', 0), 'f1')} m"),
                ("Dominant Morphotype", str(ms.get("dominant_morphotype", "N/A")))]
    if section == "Street Network":
        return [("Orientation Entropy", _fmt_num(sc.get("orientation_entropy", 0), "f3")),
                ("Dead-End Ratio", _fmt_num(100 * float(sc.get("dead_end_ratio", 0) or 0), "pct")),
                ("Block Size Median", f"{_fmt_num(sc.get('block_size_median', 0))} m²")]
    if section == "Transport":
        rows = [("Transit Stops", _fmt_num(sc.get("transit_stops_count", 0))),
                ("Cycling Infra", f"{_fmt_num(sc.get('cycling_km', 0), 'f1')} km"),
                ("Transport Index", _fmt_num(ms.get("transport_index_mean", 0), "f3")),
                ("Dominant Road", str(sc.get("dominant_road", "N/A")).title())]
        if sc.get("score_15min_mean") is not None:
            rows.append(("15-Min Score", _fmt_num(sc.get("score_15min_mean", 0), "f1")))
        return rows
    if section == "Nature & Risk":
        return [("Green Space Coverage", _fmt_num(ms.get("green_space_pct", 0), "pct")),
                ("High Flood Risk Zones", _fmt_num(sc.get("high_flood_pct", 0), "pct")),
                ("Water Bodies", _fmt_num(sc.get("water_bodies_count", 0)))]
    if section == "Stress & Risk":
        return [("Mean Urban Stress", _fmt_num(ms.get("urban_stress_mean", 0), "f3"))]
    if section == "Typology":
        return [("Dominant Morphotype", str(ms.get("dominant_morphotype", "N/A")))]
    return []


def generate_pdf_report(
    city_name: str,
    metrics_summary: dict,
    figures: dict,
    ai_insights: str = "",
    scalars: dict = None,
) -> bytes:
    """Generate the dark, branded PDF report. `figures` maps chart keys (same
    keys as the web UI result) to go.Figure objects."""
    try:
        from reportlab.lib.colors import HexColor
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            BaseDocTemplate, Frame, HRFlowable, Image, PageBreak, PageTemplate,
            Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError as exc:
        raise ImportError(f"reportlab is required for PDF export: {exc}")

    page_w, page_h = A4
    margin = 1.3 * cm  # §3.3: dense layout, down from 2cm

    def _page_chrome(canvas, doc):
        """Dark background + persistent branded header/footer on EVERY page."""
        canvas.saveState()
        canvas.setFillColor(HexColor(_BG))
        canvas.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        canvas.setFont("Courier-Bold", 8)
        canvas.setFillColor(HexColor(_ACCENT["transport"]))
        canvas.drawString(margin, page_h - 0.8 * cm, "URBAN PULSE")
        canvas.setFont("Courier", 8)
        canvas.setFillColor(HexColor(_INK_DIM))
        canvas.drawRightString(page_w - margin, page_h - 0.8 * cm,
                               f"Urban Spatial Analytics — {city_name}")
        canvas.setStrokeColor(HexColor(_EDGE))
        canvas.setLineWidth(0.5)
        canvas.line(margin, page_h - 1.0 * cm, page_w - margin, page_h - 1.0 * cm)
        canvas.line(margin, 0.9 * cm, page_w - margin, 0.9 * cm)
        canvas.setFillColor(HexColor(_INK_FAINT))
        canvas.setFont("Courier", 7)
        canvas.drawString(margin, 0.55 * cm,
                          "Data: Overture Maps + OpenStreetMap · Open-Meteo")
        canvas.drawRightString(page_w - margin, 0.55 * cm, f"p. {doc.page}")
        canvas.restoreState()

    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        rightMargin=margin, leftMargin=margin,
        topMargin=margin + 0.5 * cm, bottomMargin=margin,
    )
    frame = Frame(margin, margin, page_w - 2 * margin,
                  page_h - 2 * margin - 0.5 * cm, id="main")
    doc.addPageTemplates([PageTemplate(id="dark", frames=[frame],
                                       onPage=_page_chrome)])

    style_title = ParagraphStyle(
        "Title", fontSize=26, leading=30, spaceAfter=4,
        textColor=HexColor(_INK), alignment=TA_LEFT, fontName="Helvetica-Bold")
    style_subtitle = ParagraphStyle(
        "Subtitle", fontSize=12, leading=16, textColor=HexColor(_INK_DIM),
        spaceAfter=14, fontName="Helvetica")
    style_h2 = ParagraphStyle(
        "H2", fontSize=15, leading=19, spaceBefore=8, spaceAfter=6,
        textColor=HexColor(_INK), fontName="Helvetica-Bold")
    style_h3 = ParagraphStyle(
        "H3", fontSize=11, leading=14, spaceBefore=6, spaceAfter=2,
        textColor=HexColor(_INK), fontName="Helvetica-Bold")
    style_body = ParagraphStyle(
        "Body", fontSize=9.5, leading=13.5, spaceAfter=5,
        textColor=HexColor(_INK_DIM), fontName="Helvetica")
    style_caption = ParagraphStyle(
        "Caption", fontSize=7.5, leading=10, spaceAfter=8,
        textColor=HexColor(_INK_FAINT), fontName="Helvetica")
    style_insight = ParagraphStyle(
        "Insight", fontSize=9.5, leading=14, spaceAfter=6, leftIndent=10,
        textColor=HexColor(_INK_DIM), fontName="Helvetica")

    def _accent_rule(section_accent):
        return HRFlowable(width="100%", thickness=1.5,
                          color=HexColor(_ACCENT.get(section_accent,
                                                     _ACCENT["transport"])))

    def _key_figures_table(rows):
        """Monospace stat block (§3.3), mirrors the web UI's stat tiles."""
        if not rows:
            return None
        data = [[label.upper() for label, _ in rows],
                [value for _, value in rows]]
        t = Table(data, colWidths=[(page_w - 2 * margin) / len(rows)] * len(rows))
        t.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), HexColor(_PANEL)),
            ("BOX",          (0, 0), (-1, -1), 0.5, HexColor(_EDGE)),
            ("INNERGRID",    (0, 0), (-1, -1), 0.5, HexColor(_EDGE)),
            ("FONTNAME",     (0, 0), (-1, 0), "Courier"),
            ("FONTSIZE",     (0, 0), (-1, 0), 6.5),
            ("TEXTCOLOR",    (0, 0), (-1, 0), HexColor(_INK_FAINT)),
            ("FONTNAME",     (0, 1), (-1, 1), "Courier-Bold"),
            ("FONTSIZE",     (0, 1), (-1, 1), 11),
            ("TEXTCOLOR",    (0, 1), (-1, 1), HexColor(_INK)),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 7),
        ]))
        return t

    tmp_files: list = []
    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph("Urban Pulse", style_title))
    story.append(Paragraph("Urban Spatial Analytics Report", style_subtitle))
    story.append(_accent_rule("transport"))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(f"<b>City:</b> {city_name}", style_body))
    story.append(Paragraph(
        f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y at %H:%M')}",
        style_body))
    story.append(Paragraph(
        "<b>Data sources:</b> Overture Maps Places, OpenStreetMap (Overpass), "
        "Open-Meteo elevation & forecast", style_body))
    story.append(Spacer(1, 0.5 * cm))

    kf = _key_figures_table(_section_key_figures("Overview", metrics_summary, scalars))
    if kf:
        story.append(kf)
        story.append(Spacer(1, 0.5 * cm))

    # ── AI Insights ───────────────────────────────────────────────────────────
    if ai_insights and "unavailable" not in ai_insights.lower()[:30]:
        story.append(Paragraph("AI Analysis", style_h2))
        story.append(_accent_rule("poi"))
        story.append(Spacer(1, 0.2 * cm))
        for line in ai_insights.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), style_insight))

    # ── Chart sections — max 2 charts per page (§3.2) ─────────────────────────
    for section_title, accent, charts in _SECTIONS:
        present = [(k, t, w, h) for (k, t, w, h) in charts
                   if figures.get(k) is not None]
        if not present:
            continue
        story.append(PageBreak())
        story.append(Paragraph(section_title, style_h2))
        story.append(_accent_rule(accent))
        story.append(Spacer(1, 0.25 * cm))
        if section_title != "Overview":  # Overview key figures already on cover
            kf = _key_figures_table(
                _section_key_figures(section_title, metrics_summary, scalars))
            if kf:
                story.append(kf)
                story.append(Spacer(1, 0.3 * cm))

        on_page = 0
        for fig_key, fig_title, w_cm, h_cm in present:
            if on_page == 2:  # hard 2-per-page rule (§3.2)
                story.append(PageBreak())
                on_page = 0
            fig = figures.get(fig_key)
            try:
                story.append(Paragraph(fig_title, style_h3))
                w_px = int(w_cm * 37.8 * 2.2)
                h_px = int(h_cm * 37.8 * 2.2)
                img_path = fig_to_image_bytes(fig, width=w_px, height=h_px)
                if img_path:
                    tmp_files.append(img_path)
                    story.append(Image(img_path, width=w_cm * cm, height=h_cm * cm))
                else:
                    story.append(Paragraph("[Chart image unavailable]", style_body))
                caption = CHART_CAPTIONS.get(fig_key)
                if caption:
                    story.append(Paragraph(caption, style_caption))
                on_page += 1
            except Exception as exc:
                story.append(Paragraph(f"Chart unavailable: {exc}", style_body))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story)
    for f in tmp_files:
        try:
            os.unlink(f)
        except Exception:
            pass
    buffer.seek(0)
    return buffer.read()
