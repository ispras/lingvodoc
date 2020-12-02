"""komi_zyryan_parser

Revision ID: d7a6389ac968
Revises: bea877f1af75
Create Date: 2020-11-18 20:06:07.849196

"""

# revision identifiers, used by Alembic.
revision = 'd7a6389ac968'
down_revision = 'bea877f1af75'
branch_labels = None
depends_on = None

from alembic import op

def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2020-10-28 20:22:00.000000', 5, 1, 'Парсер коми-зырянского языка Т.Архангельского', '[]',
           'timarkh_komi_zyryan');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'timarkh_komi_zyryan';
    ''')
