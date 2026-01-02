"""Expand Real Estate

Revision ID: 3a8b9c2d1e4f
Revises: 05b4f007a9f9
Create Date: 2026-01-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3a8b9c2d1e4f'
down_revision = '05b4f007a9f9'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Asset Vendors
    op.create_table('asset_vendor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=100), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], ),
        sa.ForeignKeyConstraint(['person_id'], ['person.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Location Points (Pins)
    op.create_table('location_point',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Property Structures (Accommodations)
    op.create_table('property_structure',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('structure_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('date_built', sa.Date(), nullable=True),
        sa.Column('date_last_maintained', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. Recurring Bills
    op.create_table('recurring_bill',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('payee', sa.String(length=100), nullable=True),
        sa.Column('amount_estimated', sa.Float(), nullable=True),
        sa.Column('frequency', sa.String(length=50), nullable=True),
        sa.Column('is_autopay', sa.Boolean(), nullable=True),
        sa.Column('next_due_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['asset.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('recurring_bill')
    op.drop_table('property_structure')
    op.drop_table('location_point')
    op.drop_table('asset_vendor')