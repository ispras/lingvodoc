
"""Entry group optimization

Revision ID: eb70cc55b178
Revises: 2b852140e36e
Create Date: 2019-11-05 09:40:55.615947

"""


# revision identifiers, used by Alembic.
revision = 'eb70cc55b178'
down_revision = '2b852140e36e'
branch_labels = None
depends_on = None


from alembic import op
import sqlalchemy as sa


def upgrade():

    op.execute('''

        /* Gathers lexical entries linked through a specified link field. */

        create or replace function

        linked_cycle(
          entity_field_client_id BIGINT,
          entity_field_object_id BIGINT,
          publish BOOLEAN = true,
          accept BOOLEAN = true) 

        returns void as $$

        begin

          -- Gathering all entries until no unprocessed tags are left.

          while exists (
            select 1 from tag_list_a) loop

            with

            entry_id_cte as (

              insert into entry_id_table

              select
                L.client_id,
                L.object_id

              from
                lexicalentry L,
                public.entity E,
                publishingentity P

              where
                L.marked_for_deletion = false and
                E.parent_client_id = L.client_id and
                E.parent_object_id = L.object_id and
                E.field_client_id = entity_field_client_id and
                E.field_object_id = entity_field_object_id and
                E.marked_for_deletion = false and
                E.content in (
                  select * from tag_list_a) and
                P.client_id = E.client_id and
                P.object_id = E.object_id and
                (accept is null or P.accepted = accept) and
                (publish is null or P.published = publish)

              on conflict do nothing
              returning *),

            tag_cte as (

              insert into tag_table
              select distinct E.content

              from
                public.entity E,
                publishingentity P

              where
                (E.parent_client_id, E.parent_object_id) in (
                  select * from entry_id_cte) and
                E.field_client_id = entity_field_client_id and
                E.field_object_id = entity_field_object_id and
                E.marked_for_deletion = false and
                P.client_id = E.client_id and
                P.object_id = E.object_id and
                (accept is null or P.accepted = accept) and
                (publish is null or P.published = publish)

              on conflict do nothing
              returning *)
            
            insert into tag_list_b
            select * from tag_cte;

            truncate table tag_list_a;

            -- The next batch of additional tags.

            if exists (
              select 1 from tag_list_b) then

              with

              entry_id_cte as (

                insert into entry_id_table

                select
                  L.client_id,
                  L.object_id

                from
                  lexicalentry L,
                  public.entity E,
                  publishingentity P

                where
                  L.marked_for_deletion = false and
                  E.parent_client_id = L.client_id and
                  E.parent_object_id = L.object_id and
                  E.field_client_id = entity_field_client_id and
                  E.field_object_id = entity_field_object_id and
                  E.marked_for_deletion = false and
                  E.content in (
                    select * from tag_list_b) and
                  P.client_id = E.client_id and
                  P.object_id = E.object_id and
                  (accept is null or P.accepted = accept) and
                  (publish is null or P.published = publish)

                on conflict do nothing
                returning *),

              tag_cte as (

                insert into tag_table
                select distinct E.content

                from
                  public.entity E,
                  publishingentity P

                where
                  (E.parent_client_id, E.parent_object_id) in (
                    select * from entry_id_cte) and
                  E.field_client_id = entity_field_client_id and
                  E.field_object_id = entity_field_object_id and
                  E.marked_for_deletion = false and
                  P.client_id = E.client_id and
                  P.object_id = E.object_id and
                  (accept is null or P.accepted = accept) and
                  (publish is null or P.published = publish)

                on conflict do nothing
                returning *)
              
              insert into tag_list_a
              select * from tag_cte;

              truncate table tag_list_b;

            end if;

          end loop;

        end;

        $$ language plpgsql;

        ''')

    op.execute('''

        /* 
         * Like linked_cycle(), but does not join with publishingentity, so is
         * equivalent to linked_cycle(_, _, null, null), but should be faster.
         */

        create or replace function

        linked_cycle_no_publishing(
          entity_field_client_id BIGINT,
          entity_field_object_id BIGINT) 

        returns void as $$

        begin

          -- Gathering all entries until no unprocessed tags are left.

          while exists (
            select 1 from tag_list_a) loop

            with

            entry_id_cte as (

              insert into entry_id_table

              select
                L.client_id,
                L.object_id

              from
                lexicalentry L,
                public.entity E

              where
                L.marked_for_deletion = false and
                E.parent_client_id = L.client_id and
                E.parent_object_id = L.object_id and
                E.field_client_id = entity_field_client_id and
                E.field_object_id = entity_field_object_id and
                E.marked_for_deletion = false and
                E.content in (
                  select * from tag_list_a)

              on conflict do nothing
              returning *),

            tag_cte as (

              insert into tag_table

              select distinct E.content
              from public.entity E

              where
                (E.parent_client_id, E.parent_object_id) in (
                  select * from entry_id_cte) and
                E.field_client_id = entity_field_client_id and
                E.field_object_id = entity_field_object_id and
                E.marked_for_deletion = false

              on conflict do nothing
              returning *)
            
            insert into tag_list_b
            select * from tag_cte;

            truncate table tag_list_a;

            -- The next batch of additional tags.

            if exists (
              select 1 from tag_list_b) then

              with

              entry_id_cte as (

                insert into entry_id_table

                select
                  L.client_id,
                  L.object_id

                from
                  lexicalentry L,
                  public.entity E

                where
                  L.marked_for_deletion = false and
                  E.parent_client_id = L.client_id and
                  E.parent_object_id = L.object_id and
                  E.field_client_id = entity_field_client_id and
                  E.field_object_id = entity_field_object_id and
                  E.marked_for_deletion = false and
                  E.content in (
                    select * from tag_list_b)

                on conflict do nothing
                returning *),

              tag_cte as (

                insert into tag_table

                select distinct E.content
                from public.entity E

                where
                  (E.parent_client_id, E.parent_object_id) in (
                    select * from entry_id_cte) and
                  E.field_client_id = entity_field_client_id and
                  E.field_object_id = entity_field_object_id and
                  E.marked_for_deletion = false

                on conflict do nothing
                returning *)
              
              insert into tag_list_a
              select * from tag_cte;

              truncate table tag_list_b;

            end if;

          end loop;

        end;

        $$ language plpgsql;

        ''')

    op.execute('''

        /*
         * Finds a group of lexical entries linked through a specified link
         * field, starting from a given entry.
         */

        create or replace function

        linked_group(
          entity_field_client_id BIGINT,
          entity_field_object_id BIGINT,
          entry_client_id BIGINT,
          entry_object_id BIGINT,
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
         
          with
          tag_cte as (

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

    op.execute('''

        /* 
         * Like linked_group(), but does not join with publishingentity, so is
         * equivalent to linked_group(_, _, _, _, null, null), but should be
         * faster.
         */

        create or replace function

        linked_group_no_publishing(
          entity_field_client_id BIGINT,
          entity_field_object_id BIGINT,
          entry_client_id BIGINT,
          entry_object_id BIGINT,
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
         
          with
          tag_cte as (

            insert into tag_table

            select distinct E.content
            from public.entity E

            where
              E.parent_client_id = entry_client_id and
              E.parent_object_id = entry_object_id and
              E.field_client_id = entity_field_client_id and
              E.field_object_id = entity_field_object_id and
              E.marked_for_deletion = false

            on conflict do nothing
            returning *)
          
          insert into tag_list_a
          select * from tag_cte;

          -- Gathering and returning linked lexical entries.

          perform linked_cycle_no_publishing(
            entity_field_client_id,
            entity_field_object_id);

          return query
          select * from entry_id_table;

          truncate table entry_id_table;
          truncate table tag_table;

        end;

        $$ language plpgsql;

        ''')

    op.execute('''

        /*
         * Finds a group of lexical entries linked through a specified link
         * field, starting from a link tag.
         */

        create or replace function

        linked_group(
          entity_field_client_id BIGINT,
          entity_field_object_id BIGINT,
          tag TEXT,
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

          select
            L.client_id,
            L.object_id

          from
            lexicalentry L,
            public.entity E,
            publishingentity P

          where
            L.marked_for_deletion = false and
            E.parent_client_id = L.client_id and
            E.parent_object_id = L.object_id and
            E.field_client_id = entity_field_client_id and
            E.field_object_id = entity_field_object_id and
            E.marked_for_deletion = false and
            E.content = tag and
            P.client_id = E.client_id and
            P.object_id = E.object_id and
            (accept is null or P.accepted = accept) and
            (publish is null or P.published = publish)

          on conflict do nothing;

          -- Temporary table for etymological tags.

          create temporary table
          if not exists

          tag_table (
            tag TEXT primary key)

          on commit drop;

          insert into tag_table
            values (tag);

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
         
          with
          tag_cte as (

            insert into tag_table
            select distinct E.content

            from
              public.entity E,
              publishingentity P

            where
              (E.parent_client_id, E.parent_object_id) in (
                select * from entry_id_table) and
              E.field_client_id = entity_field_client_id and
              E.field_object_id = entity_field_object_id and
              E.marked_for_deletion = false and
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

    op.execute('''

        /*
         * Non-deleted text fields, used for getting etymology text info, see
         * etymology_text() and etymology_group_text().
         */

        create materialized view
        text_field_id_view as

        select
          client_id,
          object_id

        from field

        where
          data_type_translation_gist_client_id = 1 and
          data_type_translation_gist_object_id = 47 and
          marked_for_deletion = false;

        create unique index
          text_field_id_view_idx on

          text_field_id_view (
            client_id, object_id);

        ''')

    op.execute('''

        /*
         * Returns aggregated text data of an etymologically linked lexical
         * entry group.
         */

        create or replace function

        etymology_text(
          tag TEXT,
          publish BOOLEAN = true) 

        returns table (
          content TEXT) as $$

        begin

          -- Returning data of each linked lexical entry.

          return query

          select
            string_agg(E.content, '; ')

          from
            public.entity E,
            publishingentity P

          where
            (E.parent_client_id, E.parent_object_id) in (
              select * from linked_group(66, 25, tag, publish)) and
            (E.field_client_id, E.field_object_id) in (
              select * from text_field_id_view) and
            E.marked_for_deletion = false and
            E.content is not null and
            P.client_id = E.client_id and
            P.object_id = E.object_id and
            P.accepted = true and
            (publish is null or P.published = publish)

          group by (
            E.parent_client_id, E.parent_object_id);

        end;

        $$ language plpgsql;

        ''')

    op.execute('''

        /*
         * Returns aggregated text data and lexical entry ids of an
         * etymologically linked lexical entry group.
         */

        create or replace function

        etymology_group_text(
          tag TEXT,
          publish BOOLEAN = true) 

        returns table (
          client_id BIGINT,
          object_id BIGINT,
          content TEXT) as $$

        begin

          -- Returning data of each linked lexical entry.

          return query

          select
            E.parent_client_id,
            E.parent_object_id,
            string_agg(E.content, '; ')

          from
            public.entity E,
            publishingentity P

          where
            (E.parent_client_id, E.parent_object_id) in (
              select * from linked_group(66, 25, tag, publish)) and
            (E.field_client_id, E.field_object_id) in (
              select * from text_field_id_view) and
            E.marked_for_deletion = false and
            E.content is not null and
            P.client_id = E.client_id and
            P.object_id = E.object_id and
            P.accepted = true and
            (publish is null or P.published = publish)

          group by (
            E.parent_client_id, E.parent_object_id);

          truncate table entry_id_table;
          truncate table tag_table;

        end;

        $$ language plpgsql;

        ''')


def downgrade():

    op.execute(
        'drop function if exists linked_cycle(bigint, bigint, boolean, boolean);')

    op.execute(
        'drop function if exists linked_cycle_no_publishing(bigint, bigint);')

    op.execute(
        'drop function if exists linked_group(bigint, bigint, bigint, bigint, boolean, boolean);')

    op.execute(
        'drop function if exists linked_group_no_publishing(bigint, bigint, bigint, bigint, boolean, boolean);')

    op.execute(
        'drop function if exists linked_group(bigint, bigint, text, boolean, boolean);')

    op.execute(
        'drop materialized view if exists text_field_id_view;')

    op.execute(
        'drop function if exists etymology_text(text, boolean);')

    op.execute(
        'drop function if exists etymology_group_text(text, boolean);')

