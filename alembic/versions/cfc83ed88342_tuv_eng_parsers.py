""" tuvan and english parsers

Revision ID: cfc83ed88342
Revises: 89663388d970
Create Date: 2024-09-02 21:27:54.739095

"""

# revision identifiers, used by Alembic.
revision = 'cfc83ed88342'
down_revision = '89663388d970'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2021-10-05 20:23:00.000000', 14, 1, 'Парсер английского языка Apertium', '[]',
           'apertium_eng');
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2021-10-05 20:22:00.000000', 15, 1, 'Парсер тувинского языка Apertium', '[]',
           'apertium_tuv');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_eng';
    DELETE FROM parser WHERE method = 'apertium_tuv';
    ''')
