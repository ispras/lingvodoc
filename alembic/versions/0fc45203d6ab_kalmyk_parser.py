"""Kalmyk parser added

Revision ID: 0fc45203d6ab
Revises: 6e02e6fdf0f9
Create Date: 2024-01-11 12:20:38.119574

"""

# revision identifiers, used by Alembic.
revision = '0fc45203d6ab'
down_revision = '6e02e6fdf0f9'
branch_labels = None
depends_on = None

from alembic import op

def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2024-01-11 12:20:38', 12, 1, 'Парсер калмыцкого языка (hfst формат)', '[]',
           'hfst_kalmyk');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'hfst_kalmyk';
    ''')
