"""Added more indexes

Revision ID: 4eaaa494e36
Revises: 479841e119f
Create Date: 2015-12-01 16:53:27.562361

"""

# revision identifiers, used by Alembic.
revision = '4eaaa494e36'
down_revision = '479841e119f'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_index('pl2e_parent_idx', 'publishleveltwoentity', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('pl2e_entity_type_idx', 'publishleveltwoentity', ['entity_type'], unique=False)
    op.create_index('pl2e_entity_idx', 'publishleveltwoentity', ['entity_client_id', 'entity_object_id'], unique=False)
    op.create_index('pl2e_deleted_idx', 'publishleveltwoentity', ['marked_for_deletion'], unique=False)
    op.create_index('l2e_parent_idx', 'leveltwoentity', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('l2e_entity_type_idx', 'leveltwoentity', ['entity_type'], unique=False)
    op.create_index('l2e_deleted_idx', 'leveltwoentity', ['marked_for_deletion'], unique=False)
    op.create_index('l2e_content_idx', 'leveltwoentity', ['content'], unique=False)
    op.create_index('pge_parent_idx', 'publishgroupingentity', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('pge_entity_type_idx', 'publishgroupingentity', ['entity_type'], unique=False)
    op.create_index('pge_entity_idx', 'publishgroupingentity', ['entity_client_id', 'entity_object_id'], unique=False)
    op.create_index('pge_deleted_idx', 'publishgroupingentity', ['marked_for_deletion'], unique=False)
    op.create_index('ge_parent_idx', 'groupingentity', ['parent_client_id', 'parent_object_id'], unique=False)
    op.create_index('ge_entity_type_idx', 'groupingentity', ['entity_type'], unique=False)
    op.create_index('ge_deleted_idx', 'groupingentity', ['marked_for_deletion'], unique=False)
    op.create_index('ge_content_idx', 'groupingentity', ['content'], unique=False)
    pass


def downgrade():
    op.drop_index('l2e_content_idx', table_name='leveltwoentity')
    op.drop_index('l2e_deleted_idx', table_name='leveltwoentity')
    op.drop_index('l2e_entity_type_idx', table_name='leveltwoentity')
    op.drop_index('l2e_parent_idx', table_name='leveltwoentity')
    op.drop_index('pl2e_deleted_idx', table_name='publishleveltwoentity')
    op.drop_index('pl2e_entity_idx', table_name='publishleveltwoentity')
    op.drop_index('pl2e_entity_type_idx', table_name='publishleveltwoentity')
    op.drop_index('pl2e_parent_idx', table_name='publishleveltwoentity')
    op.drop_index('ge_content_idx', table_name='groupingentity')
    op.drop_index('ge_deleted_idx', table_name='groupingentity')
    op.drop_index('ge_entity_type_idx', table_name='groupingentity')
    op.drop_index('ge_parent_idx', table_name='groupingentity')
    op.drop_index('pge_deleted_idx', table_name='publishgroupingentity')
    op.drop_index('pge_entity_idx', table_name='publishgroupingentity')
    op.drop_index('pge_entity_type_idx', table_name='publishgroupingentity')
    op.drop_index('pge_parent_idx', table_name='publishgroupingentity')
    pass
