from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import UserProfile


def _norm(email: str | None) -> str:
    return (email or "").strip().lower()


def fix_mojibake(value: str) -> str:
    """Repair UTF-8 Cyrillic stored as Latin-1 mojibake (Ð—Ð¸Ð½Ð¾Ð²...)."""
    text = (value or "").strip()
    if not text or "Ð" not in text and "Ñ" not in text:
        return text
    try:
        fixed = text.encode("latin-1").decode("utf-8")
        if any("\u0400" <= c <= "\u04FF" for c in fixed):
            return fixed.strip()
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return text


def upsert_profile(
    db: Session,
    *,
    email: str,
    fio: str,
    role: str = "student",
) -> UserProfile:
    email_n = _norm(email)
    fio_clean = fix_mojibake((fio or "").strip())
    row = db.query(UserProfile).filter(UserProfile.email == email_n).one_or_none()
    if row:
        if fio_clean:
            row.fio = fio_clean
        elif row.fio.strip():
            row.fio = fix_mojibake(row.fio.strip())
        if role:
            row.role = role
    else:
        row = UserProfile(
            email=email_n,
            fio=fio_clean or email_n,
            role=role or "student",
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def display_name(db: Session, email: str | None) -> str | None:
    email_n = _norm(email)
    if not email_n:
        return None
    row = db.query(UserProfile).filter(UserProfile.email == email_n).one_or_none()
    if row and row.fio.strip():
        return fix_mojibake(row.fio.strip())
    return email_n


def display_names(db: Session, emails: list[str]) -> dict[str, str]:
    normalized = {_norm(e) for e in emails if _norm(e)}
    if not normalized:
        return {}
    rows = db.query(UserProfile).filter(UserProfile.email.in_(normalized)).all()
    out = {e: e for e in normalized}
    for row in rows:
        if row.fio.strip():
            out[row.email] = fix_mojibake(row.fio.strip())
    return out
