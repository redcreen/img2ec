"""source_image.scene_id — per-image template override

Revision ID: f4a91b2c7e83
Revises: e2f8b9d04c12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a91b2c7e83"
down_revision: Union[str, Sequence[str], None] = "e2f8b9d04c12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("source_images") as batch_op:
        batch_op.add_column(sa.Column("scene_id", sa.String(length=36), nullable=True))
        # ON DELETE SET NULL；命名约束让 batch mode 干净
        batch_op.create_foreign_key(
            "fk_source_image_scene", "scenes",
            ["scene_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("source_images") as batch_op:
        batch_op.drop_constraint("fk_source_image_scene", type_="foreignkey")
        batch_op.drop_column("scene_id")
