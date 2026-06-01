"""create tables

Revision ID: bc81b9cb798c
Revises: 
Create Date: 2026-05-26 11:00:46.630456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'bc81b9cb798c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('urls',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('status', sa.String(), nullable=True),
    sa.Column('pages_found', sa.Integer(), nullable=True),
    sa.Column('retries', sa.Integer(), nullable=True),
    sa.Column('error_msg', sa.Text(), nullable=True),
    sa.Column('last_crawled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('url')
    )
    op.create_table('crawled_pages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('url_id', sa.UUID(), nullable=True),
    sa.Column('page_url', sa.Text(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('body_text', sa.Text(), nullable=True),
    sa.Column('content_hash', sa.String(), nullable=True),
    sa.Column('crawled_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['url_id'], ['urls.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('crawled_pages')
    op.drop_table('urls')

