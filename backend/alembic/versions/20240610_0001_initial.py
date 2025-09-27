"""Initial schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20240610_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    account = op.create_table(
        "account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("screen_name", sa.String(), nullable=False, unique=True),
        sa.Column("rest_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_result", sa.String(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.String(), nullable=True),
    )
    op.create_index("ix_account_status", "account", ["status"])
    op.create_index("ix_account_last_checked_at", "account", ["last_checked_at"])
    op.create_index("ix_account_rest_id", "account", ["rest_id"], unique=False)
    token = op.create_table(
        "token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("login", sa.String(), nullable=False),
        sa.Column("auth_token", sa.String(), nullable=False),
        sa.Column("ct0", sa.String(), nullable=False),
        sa.Column("web_bearer", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="active"),
        sa.Column("last_429_at", sa.DateTime(), nullable=True),
        sa.Column("estimated_rps", sa.Float(), nullable=False, server_default="0.0167"),
        sa.Column("consecutive_429", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_response", sa.String(), nullable=True),
    )
    op.create_index("ix_token_login", "token", ["login"])
    op.create_index("ix_token_state", "token", ["state"])
    proxy = op.create_table(
        "proxy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("raw", sa.String(), nullable=False, unique=True),
        sa.Column("type", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("fails", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_proxy_type", "proxy", ["type"])
    op.create_table(
        "check",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=False),
        sa.Column("token_id", sa.Integer(), sa.ForeignKey("token.id"), nullable=True),
        sa.Column("proxy_id", sa.Integer(), sa.ForeignKey("proxy.id"), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body_snippet", sa.String(length=2000), nullable=True),
    )
    op.create_index("ix_check_timestamp", "check", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_check_timestamp", table_name="check")
    op.drop_table("check")
    op.drop_index("ix_proxy_type", table_name="proxy")
    op.drop_table("proxy")
    op.drop_index("ix_token_state", table_name="token")
    op.drop_index("ix_token_login", table_name="token")
    op.drop_table("token")
    op.drop_index("ix_account_rest_id", table_name="account")
    op.drop_index("ix_account_last_checked_at", table_name="account")
    op.drop_index("ix_account_status", table_name="account")
    op.drop_table("account")
