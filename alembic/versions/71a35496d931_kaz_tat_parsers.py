"""Kazakh and Tatar parsers

Revision ID: 71a35496d931
Revises: d15043d2cbd9
Create Date: 2021-10-05 04:34:20.845470

"""

# revision identifiers, used by Alembic.
revision = '71a35496d931'
down_revision = 'd15043d2cbd9'
branch_labels = None
depends_on = None

from alembic import op

def upgrade():
    op.execute('''
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2021-10-05 20:22:00.000000', 6, 1, 'Парсер казахского языка Apertium', '[]',
           'apertium_kaz_rus');
    INSERT INTO public.parser(additional_metadata, created_at, object_id, client_id, name, parameters, method)
    VALUES(null, '2021-10-05 20:23:00.000000', 7, 1, 'Парсер татарского языка Apertium', '[]',
           'apertium_tat_rus');
    ''')

def downgrade():
    op.execute('''
    DELETE FROM parser WHERE method = 'apertium_kaz_rus';
    DELETE FROM parser WHERE method = 'apertium_tat_rus';
    ''')
