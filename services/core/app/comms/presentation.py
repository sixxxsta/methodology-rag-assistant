from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from sqlalchemy.orm import Session

from ..config import get_settings
from ..cycles.service import get_work_context
from .service import get_faq

logger = logging.getLogger(__name__)

_FONT_REGISTERED = False


def _ensure_font() -> str:
    global _FONT_REGISTERED
    font_name = "Helvetica"
    if _FONT_REGISTERED:
        return font_name
    try:
        import os

        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for path in candidates:
            if os.path.isfile(path):
                pdfmetrics.registerFont(TTFont("EdAgentSans", path))
                _FONT_REGISTERED = True
                return "EdAgentSans"
    except Exception as exc:
        logger.debug("custom font unavailable: %s", exc)
    _FONT_REGISTERED = True
    return font_name


def build_presentation_pdf(db: Session) -> bytes:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    settings = get_settings()
    faq_comm = get_faq(db)

    font = _ensure_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleRU",
        parent=styles["Title"],
        fontName=font,
        fontSize=18,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "BodyRU",
        parent=styles["Normal"],
        fontName=font,
        fontSize=11,
        leading=14,
        spaceAfter=8,
    )
    h2_style = ParagraphStyle(
        "H2RU",
        parent=styles["Heading2"],
        fontName=font,
        fontSize=13,
        spaceBefore=10,
        spaceAfter=6,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm)
    story: list = []

    program = settings.program_name or "ПроКомпетенции"
    story.append(Paragraph(f"Партнёрская презентация — {program}", title_style))
    story.append(
        Paragraph(
            f"Уральский федеральный университет · {ws.industry or 'IT-отрасль'} · "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            body_style,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    sections = [
        (
            "О программе",
            "ПроКомпетенции — проектное обучение студентов под кураторством преподавателей УрФУ. "
            "Компания формулирует прикладную задачу; команда студентов выполняет её в течение семестра.",
        ),
        (
            "Ценность для партнёра",
            "Пилот решения без найма, доступ к мотивированным студентам, формирование кадрового резерва. "
            "Типичная нагрузка на ментора — 1–2 часа в неделю.",
        ),
    ]
    if faq_comm and faq_comm.get("body"):
        sections.append(("FAQ", str(faq_comm["body"])[:6000]))
    else:
        sections.append(
            (
                "FAQ",
                "Готовы ответить на вопросы о формате, сроках и составе команды на коротком созвоне.",
            )
        )

    for heading, text in sections:
        story.append(Paragraph(heading, h2_style))
        for block in text.split("\n"):
            block = block.strip()
            if block:
                safe = (
                    block.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                story.append(Paragraph(safe, body_style))

    doc.build(story)
    return buf.getvalue()
