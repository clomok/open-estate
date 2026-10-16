"""Timeline engine: event / playbook / playbook_step replace task + milestone

Every task and milestone row moves into `event`; the transform is
src/services/v3_upgrade.py, the same code the importer runs on a v3 backup.
The default death-of-trustor playbook is inserted so an upgraded database
starts where a fresh install does.

Downgrade is not supported, for the same reason as ledger v3: restore the
copy scripts/upgrade_db.py takes before every migration.

Revision ID: c4d8e1f2a7b5
Revises: b7e2c41f9a03
Create Date: 2026-10-15

"""
from alembic import op
import sqlalchemy as sa

from src.services import v3_upgrade
from src.services.backup_codec import row_kwargs


# revision identifiers, used by Alembic.
revision = 'c4d8e1f2a7b5'
down_revision = 'b7e2c41f9a03'
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('last_verified', sa.Date(), nullable=True),
    ]


def upgrade():
    conn = op.get_bind()
    tasks = [dict(r) for r in conn.execute(sa.text('SELECT * FROM task')).mappings()]
    milestones = [dict(r) for r in conn.execute(sa.text('SELECT * FROM milestone')).mappings()]
    events = v3_upgrade.events_from(tasks, milestones)
    playbooks, steps = v3_upgrade.default_playbook_rows()

    event = op.create_table('event',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), server_default='task', nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('date', sa.Date(), nullable=True),
    sa.Column('done_at', sa.Date(), nullable=True),
    sa.Column('assignee_id', sa.Integer(), nullable=True),
    sa.Column('phase', sa.String(length=20), server_default='now', nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('holding_id', sa.Integer(), nullable=True),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('person_id', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=120), nullable=True),
    sa.Column('repeat_every', sa.Integer(), nullable=True),
    sa.Column('repeat_unit', sa.String(length=10), nullable=True),
    *_audit_columns(),
    sa.CheckConstraint("kind IN ('task', 'deadline', 'renewal', 'review', 'milestone', 'memory')", name='ck_event_kind'),
    sa.CheckConstraint("phase IN ('now', 'planning', 'transition', 'administration')", name='ck_event_phase'),
    sa.CheckConstraint("repeat_unit IS NULL OR repeat_unit IN ('day', 'week', 'month', 'year')", name='ck_event_repeat_unit'),
    sa.CheckConstraint('repeat_every IS NULL OR repeat_every > 0', name='ck_event_repeat_every'),
    sa.ForeignKeyConstraint(['assignee_id'], ['person.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['entity_id'], ['entity.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['holding_id'], ['holding.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['person_id'], ['person.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_event_open_date', 'event', ['done_at', 'date'], unique=False)
    op.create_index('uq_event_source', 'event', ['source'], unique=True,
                    sqlite_where=sa.text('source IS NOT NULL'))

    playbook = op.create_table('playbook',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('trigger', sa.String(length=50), nullable=True),
    *_audit_columns(),
    sa.PrimaryKeyConstraint('id')
    )
    playbook_step = op.create_table('playbook_step',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('playbook_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), server_default='0', nullable=False),
    sa.Column('offset_days', sa.Integer(), server_default='0', nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('who_role', sa.String(length=50), nullable=True),
    sa.Column('instructions', sa.Text(), nullable=True),
    sa.Column('document_type', sa.String(length=100), nullable=True),
    sa.Column('kind', sa.String(length=20), server_default='task', nullable=False),
    *_audit_columns(),
    sa.ForeignKeyConstraint(['playbook_id'], ['playbook.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    for table, rows in ((event, events), (playbook, playbooks), (playbook_step, steps)):
        for row in rows:
            conn.execute(table.insert(), [row_kwargs(table, row)])

    op.drop_table('task')
    op.drop_table('milestone')


def downgrade():
    raise NotImplementedError(
        "The timeline migration cannot be downgraded in place. Restore the "
        "database copy taken by scripts/upgrade_db.py before the upgrade."
    )
