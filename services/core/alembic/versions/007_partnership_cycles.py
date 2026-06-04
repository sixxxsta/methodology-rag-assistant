"""007 — partnership cycles (repeatable phase runs)

Revision ID: 007_partnership_cycles
Revises: 006_backlog_features
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_partnership_cycles"
down_revision: Union[str, None] = "006_backlog_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "partnership_cycles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active"),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_partnership_cycles_workspace_id", "partnership_cycles", ["workspace_id"])

    for table in (
        "companies",
        "competencies",
        "vacancies",
        "projects",
        "communication_outcomes",
        "strategy_patterns",
        "escalations",
    ):
        op.add_column(table, sa.Column("cycle_id", sa.Integer(), nullable=True))
        op.create_index(f"ix_{table}_cycle_id", table, ["cycle_id"])

    op.add_column("phase_runs", sa.Column("cycle_id", sa.Integer(), nullable=True))

    conn = op.get_bind()
    workspaces = conn.execute(sa.text("SELECT id, industry FROM workspaces")).fetchall()
    for ws_id, industry in workspaces:
        res = conn.execute(
            sa.text(
                "INSERT INTO partnership_cycles (workspace_id, name, industry, status, created_by) "
                "VALUES (:ws, :name, :ind, 'active', 'migration') RETURNING id"
            ),
            {"ws": ws_id, "name": "Цикл 1", "ind": industry},
        )
        cycle_id = res.scalar_one()
        for table in (
            "companies",
            "competencies",
            "vacancies",
            "projects",
            "communication_outcomes",
            "strategy_patterns",
        ):
            conn.execute(
                sa.text(f"UPDATE {table} SET cycle_id = :cid WHERE workspace_id = :ws"),
                {"cid": cycle_id, "ws": ws_id},
            )
        conn.execute(
            sa.text("UPDATE escalations SET cycle_id = :cid WHERE workspace_id = :ws"),
            {"cid": cycle_id, "ws": ws_id},
        )
        old_phases = conn.execute(
            sa.text("SELECT phase_key, status, progress_pct, notes FROM phase_runs WHERE workspace_id = :ws"),
            {"ws": ws_id},
        ).fetchall()
        if old_phases:
            for phase_key, status, progress_pct, notes in old_phases:
                conn.execute(
                    sa.text(
                        "INSERT INTO phase_runs (cycle_id, phase_key, status, progress_pct, notes) "
                        "VALUES (:cid, :pk, :st, :pp, :nt)"
                    ),
                    {
                        "cid": cycle_id,
                        "pk": phase_key,
                        "st": status,
                        "pp": progress_pct,
                        "nt": notes,
                    },
                )
        else:
            for pk, st, pp in (
                ("industry_analysis", "active", 5),
                ("company_scoring", "locked", 0),
                ("communication", "locked", 0),
                ("outreach", "locked", 0),
                ("projects", "locked", 0),
            ):
                conn.execute(
                    sa.text(
                        "INSERT INTO phase_runs (cycle_id, phase_key, status, progress_pct) "
                        "VALUES (:cid, :pk, :st, :pp)"
                    ),
                    {"cid": cycle_id, "pk": pk, "st": st, "pp": pp},
                )

    op.drop_constraint("phase_runs_workspace_id_fkey", "phase_runs", type_="foreignkey")
    op.drop_column("phase_runs", "workspace_id")

    for table in (
        "companies",
        "competencies",
        "vacancies",
        "projects",
        "communication_outcomes",
        "strategy_patterns",
    ):
        op.alter_column(table, "cycle_id", nullable=False)
        op.create_foreign_key(
            f"{table}_cycle_id_fkey",
            table,
            "partnership_cycles",
            ["cycle_id"],
            ["id"],
        )

    op.create_foreign_key(
        "escalations_cycle_id_fkey",
        "escalations",
        "partnership_cycles",
        ["cycle_id"],
        ["id"],
    )
    op.alter_column("phase_runs", "cycle_id", nullable=False)
    op.create_foreign_key(
        "phase_runs_cycle_id_fkey",
        "phase_runs",
        "partnership_cycles",
        ["cycle_id"],
        ["id"],
    )


def downgrade() -> None:
    op.add_column("phase_runs", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.drop_constraint("phase_runs_cycle_id_fkey", "phase_runs", type_="foreignkey")
    op.drop_column("phase_runs", "cycle_id")

    for table in (
        "companies",
        "competencies",
        "vacancies",
        "projects",
        "communication_outcomes",
        "strategy_patterns",
        "escalations",
    ):
        op.drop_constraint(f"{table}_cycle_id_fkey", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_cycle_id", table=table)
        op.drop_column(table, "cycle_id")

    op.drop_index("ix_partnership_cycles_workspace_id", table_name="partnership_cycles")
    op.drop_table("partnership_cycles")
