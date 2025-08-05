"""japanese english parser

Revision ID: 60d1a9a5b60c
Revises: 6fcf195ab3a5
Create Date: 2025-07-30 16:59:22.487393

"""

# revision identifiers, used by Alembic.
revision = '60d1a9a5b60c'
down_revision = '6fcf195ab3a5'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2025-07-30 16:59:22.487393', 19, 1, 'Парсер японского языка Apertium (многоязыковой)', '[]',
           'apertium_jpn');
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2025-07-30 16:59:22.487393', 20, 1, 'Парсер японского языка Apertium (с переводом на английский)', '[]',
           'apertium_jpn_eng');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_jpn';
    DELETE FROM parser WHERE method = 'apertium_jpn_eng';
    ''')
