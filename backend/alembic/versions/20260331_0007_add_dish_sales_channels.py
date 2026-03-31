from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260331_0007"
down_revision = "20260331_0006"
branch_labels = None
depends_on = None


ALL_CHANNELS_JSON = "'[\"website\", \"mobile_app\", \"telegram\", \"vk\", \"pos\"]'::json"


def upgrade() -> None:
    op.add_column(
        "dishes",
        sa.Column(
            "available_channels",
            sa.JSON(),
            nullable=False,
            server_default=sa.text(ALL_CHANNELS_JSON),
        ),
    )


def downgrade() -> None:
    op.drop_column("dishes", "available_channels")
