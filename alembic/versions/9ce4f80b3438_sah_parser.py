"""Sah parser

Revision ID: 9ce4f80b3438
Revises: 71a35496d931
Create Date: 2022-01-21 10:49:39.751276

"""

# revision identifiers, used by Alembic.
revision = '9ce4f80b3438'
down_revision = '71a35496d931'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2021-01-21 13:52:00.000000', 8, 1, 'Парсер якутского языка Apertium (моноязыковой)', '[]',
           'apertium_sah');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_sah';
    ''')
