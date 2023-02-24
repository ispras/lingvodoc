"""Bashkir parsers added

Revision ID: d88f47d819e0
Revises: 9ce4f80b3438
Create Date: 2022-01-29 14:24:02.244094

"""

# revision identifiers, used by Alembic.
revision = 'd88f47d819e0'
down_revision = '9ce4f80b3438'
branch_labels = None
depends_on = None

from alembic import op

def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2021-01-29 17:28:00.000000', 9, 1, 'Парсер башкирского языка Apertium (моноязыковой)', '[]',
           'apertium_bak');
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2021-01-29 17:29:00.000000', 10, 1, 'Парсер башкирского языка Apertium (с переводом на татарский)', '[]',
           'apertium_bak_tat');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_bak';
    DELETE FROM parser WHERE method = 'apertium_bak_tat';
    ''')
