"""armenian locale

Revision ID: a1b2c3d4e5f6
Revises: 6fe531016cb5
Create Date: 2026-11-03 12:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '6fe531016cb5'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    DO $$
    DECLARE
        loc_id BIGINT;
    BEGIN
        SELECT COALESCE(MAX(id), 0) + 1 INTO loc_id FROM locale;
        INSERT INTO public.locale(id, shortcut, intl_name)
        VALUES (loc_id, 'hy', 'Armenian (Հայերեն)');
    END $$;
    ''')


def downgrade():
    op.execute('''
    DELETE FROM locale WHERE shortcut = 'hy';
    ''')
