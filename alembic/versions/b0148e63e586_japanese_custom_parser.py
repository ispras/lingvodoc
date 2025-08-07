"""japanese custom parser

Revision ID: b0148e63e586
Revises: 60d1a9a5b60c
Create Date: 2025-08-05 21:09:54.728754

"""

# revision identifiers, used by Alembic.
revision = 'b0148e63e586'
down_revision = '60d1a9a5b60c'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2025-08-05 21:09:54.728754', 21, 1, 'Парсер японского языка Apertium (пользовательский)', '[]',
           'apertium_jpn_yypy22');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_jpn_yypy22';
    ''')
