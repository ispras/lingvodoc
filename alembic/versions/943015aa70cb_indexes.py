"""indexes

Revision ID: 943015aa70cb
Revises: 9e7ee952f6ae
Create Date: 2016-11-08 18:39:10.246053

"""

# revision identifiers, used by Alembic.
revision = '943015aa70cb'
down_revision = '9e7ee952f6ae'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('parent_entity_idx', 'entity', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('self_entity_idx', 'entity', ['self_client_id', 'self_object_id'], unique=False)
    op.create_index('parent_lexical_entry_idx', 'lexicalentry', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('parent_translation_atom_idx', 'translationatom', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('parent_perspective_idx', 'dictionaryperspective', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('parent_dictionary_idx', 'dictionary', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('gist_field_idx', 'field', ['translation_gist_client_id', 'translation_gist_object_id'], unique=False)
    op.create_index('gist_field_data_type_idx', 'field', ['data_type_translation_gist_client_id', 'data_type_translation_gist_object_id'], unique=False)

    pass


def downgrade():
    op.drop_index('parent_entity_idx', table_name='entity')
    op.drop_index('self_entity_idx', table_name='entity')
    op.drop_index('parent_lexical_entry_idx', table_name='lexicalentry')
    op.drop_index('parent_translation_atom_idx', table_name='translationatom')
    op.drop_index('parent_perspective_idx', table_name='dictionaryperspective')
    op.drop_index('parent_dictionary_idx', table_name='dictionary')
    op.drop_index('gist_field_idx', table_name='field')
    op.drop_index('gist_field_data_type_idx', table_name='field')
    pass
