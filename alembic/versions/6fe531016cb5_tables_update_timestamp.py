"""tables_update_timestamp

Revision ID: 6fe531016cb5
Revises: b0148e63e586
Create Date: 2025-11-12 17:41:04.736371

"""

# revision identifiers, used by Alembic.
revision = '6fe531016cb5'
down_revision = 'b0148e63e586'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from pdb import set_trace as A


def tables():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    return inspector.get_table_names()


def upgrade():

    for table in tables():
        if table == 'parserresult':
            continue

        op.execute(f'''
            -- Adding 'updated_at' column
            ALTER TABLE public.{table} 
              ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT TIMEZONE('UTC', NOW());

            -- Trigger which will call the function before an update is performed on 'updated_at'
            CREATE TRIGGER {table}_set_timestamp
              BEFORE UPDATE ON public.{table}
              FOR EACH ROW
              EXECUTE PROCEDURE trigger_set_timestamp();
        ''')


def downgrade():

    for table in tables():
        if table == 'parserresult':
            continue

        op.execute(f'''
            -- Removing trigger
            DROP TRIGGER set_timestamp ON public.{table};
    
            -- Removing 'updated_at'
            ALTER TABLE public.{table}
              DROP COLUMN updated_at;
        ''')
