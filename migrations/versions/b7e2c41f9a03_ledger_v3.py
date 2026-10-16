"""Ledger v3: holding / entity / person_role / beneficiary_designation

Replaces the asset-era schema with the v3 ledger, carrying every row across.
The data transform is src/services/v2_upgrade.py - the same code the
importer runs on an old backup file - so an upgraded database and a restored
v2 backup come out identical.

Downgrade is not supported: v3 holds facts v2 cannot (several roles per
person, add-on entities, equity, designation kinds). To go back, restore the
copy scripts/upgrade_db.py takes before every migration.

Revision ID: b7e2c41f9a03
Revises: 9bbb6e6a6bff
Create Date: 2026-10-15

"""
import json

from alembic import op
import sqlalchemy as sa

from src.services import v2_upgrade
from src.services.backup_codec import parent_first, row_kwargs


# revision identifiers, used by Alembic.
revision = 'b7e2c41f9a03'
down_revision = '9bbb6e6a6bff'
branch_labels = None
depends_on = None

# v2 table -> key in a v2 backup file, in the order the old tables are dropped
# (children first, so foreign keys stay satisfied the whole way down).
OLD_TABLES = [
    ('asset_beneficiaries', 'asset_beneficiaries'),
    ('appraisal', 'appraisals'),
    ('task', 'tasks'),
    ('property_structure', 'structures'),
    ('location_point', 'location_points'),
    ('recurring_bill', 'bills'),
    ('asset_vendor', 'vendors'),
    ('asset', 'assets'),
    ('person', 'people'),
    ('trust_profile', 'trust_profile'),
    ('milestone', 'milestones'),
]

# v3 backup key -> new table, parents first.
NEW_TABLES = [
    ('people', 'person'),
    ('person_roles', 'person_role'),
    ('entities', 'entity'),
    ('holdings', 'holding'),
    ('valuations', 'valuation'),
    ('beneficiary_designations', 'beneficiary_designation'),
    ('tasks', 'task'),
    ('milestones', 'milestone'),
    ('structures', 'property_structure'),
    ('location_points', 'location_point'),
    ('bills', 'recurring_bill'),
    ('vendors', 'holding_vendor'),
]
SELF_REFERENCES = {'entities': 'parent_id', 'holdings': 'secured_by_id'}


def _read_v2(conn):
    data = {'version': '2.0 (database)'}
    for table, key in OLD_TABLES:
        rows = []
        for row in conn.execute(sa.text(f'SELECT * FROM {table}')).mappings():
            row = dict(row)
            if isinstance(row.get('attributes'), str):
                row['attributes'] = json.loads(row['attributes'] or '{}')
            rows.append(row)
        data[key] = rows
    return data


def upgrade():
    conn = op.get_bind()
    v2 = _read_v2(conn)
    v3 = v2_upgrade.convert(v2)

    for table, _ in OLD_TABLES:
        op.drop_table(table)

    tables = {}
    tables['milestone'] = op.create_table('milestone',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=100), nullable=False),
    sa.Column('date_event', sa.Date(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_completed', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    tables['person'] = op.create_table('person',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('kind', sa.String(length=20), server_default='individual', nullable=False),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('attributes', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.CheckConstraint("kind IN ('individual', 'organisation')", name='ck_person_kind'),
    sa.PrimaryKeyConstraint('id')
    )
    tables['entity'] = op.create_table('entity',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('is_root', sa.Boolean(), server_default='0', nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=True),
    sa.Column('person_id', sa.Integer(), nullable=True),
    sa.Column('date_established', sa.Date(), nullable=True),
    sa.Column('date_death_estimated', sa.Date(), nullable=True),
    sa.Column('date_death_actual', sa.Date(), nullable=True),
    sa.Column('review_frequency', sa.String(length=50), nullable=True),
    sa.Column('next_review_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('attributes', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.CheckConstraint("is_root = 0 OR kind = 'trust'", name='ck_entity_root_is_trust'),
    sa.CheckConstraint("kind IN ('trust', 'corporation', 'llc', 'retirement_account', 'individual')", name='ck_entity_kind'),
    sa.CheckConstraint('(is_root = 1 AND parent_id IS NULL) OR (is_root = 0 AND parent_id IS NOT NULL)', name='ck_entity_root_has_no_parent'),
    sa.ForeignKeyConstraint(['parent_id'], ['entity.id'], ),
    sa.ForeignKeyConstraint(['person_id'], ['person.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_entity_one_root', 'entity', ['is_root'], unique=True, sqlite_where=sa.text('is_root = 1'))
    tables['person_role'] = op.create_table('person_role',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('person_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['person_id'], ['person.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('person_id', 'role', name='uq_person_role')
    )
    tables['holding'] = op.create_table('holding',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('side', sa.String(length=10), nullable=False),
    sa.Column('type_code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('value_cents', sa.Integer(), server_default='0', nullable=False),
    sa.Column('attributes', sa.JSON(), nullable=True),
    sa.Column('ownership_pct', sa.Float(), nullable=True),
    sa.Column('secured_by_id', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.CheckConstraint("side IN ('asset', 'liability', 'equity')", name='ck_holding_side'),
    sa.CheckConstraint('ownership_pct IS NULL OR (ownership_pct >= 0 AND ownership_pct <= 100)', name='ck_holding_ownership_pct'),
    sa.CheckConstraint('value_cents >= 0', name='ck_holding_value_positive'),
    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['person.id'], ),
    sa.ForeignKeyConstraint(['secured_by_id'], ['holding.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    tables['beneficiary_designation'] = op.create_table('beneficiary_designation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('holding_id', sa.Integer(), nullable=False),
    sa.Column('person_id', sa.Integer(), nullable=False),
    sa.Column('percentage', sa.Float(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.CheckConstraint("kind IN ('trust_schedule', 'account_tod', 'will')", name='ck_designation_kind'),
    sa.CheckConstraint('percentage > 0 AND percentage <= 100', name='ck_designation_pct'),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['person_id'], ['person.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('holding_id', 'person_id', 'kind', name='uq_designation')
    )
    tables['holding_vendor'] = op.create_table('holding_vendor',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('holding_id', sa.Integer(), nullable=False),
    sa.Column('person_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=100), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['person_id'], ['person.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    tables['location_point'] = op.create_table('location_point',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('holding_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    tables['property_structure'] = op.create_table('property_structure',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('holding_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('structure_type', sa.String(length=50), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('date_built', sa.Date(), nullable=True),
    sa.Column('date_last_maintained', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    tables['recurring_bill'] = op.create_table('recurring_bill',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('holding_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('payee', sa.String(length=100), nullable=True),
    sa.Column('account_number', sa.String(length=100), nullable=True),
    sa.Column('amount_cents', sa.Integer(), server_default='0', nullable=False),
    sa.Column('frequency', sa.String(length=50), nullable=True),
    sa.Column('is_autopay', sa.Boolean(), nullable=True),
    sa.Column('next_due_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    tables['task'] = op.create_table('task',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('is_recurring', sa.Boolean(), nullable=True),
    sa.Column('holding_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    tables['valuation'] = op.create_table('valuation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('holding_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('value_cents', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('last_verified', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    for key, table_name in NEW_TABLES:
        rows = v3.get(key, [])
        if key in SELF_REFERENCES:
            rows = parent_first(rows, SELF_REFERENCES[key])
        table = tables[table_name]
        for row in rows:
            conn.execute(table.insert(), [row_kwargs(table, row)])


def downgrade():
    raise NotImplementedError(
        "Ledger v3 cannot be downgraded in place. Restore the database copy "
        "taken by scripts/upgrade_db.py before the upgrade, or restore a v2 "
        "backup file into a v2 build of the app."
    )
