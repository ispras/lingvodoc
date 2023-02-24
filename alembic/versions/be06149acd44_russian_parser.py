"""Russian parser

Revision ID: be06149acd44
Revises: 442dd93eb35c
Create Date: 2022-12-24 11:32:18.420744

"""

# revision identifiers, used by Alembic.
revision = 'be06149acd44'
down_revision = '442dd93eb35c'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        INSERT
        INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)

        VALUES(
            null, '2022-12-24 12:31:00.000000', 11, 1,
            'Парсер русского языка Apertium (моноязыковой)',
            '[]', 'apertium_rus');

    ''')


def downgrade():

    op.execute('''

        DELETE FROM parser WHERE method = 'apertium_rus';

    ''')

