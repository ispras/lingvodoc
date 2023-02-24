"""Parsers

Revision ID: 9d40fd0124a6
Revises: 35fa6871a15b
Create Date: 2020-10-28 16:19:12.014044

"""

# revision identifiers, used by Alembic.
revision = '9d40fd0124a6'
down_revision = '35fa6871a15b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.execute('''
        CREATE TABLE public.parser (
        additional_metadata jsonb,
        created_at timestamp without time zone NOT NULL,
        object_id bigint NOT NULL,
        client_id bigint NOT NULL,
        name text NOT NULL,
        parameters jsonb,
        method text
        );
    
        CREATE TABLE public.parserresult (
        additional_metadata jsonb,
        marked_for_deletion boolean NOT NULL,
        created_at timestamp without time zone NOT NULL,
        object_id bigint NOT NULL,
        client_id bigint NOT NULL,
        entity_client_id bigint NOT NULL,
        entity_object_id bigint NOT NULL,
        parser_client_id bigint NOT NULL,
        parser_object_id bigint NOT NULL,
        arguments jsonb,
        content text
        );
    
	    INSERT INTO public.parser (additional_metadata, created_at, object_id, client_id, name, parameters, method) VALUES (null, '2020-10-28 20:19:36.000000', 1, 1, 'Парсер удмуртского языка Т.Архангельского', '[]', 'timarkh_udm');
        INSERT INTO public.parser (additional_metadata, created_at, object_id, client_id, name, parameters, method) VALUES (null, '2020-10-28 20:21:55.000000', 2, 1, 'Парсер эрзянского языка Т.Архангельского', '[]', 'timarkh_erzya');
        INSERT INTO public.parser (additional_metadata, created_at, object_id, client_id, name, parameters, method) VALUES (null, '2020-10-28 20:21:58.000000', 3, 1, 'Парсер марийского лугового языка Т.Архангельского', '[]', 'timarkh_meadow_mari');
        INSERT INTO public.parser (additional_metadata, created_at, object_id, client_id, name, parameters, method) VALUES (null, '2020-10-28 20:22:00.000000', 4, 1, 'Парсер мокшанского языка Т.Архангельского', '[]', 'timarkh_moksha');
        ''')

def downgrade():
    op.execute('''
        DROP TABLE public.parserresult;
        DROP TABLE public.parser;
        ''')

