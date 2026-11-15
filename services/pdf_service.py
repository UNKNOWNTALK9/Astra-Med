"""Professional PDF medical report (ReportLab). Charts are rendered with Matplotlib's Agg
backend (no Tk), so this can run safely in a worker thread."""
import io
from datetime import datetime
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from config import APP_NAME, PARAM_KEYS, REFERENCE_RANGES, REPORTS_DIR, SIMULATION_NOTICE, TAGLINE
from core.analytics_engine import status_breakdown, summary_stats
from core.anomaly_detector import DISCLAIMER, AnomalyDetector
from core.authentication import can
from utils.helpers import ensure_logo

NAVY, SKY = colors.HexColor("#0E1626"), colors.HexColor("#38BDF8")
GREY = colors.HexColor("#64748B")
SEV_BG = {"critical": colors.HexColor("#FEE2E2"), "warning": colors.HexColor("#FEF3C7"),
          "normal": colors.HexColor("#DCFCE7"), "info": colors.HexColor("#E0F2FE")}


def _chart(df, series, title, ylabel, band=None, width=7.2, height=2.3):
    fig = Figure(figsize=(width, height), dpi=150)
    ax = fig.add_subplot(111)
    d = df.set_index("timestamp")
    if len(d) > 1500:
        d = d.resample("h").mean(numeric_only=True)
    for key, label, color in series:
        ax.plot(d.index, d[key], lw=1.1, color=color, label=label)
    if band:
        ax.axhspan(band[0], band[1], color="#22C55E", alpha=0.10, lw=0)
    ax.set_title(title, fontsize=9, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=7)
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.25)
    if len(series) > 1:
        ax.legend(fontsize=7, frameon=False, ncol=len(series))
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    buf = io.BytesIO()
    FigureCanvasAgg(fig).print_png(buf)
    buf.seek(0)
    return Image(buf, width=172 * mm, height=172 * mm * height / width)


def _table(data, col_widths=None, header=True, zebra=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    st = [("FONTSIZE", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    if zebra:
        st += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")])]
    t.setStyle(TableStyle(st))
    return t


def build_report(db, user, astronaut_id, start, end, out_path=None, detector=None,
                 include_charts=True, include_anomalies=True, include_alerts=True,
                 include_history=False):
    """Generate the PDF; registers it in health_reports. Returns the output Path."""
    a = db.get_astronaut(astronaut_id)
    if not a:
        raise ValueError("Astronaut not found.")
    df = db.readings_df([astronaut_id], start, end)
    if df.empty:
        raise ValueError("No readings in the selected period.")
    now = datetime.now()
    out_path = Path(out_path or REPORTS_DIR / f"report_{a['code']}_{now:%Y%m%d_%H%M%S}.pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontSize=18, textColor=NAVY, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, textColor=NAVY, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=8.5, leading=11.5)
    small = ParagraphStyle("s", parent=body, fontSize=7, textColor=GREY)
    notice = ParagraphStyle("n", parent=body, backColor=colors.HexColor("#FEF3C7"), borderPadding=5,
                            textColor=colors.HexColor("#92400E"), fontName="Helvetica-Bold")

    story = []
    logo = Image(str(ensure_logo()), width=18 * mm, height=18 * mm)
    head = Table([[logo, [Paragraph(f"{APP_NAME} Medical Report", h1),
                          Paragraph(f"{TAGLINE}", small)]]], colWidths=[22 * mm, 150 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [head, Spacer(1, 4), Paragraph(SIMULATION_NOTICE, notice), Spacer(1, 6)]

    # Mission information
    story.append(Paragraph("1. Mission Information", h2))
    missions = db.astronaut_missions(astronaut_id)
    if missions:
        data = [["Mission", "Spacecraft", "Launch", "Return", "Status"]] + [
            [f"{m['code']} {m['name']}", m["spacecraft"], m["launch_date"], m["return_date"], m["status"]]
            for m in missions]
        story.append(_table(data, [52 * mm, 38 * mm, 25 * mm, 25 * mm, 22 * mm]))
    else:
        story.append(Paragraph("Not assigned to a mission.", body))

    # Astronaut information
    story.append(Paragraph("2. Astronaut Information", h2))
    info = [["ID", a["code"], "Name", a["full_name"]], ["Age", a["age"], "Role", a["role"]],
            ["Spacecraft", a["spacecraft"], "Blood group", a["blood_group"] or "-"],
            ["Joined", a["joined_date"], "Current status", a["health_status"].upper()],
            ["Emergency contact", f"{a['emergency_contact_name']} {a['emergency_contact_phone']}", "Report period",
             f"{df['timestamp'].min():%Y-%m-%d} to {df['timestamp'].max():%Y-%m-%d}"]]
    t = _table(info, [32 * mm, 55 * mm, 28 * mm, 55 * mm], header=False, zebra=False)
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E2E8F0")),
                           ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E2E8F0"))]))
    story.append(t)

    # Health summary
    br = status_breakdown(df)
    alerts_all = db.list_alerts(astronaut_id=astronaut_id, limit=5000, start=start, end=end)
    n_alert = sum(1 for x in alerts_all if x["severity"] in ("warning", "critical"))
    story.append(Paragraph("3. Health Summary", h2))
    story.append(Paragraph(
        f"{len(df):,} simulated readings were analysed. Readings within the configured normal ranges: "
        f"<b>{br['normal']:.1f}%</b>; warning: <b>{br['warning']:.1f}%</b>; critical: <b>{br['critical']:.1f}%</b>. "
        f"{n_alert} warning/critical alerts were raised in this period.", body))

    # Vital statistics
    story.append(Paragraph("4. Vital-Sign Statistics", h2))
    stats_df = summary_stats(df)
    rows = [["Parameter", "Unit", "Min", "Mean", "Max", "Std", "Out of range", "Normal range"]]
    for _, r in stats_df.iterrows():
        rows.append([r["label"], r["unit"], f"{r['min']:.1f}", f"{r['mean']:.1f}", f"{r['max']:.1f}",
                     f"{r['std']:.2f}", f"{r['out_pct']:.1f}%", r["range"]])
    story.append(_table(rows, [30 * mm, 17 * mm, 16 * mm, 16 * mm, 16 * mm, 14 * mm, 26 * mm, 28 * mm]))

    # Charts
    if include_charts:
        story.append(PageBreak())
        story.append(Paragraph("5. Historical Charts", h2))
        specs = [([("heart_rate", "Heart rate", "#0284C7")], "Heart Rate", "BPM", REFERENCE_RANGES["heart_rate"]["range"][1:3]),
                 ([("spo2", "SpO2", "#7C3AED")], "Blood Oxygen Saturation", "%", REFERENCE_RANGES["spo2"]["range"][1:3]),
                 ([("systolic", "Systolic", "#DC2626"), ("diastolic", "Diastolic", "#2563EB")], "Blood Pressure", "mmHg", None),
                 ([("temperature", "Temperature", "#D97706")], "Body Temperature", "°C", REFERENCE_RANGES["temperature"]["range"][1:3]),
                 ([("resp_rate", "Resp. rate", "#059669")], "Respiratory Rate", "br/min", REFERENCE_RANGES["resp_rate"]["range"][1:3])]
        for series, title, yl, band in specs:
            story.append(_chart(df, series, title, yl, band))
            story.append(Spacer(1, 3))

    # Anomalies
    if include_anomalies:
        story.append(Paragraph("6. Detected Anomalies (AI-assisted)", h2))
        if detector is not None and detector.ready:
            scored = detector.score_df(df)
            flagged = scored[scored["is_anomaly"]].sort_values("anomaly_score", ascending=False).head(12)
            trends = AnomalyDetector.trends(df)
            story.append(Paragraph(detector.summarize(a["full_name"], scored, trends).replace("\n", "<br/>"), body))
            if not flagged.empty:
                rows = [["Time", "Score", "Contributing factors"]]
                for _, r in flagged.iterrows():
                    rows.append([f"{r['timestamp']:%Y-%m-%d %H:%M}", f"{r['anomaly_score']:.0f}",
                                 Paragraph("; ".join(detector.reasons(r, a['code'])), small)])
                story += [Spacer(1, 4), _table(rows, [32 * mm, 14 * mm, 126 * mm])]
        else:
            story.append(Paragraph("AI model not available; no anomaly analysis was included. " + DISCLAIMER, body))

    # Alerts
    if include_alerts:
        story.append(Paragraph("7. Alert History", h2))
        if alerts_all:
            rows = [["Time", "Severity", "Message", "Ack"]]
            for x in alerts_all[:30]:
                rows.append([x["timestamp"][:16], x["severity"].upper(), Paragraph(x["message"], small),
                             "yes" if x["acknowledged"] else "no"])
            t = _table(rows, [32 * mm, 20 * mm, 112 * mm, 10 * mm])
            t.setStyle(TableStyle([("BACKGROUND", (1, i), (1, i), SEV_BG[x["severity"]])
                                   for i, x in enumerate(alerts_all[:30], 1)]))
            story.append(t)
            if len(alerts_all) > 30:
                story.append(Paragraph(f"Showing 30 of {len(alerts_all)} alerts.", small))
        else:
            story.append(Paragraph("No alerts in this period.", body))

    # Restricted medical history
    if include_history and can(user, "medical_history"):
        story.append(Paragraph("8. Medical History (restricted)", h2))
        hist = db.list_history(astronaut_id)
        if hist:
            story.append(_table([["Date", "Condition", "Notes"]] + [[h["entry_date"], h["condition"], Paragraph(h["notes"], small)]
                                                                      for h in hist], [26 * mm, 50 * mm, 96 * mm]))
        else:
            story.append(Paragraph("No entries.", body))

    story += [Spacer(1, 10), Paragraph(f"Report generated {now:%Y-%m-%d %H:%M} by "
                                       f"{user['full_name'] or user['username']}. {DISCLAIMER}", small)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(18 * mm, 10 * mm, f"{APP_NAME} | {a['code']} | SIMULATED DATA")
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
        canvas.setStrokeColor(SKY)
        canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
        canvas.restoreState()

    SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=14 * mm, bottomMargin=20 * mm, title=f"{APP_NAME} report {a['code']}",
                      author=APP_NAME).build(story, onFirstPage=footer, onLaterPages=footer)
    db.add_report(astronaut_id, f"{a['full_name']} health report", out_path, "pdf",
                  f"{df['timestamp'].min():%Y-%m-%d}", f"{df['timestamp'].max():%Y-%m-%d}", user["id"])
    db.log("INFO", "reports", f"PDF report generated for {a['code']}", user["id"])
    return out_path
