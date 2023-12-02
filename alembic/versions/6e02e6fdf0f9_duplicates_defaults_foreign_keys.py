"""Duplicates, defaults, foreign keys

Revision ID: 6e02e6fdf0f9
Revises: 2fd520393cc5
create date: 2023-06-28 14:53:03.839379

"""

# revision identifiers, used by Alembic.
revision = '6e02e6fdf0f9'
down_revision = 'b1210b50fb70'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():

    # Adding not null constraints where they should be.

    op.execute('''

        ALTER TABLE dictionary ALTER COLUMN parent_client_id SET NOT NULL;
        ALTER TABLE dictionary ALTER COLUMN parent_object_id SET NOT NULL;

        ALTER TABLE dictionaryperspective ALTER COLUMN parent_client_id SET NOT NULL;
        ALTER TABLE dictionaryperspective ALTER COLUMN parent_object_id SET NOT NULL;

        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN parent_client_id SET NOT NULL;
        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN parent_object_id SET NOT NULL;

        ALTER TABLE public.entity ALTER COLUMN parent_client_id SET NOT NULL;
        ALTER TABLE public.entity ALTER COLUMN parent_object_id SET NOT NULL;

        ALTER TABLE lexicalentry ALTER COLUMN parent_client_id SET NOT NULL;
        ALTER TABLE lexicalentry ALTER COLUMN parent_object_id SET NOT NULL;

        ALTER TABLE translationatom ALTER COLUMN parent_client_id SET NOT NULL;
        ALTER TABLE translationatom ALTER COLUMN parent_object_id SET NOT NULL;

        ALTER TABLE unstructured_data ALTER COLUMN client_id SET NOT NULL;

        ALTER TABLE userblobs ALTER COLUMN user_id SET NOT NULL;

        ''')

    # Adding default values where it makes sense.

    op.execute('''

        ALTER TABLE basegroup ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE basegroup ALTER COLUMN dictionary_default SET DEFAULT false;
        ALTER TABLE basegroup ALTER COLUMN perspective_default SET DEFAULT false;

        ALTER TABLE client ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE client ALTER COLUMN is_browser_client SET DEFAULT true;
        ALTER TABLE client ALTER COLUMN counter SET DEFAULT 1;

        ALTER TABLE dictionary ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE dictionary ALTER COLUMN marked_for_deletion SET DEFAULT false;
        ALTER TABLE dictionary ALTER COLUMN category SET DEFAULT 0;
        ALTER TABLE dictionary ALTER COLUMN domain SET DEFAULT 0;

        ALTER TABLE dictionaryperspective ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE dictionaryperspective ALTER COLUMN marked_for_deletion SET DEFAULT false;
        ALTER TABLE dictionaryperspective ALTER COLUMN is_template SET DEFAULT false;

        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE email ALTER COLUMN created_at SET DEFAULT timezone('utc', now());

        ALTER TABLE entity ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE entity ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE field ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE field ALTER COLUMN marked_for_deletion SET DEFAULT false;
        ALTER TABLE field ALTER COLUMN is_translatable SET DEFAULT false;

        ALTER TABLE public.grant ALTER COLUMN created_at SET DEFAULT timezone('utc', now());

        ALTER TABLE public.group ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE public.group ALTER COLUMN id SET DEFAULT gen_random_uuid();
        ALTER TABLE public.group ALTER COLUMN subject_override SET DEFAULT false;

        ALTER TABLE language ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE language ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE lexicalentry ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE lexicalentry ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE locale ALTER COLUMN created_at SET DEFAULT timezone('utc', now());

        ALTER TABLE objecttoc ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE organization ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE organization ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE parser ALTER COLUMN created_at SET DEFAULT timezone('utc', now());

        ALTER TABLE parserresult ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE parserresult ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE passhash ALTER COLUMN created_at SET DEFAULT timezone('utc', now());

        ALTER TABLE publishingentity ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE publishingentity ALTER COLUMN published SET DEFAULT false;
        ALTER TABLE publishingentity ALTER COLUMN accepted SET DEFAULT false;

        ALTER TABLE translationatom ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE translationatom ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE translationgist ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE translationgist ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE unstructured_data ALTER COLUMN created_at SET DEFAULT timezone('utc', now());

        ALTER TABLE public.user ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE public.user ALTER COLUMN default_locale_id SET DEFAULT 2;
        ALTER TABLE public.user ALTER COLUMN is_active SET DEFAULT false;

        ALTER TABLE userblobs ALTER COLUMN created_at SET DEFAULT timezone('utc', now());
        ALTER TABLE userblobs ALTER COLUMN marked_for_deletion SET DEFAULT false;

        ALTER TABLE userrequest ALTER COLUMN created_at SET DEFAULT timezone('utc', now());

        ''')

    # Adding missing foreign key constraints, in particular to client ids, where needed.

    op.execute('''

        ALTER TABLE dictionary ADD CONSTRAINT dictionary_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE dictionaryperspective ADD CONSTRAINT dictionaryperspective_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE dictionaryperspectivetofield ADD CONSTRAINT dictionaryperspectivetofield_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE dictionaryperspectivetofield
          ADD CONSTRAINT dictionaryperspectivetofield_link_id_fkey
          FOREIGN KEY (link_client_id, link_object_id)
          REFERENCES dictionaryperspective (client_id, object_id);

        ALTER TABLE public.entity ADD CONSTRAINT entity_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE public.entity
          ADD CONSTRAINT entity_link_id_fkey
          FOREIGN KEY (link_client_id, link_object_id)
          REFERENCES lexicalentry (client_id, object_id);

        ALTER TABLE field ADD CONSTRAINT field_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE public.grant
          ADD CONSTRAINT grant_issuer_translation_gist_id_fkey
          FOREIGN KEY (issuer_translation_gist_client_id, issuer_translation_gist_object_id)
          REFERENCES translationgist (client_id, object_id);

        ALTER TABLE public.group
          ADD CONSTRAINT group_subject_id_fkey
          FOREIGN KEY (subject_client_id, subject_object_id)
          REFERENCES objecttoc (client_id, object_id);

        ALTER TABLE language ADD CONSTRAINT language_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE lexicalentry ADD CONSTRAINT lexicalentry_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE objecttoc ADD CONSTRAINT objecttoc_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE parser ADD CONSTRAINT parser_pkey
          PRIMARY KEY (client_id, object_id);

        ALTER TABLE parser ADD CONSTRAINT parser_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE parserresult ADD CONSTRAINT parserresult_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE parserresult
          ADD CONSTRAINT parserresult_entity_id_fkey
          FOREIGN KEY (entity_client_id, entity_object_id)
          REFERENCES public.entity (client_id, object_id);

        ALTER TABLE parserresult
          ADD CONSTRAINT parserresult_parser_id_fkey
          FOREIGN KEY (parser_client_id, parser_object_id)
          REFERENCES parser (client_id, object_id);

        ALTER TABLE translationatom ADD CONSTRAINT translationatom_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE translationgist ADD CONSTRAINT translationgist_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE unstructured_data ADD CONSTRAINT unstructured_data_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ALTER TABLE userblobs ADD CONSTRAINT userblobs_client_id_fkey
          FOREIGN KEY (client_id) REFERENCES client (id);

        ''')

    # Removing duplicates from user_to_group_association and other two permission relations.
    #
    # Adding unique constaint indices which, as testing had shown, could incidentally help with common
    # ACL queries.

    op.execute('''

        LOCK TABLE user_to_group_association;

        WITH

          info AS (
            SELECT
              ctid,
              row_number() OVER (PARTITION BY user_id, group_id)
            FROM
              user_to_group_association)
  
          DELETE FROM
          user_to_group_association
          WHERE
          ctid IN (
            SELECT ctid FROM info WHERE row_number > 1);

        CREATE UNIQUE INDEX user_to_group_association_unique_idx
          ON user_to_group_association (user_id, group_id);

        LOCK TABLE user_to_organization_association;

        WITH

          info AS (
            SELECT
              ctid,
              row_number() OVER (PARTITION BY user_id, organization_id)
            FROM
              user_to_organization_association)
  
          DELETE FROM
          user_to_organization_association
          WHERE
          ctid IN (
            SELECT ctid FROM info WHERE row_number > 1);

        CREATE UNIQUE INDEX user_to_organization_association_unique_idx
          ON user_to_organization_association (user_id, organization_id);

        LOCK TABLE organization_to_group_association;

        WITH

          info AS (
            SELECT
              ctid,
              row_number() OVER (PARTITION BY organization_id, group_id)
            FROM
              organization_to_group_association)
  
          DELETE FROM
          organization_to_group_association
          WHERE
          ctid IN (
            SELECT ctid FROM info WHERE row_number > 1);

        CREATE UNIQUE INDEX organization_to_group_association_unique_idx
          ON organization_to_group_association (organization_id, group_id);

        ''')


def downgrade():

    op.execute('''

        ALTER TABLE dictionary ALTER COLUMN parent_client_id DROP NOT NULL;
        ALTER TABLE dictionary ALTER COLUMN parent_object_id DROP NOT NULL;

        ALTER TABLE dictionaryperspective ALTER COLUMN parent_client_id DROP NOT NULL;
        ALTER TABLE dictionaryperspective ALTER COLUMN parent_object_id DROP NOT NULL;

        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN parent_client_id DROP NOT NULL;
        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN parent_object_id DROP NOT NULL;

        ALTER TABLE public.entity ALTER COLUMN parent_client_id DROP NOT NULL;
        ALTER TABLE public.entity ALTER COLUMN parent_object_id DROP NOT NULL;

        ALTER TABLE lexicalentry ALTER COLUMN parent_client_id DROP NOT NULL;
        ALTER TABLE lexicalentry ALTER COLUMN parent_object_id DROP NOT NULL;

        ALTER TABLE translationatom ALTER COLUMN parent_client_id DROP NOT NULL;
        ALTER TABLE translationatom ALTER COLUMN parent_object_id DROP NOT NULL;

        ALTER TABLE unstructured_data ALTER COLUMN client_id DROP NOT NULL;

        ALTER TABLE userblobs ALTER COLUMN user_id DROP NOT NULL;

        ALTER TABLE basegroup ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE basegroup ALTER COLUMN dictionary_default DROP DEFAULT;
        ALTER TABLE basegroup ALTER COLUMN perspective_default DROP DEFAULT;

        ALTER TABLE client ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE client ALTER COLUMN is_browser_client DROP DEFAULT;
        ALTER TABLE client ALTER COLUMN counter DROP DEFAULT;

        ALTER TABLE dictionary ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE dictionary ALTER COLUMN marked_for_deletion DROP DEFAULT;
        ALTER TABLE dictionary ALTER COLUMN category DROP DEFAULT;
        ALTER TABLE dictionary ALTER COLUMN domain DROP DEFAULT;

        ALTER TABLE dictionaryperspective ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE dictionaryperspective ALTER COLUMN marked_for_deletion DROP DEFAULT;
        ALTER TABLE dictionaryperspective ALTER COLUMN is_template DROP DEFAULT;

        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE dictionaryperspectivetofield ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE email ALTER COLUMN created_at DROP DEFAULT;

        ALTER TABLE entity ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE entity ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE field ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE field ALTER COLUMN marked_for_deletion DROP DEFAULT;
        ALTER TABLE field ALTER COLUMN is_translatable DROP DEFAULT;

        ALTER TABLE public.grant ALTER COLUMN created_at DROP DEFAULT;

        ALTER TABLE public.group ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE public.group ALTER COLUMN id DROP DEFAULT;
        ALTER TABLE public.group ALTER COLUMN subject_override DROP DEFAULT;

        ALTER TABLE language ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE language ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE lexicalentry ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE lexicalentry ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE locale ALTER COLUMN created_at DROP DEFAULT;

        ALTER TABLE objecttoc ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE organization ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE organization ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE parser ALTER COLUMN created_at DROP DEFAULT;

        ALTER TABLE parserresult ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE parserresult ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE passhash ALTER COLUMN created_at DROP DEFAULT;

        ALTER TABLE publishingentity ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE publishingentity ALTER COLUMN published DROP DEFAULT;
        ALTER TABLE publishingentity ALTER COLUMN accepted DROP DEFAULT;

        ALTER TABLE translationatom ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE translationatom ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE translationgist ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE translationgist ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE unstructured_data ALTER COLUMN created_at DROP DEFAULT;

        ALTER TABLE public.user ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE public.user ALTER COLUMN default_locale_id DROP DEFAULT;
        ALTER TABLE public.user ALTER COLUMN is_active DROP DEFAULT;

        ALTER TABLE userblobs ALTER COLUMN created_at DROP DEFAULT;
        ALTER TABLE userblobs ALTER COLUMN marked_for_deletion DROP DEFAULT;

        ALTER TABLE userrequest ALTER COLUMN created_at DROP DEFAULT;

        ALTER TABLE dictionary DROP CONSTRAINT dictionary_client_id_fkey;
        ALTER TABLE dictionaryperspective DROP CONSTRAINT dictionaryperspective_client_id_fkey;
        ALTER TABLE dictionaryperspectivetofield DROP CONSTRAINT dictionaryperspectivetofield_client_id_fkey;
        ALTER TABLE dictionaryperspectivetofield DROP CONSTRAINT dictionaryperspectivetofield_link_id_fkey;
        ALTER TABLE public.entity DROP CONSTRAINT entity_client_id_fkey;
        ALTER TABLE public.entity DROP CONSTRAINT entity_link_id_fkey;
        ALTER TABLE field DROP CONSTRAINT field_client_id_fkey;
        ALTER TABLE public.grant DROP CONSTRAINT grant_issuer_translation_gist_id_fkey;
        ALTER TABLE public.group DROP CONSTRAINT group_subject_id_fkey;
        ALTER TABLE language DROP CONSTRAINT language_client_id_fkey;
        ALTER TABLE lexicalentry DROP CONSTRAINT lexicalentry_client_id_fkey;
        ALTER TABLE objecttoc DROP CONSTRAINT objecttoc_client_id_fkey;

        ALTER TABLE parserresult DROP CONSTRAINT parserresult_client_id_fkey;
        ALTER TABLE parserresult DROP CONSTRAINT parserresult_entity_id_fkey;
        ALTER TABLE parserresult DROP CONSTRAINT parserresult_parser_id_fkey;

        ALTER TABLE parser DROP CONSTRAINT parser_pkey;
        ALTER TABLE parser DROP CONSTRAINT parser_client_id_fkey;

        ALTER TABLE translationatom DROP CONSTRAINT translationatom_client_id_fkey;
        ALTER TABLE translationgist DROP CONSTRAINT translationgist_client_id_fkey;
        ALTER TABLE unstructured_data DROP CONSTRAINT unstructured_data_client_id_fkey;
        ALTER TABLE userblobs DROP CONSTRAINT userblobs_client_id_fkey;

        DROP INDEX user_to_group_association_unique_idx;
        DROP INDEX user_to_organization_association_unique_idx;
        DROP INDEX organization_to_group_association_unique_idx;

        ''')

