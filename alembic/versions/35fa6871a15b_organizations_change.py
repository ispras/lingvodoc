
"""Organizations change

Revision ID: 35fa6871a15b
Revises: eb70cc55b178
Create Date: 2019-11-12 17:38:43.123469

"""


# revision identifiers, used by Alembic.
revision = '35fa6871a15b'
down_revision = 'eb70cc55b178'
branch_labels = None
depends_on = None


from lingvodoc.models import DBSession, SLBigInteger


from alembic import op
import sqlalchemy as sa


def upgrade():

    # Updating organization table.

    with op.batch_alter_table('organization') as batch_op:

        batch_op.drop_column('name')
        batch_op.drop_column('about')

        batch_op.add_column(sa.Column(
            'translation_gist_client_id',
            SLBigInteger(),
            nullable = False))

        batch_op.add_column(sa.Column(
            'translation_gist_object_id',
            SLBigInteger(),
            nullable = False))

        batch_op.create_foreign_key(
            'organization_translation_gist_object_id_fkey',
            'translationgist',
            ['translation_gist_object_id',
                'translation_gist_client_id'],
            ['object_id',
                'client_id'])

        batch_op.add_column(sa.Column(
            'about_translation_gist_client_id',
            SLBigInteger(),
            nullable = False))

        batch_op.add_column(sa.Column(
            'about_translation_gist_object_id',
            SLBigInteger(),
            nullable = False))

        batch_op.create_foreign_key(
            'organization_about_translation_gist_object_id_fkey',
            'translationgist',
            ['about_translation_gist_object_id',
                'about_translation_gist_client_id'],
            ['object_id',
                'client_id'])

    # Leaving organization creation rights only to the administrator.

    op.execute('''

        delete from
        user_to_group_association U

        using
        basegroup B,
        public.group G

        where
        B.name = 'Can create organizations' and
        G.base_group_id = B.id and
        U.group_id = G.id and
        U.user_id != 1;

        ''')


def downgrade():

    # Updating organization table.

    with op.batch_alter_table('organization') as batch_op:

        batch_op.drop_constraint('organization_translation_gist_object_id_fkey')

        batch_op.drop_column('translation_gist_client_id')
        batch_op.drop_column('translation_gist_object_id')

        batch_op.drop_constraint('organization_about_translation_gist_object_id_fkey')

        batch_op.drop_column('about_translation_gist_client_id')
        batch_op.drop_column('about_translation_gist_object_id')

        batch_op.add_column(sa.Column(
            'name',
            sa.TEXT(),
            nullable = True))

        batch_op.add_column(sa.Column(
            'about',
            sa.TEXT(),
            nullable = True))

