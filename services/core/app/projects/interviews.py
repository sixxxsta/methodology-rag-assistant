from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import PartnershipCycle, Project, ProjectTeamInterview, StudentTeam
from ..profiles.service import display_name, display_names
from ..teams.service import _active_team_for_student, _norm

INTERVIEW_PENDING = "pending"
INTERVIEW_SUBMITTED = "submitted"
INTERVIEW_PASSED = "passed"
INTERVIEW_FAILED = "failed"
INTERVIEW_REJECTED = "rejected"

MIN_ANSWER_LEN = 40
PASS_SCORE = 2


def _build_questions(project: Project) -> list[str]:
    comps = [c.strip() for c in (project.competencies or "").split(",") if c.strip()]
    comp_hint = comps[0] if comps else "компетенции из ТЗ"
    return [
        f"Кратко опишите, как вы понимаете задачу проекта «{project.title}».",
        f"Какие навыки и опыт вашей команды релевантны для проекта (в т.ч. {comp_hint})?",
        "Как команда планирует распределить роли и сроки работы над проектом?",
    ]


def _get_interview_row(
    db: Session, project_id: int, team_id: int
) -> ProjectTeamInterview | None:
    return (
        db.query(ProjectTeamInterview)
        .filter(
            ProjectTeamInterview.project_id == project_id,
            ProjectTeamInterview.team_id == team_id,
        )
        .one_or_none()
    )


def _interview_dict(db: Session, row: ProjectTeamInterview | None) -> dict | None:
    if not row:
        return None
    questions: list[str] = []
    if row.questions_json:
        try:
            questions = json.loads(row.questions_json)
        except json.JSONDecodeError:
            questions = []
    answers: list[str] = []
    if row.answers_json:
        try:
            answers = json.loads(row.answers_json)
        except json.JSONDecodeError:
            answers = []
    team = db.query(StudentTeam).filter(StudentTeam.id == row.team_id).one_or_none()
    return {
        "id": row.id,
        "status": row.status,
        "score": row.score,
        "questions": questions,
        "answers": answers,
        "feedback": row.feedback,
        "curator_feedback": row.curator_feedback,
        "team_id": row.team_id,
        "team_name": team.name if team else None,
        "leader_email": row.leader_email,
        "leader_fio": display_name(db, row.leader_email),
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "passed_at": row.passed_at.isoformat() if row.passed_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


def interview_passed(db: Session, project_id: int, team_id: int) -> bool:
    row = _get_interview_row(db, project_id, team_id)
    return row is not None and row.status == INTERVIEW_PASSED


def interview_context(
    db: Session,
    project: Project,
    *,
    viewer_email: str | None,
    is_leader: bool,
    team_id: int | None,
) -> dict:
    required = bool(getattr(project, "interview_required", False))
    base = {
        "interview_required": required,
        "interview_status": None,
        "interview_questions": [],
        "interview_feedback": None,
        "can_start_interview": False,
        "can_submit_interview": False,
        "interview_passed": not required,
        "awaiting_curator_review": False,
    }
    if not required or not viewer_email or not team_id:
        return base

    row = _get_interview_row(db, project.id, team_id)
    info = _interview_dict(db, row)
    passed = row is not None and row.status == INTERVIEW_PASSED
    pending = row is not None and row.status == INTERVIEW_PENDING
    submitted = row is not None and row.status == INTERVIEW_SUBMITTED
    failed = row is not None and row.status in (INTERVIEW_FAILED, INTERVIEW_REJECTED)

    base.update(
        {
            "interview_status": row.status if row else None,
            "interview_questions": (info or {}).get("questions") or [],
            "interview_feedback": (info or {}).get("feedback") or (info or {}).get("curator_feedback"),
            "interview_passed": passed or not required,
            "awaiting_curator_review": submitted,
            "can_start_interview": bool(
                is_leader and (row is None or failed) and not passed and not submitted
            ),
            "can_submit_interview": bool(is_leader and pending),
        }
    )
    return base


def start_team_interview(db: Session, project_id: int, *, leader_email: str) -> dict:
    email = _norm(leader_email)
    team = _active_team_for_student(db, email)
    if not team or _norm(team.leader_email) != email:
        raise ValueError("собеседование проходит лидер команды")

    project = db.query(Project).filter(Project.id == project_id).one()
    if not getattr(project, "interview_required", False):
        raise ValueError("для этого проекта собеседование не требуется")

    row = _get_interview_row(db, project_id, team.id)
    if row and row.status == INTERVIEW_PASSED:
        raise ValueError("собеседование уже одобрено куратором")
    if row and row.status == INTERVIEW_SUBMITTED:
        raise ValueError("ответы на проверке у куратора")
    if row and row.status == INTERVIEW_PENDING:
        questions = json.loads(row.questions_json or "[]")
        return {"status": row.status, "questions": questions}

    questions = _build_questions(project)
    if row and row.status in (INTERVIEW_FAILED, INTERVIEW_REJECTED):
        row.status = INTERVIEW_PENDING
        row.score = None
        row.answers_json = None
        row.feedback = None
        row.curator_email = None
        row.curator_feedback = None
        row.submitted_at = None
        row.reviewed_at = None
        row.passed_at = None
        row.questions_json = json.dumps(questions, ensure_ascii=False)
        row.leader_email = email
    else:
        row = ProjectTeamInterview(
            project_id=project_id,
            team_id=team.id,
            leader_email=email,
            status=INTERVIEW_PENDING,
            questions_json=json.dumps(questions, ensure_ascii=False),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return {"status": row.status, "questions": questions}


def _evaluate_answers(questions: list[str], answers: list[str]) -> tuple[bool, int, str]:
    if len(answers) != len(questions):
        raise ValueError("ответьте на все вопросы")
    score = sum(1 for a in answers if len(a.strip()) >= MIN_ANSWER_LEN)
    passed = score >= PASS_SCORE
    if passed:
        feedback = "Ответы приняты. Ожидайте проверки куратором."
    else:
        feedback = (
            f"Недостаточно развёрнутых ответов ({score}/{len(questions)}). "
            f"Каждый ответ — минимум {MIN_ANSWER_LEN} символов. Попробуйте снова."
        )
    return passed, score, feedback


def submit_team_interview(
    db: Session,
    project_id: int,
    *,
    leader_email: str,
    answers: list[str],
) -> dict:
    email = _norm(leader_email)
    team = _active_team_for_student(db, email)
    if not team or _norm(team.leader_email) != email:
        raise ValueError("ответы принимает лидер команды")

    project = db.query(Project).filter(Project.id == project_id).one()
    if not getattr(project, "interview_required", False):
        raise ValueError("для этого проекта собеседование не требуется")

    row = _get_interview_row(db, project_id, team.id)
    if not row or row.status != INTERVIEW_PENDING:
        raise ValueError("сначала начните собеседование")

    questions = json.loads(row.questions_json or "[]")
    quality_ok, score, feedback = _evaluate_answers(questions, answers)
    row.answers_json = json.dumps(answers, ensure_ascii=False)
    row.score = score
    row.feedback = feedback
    if quality_ok:
        row.status = INTERVIEW_SUBMITTED
        row.submitted_at = datetime.now(timezone.utc)
    else:
        row.status = INTERVIEW_FAILED
    db.commit()
    db.refresh(row)
    return {
        "status": row.status,
        "score": score,
        "passed": False,
        "awaiting_curator": quality_ok,
        "feedback": feedback,
    }


def list_pending_interviews(db: Session, cycle_id: int) -> list[dict]:
    rows = (
        db.query(ProjectTeamInterview, Project, StudentTeam)
        .join(Project, ProjectTeamInterview.project_id == Project.id)
        .join(StudentTeam, ProjectTeamInterview.team_id == StudentTeam.id)
        .filter(
            Project.cycle_id == cycle_id,
            ProjectTeamInterview.status == INTERVIEW_SUBMITTED,
        )
        .order_by(ProjectTeamInterview.submitted_at.asc())
        .all()
    )
    emails = [iv.leader_email for iv, _, _ in rows]
    names = display_names(db, emails)
    out: list[dict] = []
    for iv, proj, team in rows:
        item = _interview_dict(db, iv) or {}
        item.update(
            {
                "project_id": proj.id,
                "project_title": proj.title,
                "team_name": team.name or f"Команда #{team.id}",
                "leader_fio": names.get(_norm(iv.leader_email), iv.leader_email),
            }
        )
        out.append(item)
    return out


def approve_team_interview(
    db: Session,
    interview_id: int,
    *,
    actor_email: str,
    feedback: str | None = None,
) -> dict:
    row = db.query(ProjectTeamInterview).filter(ProjectTeamInterview.id == interview_id).one()
    if row.status != INTERVIEW_SUBMITTED:
        raise ValueError("собеседование не ожидает проверки")
    now = datetime.now(timezone.utc)
    row.status = INTERVIEW_PASSED
    row.curator_email = _norm(actor_email)
    row.curator_feedback = (feedback or "Одобрено куратором").strip()
    row.reviewed_at = now
    row.passed_at = now
    db.commit()
    db.refresh(row)
    return _interview_dict(db, row) or {}


def reject_team_interview(
    db: Session,
    interview_id: int,
    *,
    actor_email: str,
    feedback: str,
) -> dict:
    row = db.query(ProjectTeamInterview).filter(ProjectTeamInterview.id == interview_id).one()
    if row.status != INTERVIEW_SUBMITTED:
        raise ValueError("собеседование не ожидает проверки")
    msg = feedback.strip()
    if not msg:
        raise ValueError("укажите комментарий для команды")
    row.status = INTERVIEW_REJECTED
    row.curator_email = _norm(actor_email)
    row.curator_feedback = msg
    row.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _interview_dict(db, row) or {}
