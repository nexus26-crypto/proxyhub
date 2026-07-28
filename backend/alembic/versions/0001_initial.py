"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(128), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "proxies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer, nullable=False),
        sa.Column("username", sa.String(128), nullable=True),
        sa.Column("password", sa.String(128), nullable=True),
        sa.Column("country", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("asn", sa.String(64), nullable=True),
        sa.Column("type", sa.String(20), server_default="http"),
        sa.Column("status", sa.String(20), server_default="testing"),
        sa.Column("score", sa.Float, server_default="0"),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("fail_count", sa.Integer, server_default="0"),
        sa.Column("last_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_proxies_host", "proxies", ["host"])
    op.create_index("ix_proxies_status", "proxies", ["status"])

    op.create_table(
        "proxy_check_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("proxy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proxies.id", ondelete="CASCADE")),
        sa.Column("success", sa.Boolean, server_default=sa.false()),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("message", sa.String(255), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), server_default="offline"),
        sa.Column("proxy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proxies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cpu_usage", sa.Float, server_default="0"),
        sa.Column("ram_usage_mb", sa.Float, server_default="0"),
        sa.Column("requests_count", sa.Integer, server_default="0"),
        sa.Column("errors_count", sa.Integer, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workers_status", "workers", ["status"])

    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="queued"),
        sa.Column("priority", sa.String(20), server_default="normal"),
        sa.Column("payload", sa.JSON, server_default="{}"),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proxy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proxies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("retries", sa.Integer, server_default="0"),
        sa.Column("max_retries", sa.Integer, server_default="3"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("level", sa.String(20), server_default="info"),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("proxy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("proxies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_logs_level", "logs", ["level"])
    op.create_index("ix_logs_created_at", "logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("logs")
    op.drop_table("jobs")
    op.drop_table("workers")
    op.drop_table("proxy_check_history")
    op.drop_table("proxies")
    op.drop_table("users")
