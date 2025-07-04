"""entry group from date

Revision ID: 6fcf195ab3a5
Revises: f3a89eb0becc
Create Date: 2025-07-02 18:33:20.711287

"""

# revision identifiers, used by Alembic.
revision = '6fcf195ab3a5'
down_revision = 'f3a89eb0becc'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        /*
         * Finds a group of lexical entries linked through a specified link
         * field, starting from a given entry and linked after given date.
         */

        create or replace function

        linked_group(
          entity_field_client_id BIGINT,
          entity_field_object_id BIGINT,
          entry_client_id BIGINT,
          entry_object_id BIGINT,
          start_date TIMESTAMP,
          publish BOOLEAN = true,
          accept BOOLEAN = true)

        returns table (
          client_id BIGINT,
          object_id BIGINT) as $$

        begin

          -- Temporary table for lexical entry ids.

          create temporary table
          if not exists

          entry_id_table (
            client_id BIGINT,
            object_id BIGINT,
            primary key (client_id, object_id))

          on commit drop;

          insert into entry_id_table
            values (entry_client_id, entry_object_id);

          -- Temporary table for etymological tags.

          create temporary table
          if not exists

          tag_table (
            tag TEXT primary key)

          on commit drop;

          -- Temporary tables for tags to be processed.

          create temporary table
          if not exists

          tag_list_a (
            tag TEXT)

          on commit drop;

          create temporary table
          if not exists

          tag_list_b (
            tag TEXT)

          on commit drop;

          -- Initial batch of additional tags.

          with tag_cte as (

            insert into tag_table
            select distinct E.content

            from
              public.entity E,
              publishingentity P

            where
              E.parent_client_id = entry_client_id and
              E.parent_object_id = entry_object_id and
              E.field_client_id = entity_field_client_id and
              E.field_object_id = entity_field_object_id and
              E.marked_for_deletion = false and
              E.created_at > start_date and
              P.client_id = E.client_id and
              P.object_id = E.object_id and
              (accept is null or P.accepted = accept) and
              (publish is null or P.published = publish)

            on conflict do nothing
            returning *)

          insert into tag_list_a
          select * from tag_cte;

          -- Gathering and returning linked lexical entries.

          perform linked_cycle(
            entity_field_client_id,
            entity_field_object_id,
            publish,
            accept);

          return query
          select * from entry_id_table;

          truncate table entry_id_table;
          truncate table tag_table;

        end;

        $$ language plpgsql;

        ''')

def downgrade():
    op.execute(
        'drop function if exists linked_group(bigint, bigint, bigint, bigint, timestamp, boolean, boolean);')
