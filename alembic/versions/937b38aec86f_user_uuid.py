"""Changing user ids to UUIDs to prepare for Keycloak

Revision ID: 937b38aec86f
Revises: b0148e63e586
Create Date: 2025-11-22 14:25:45.971665

"""

# revision identifiers, used by Alembic.
revision = '937b38aec86f'
down_revision = 'b0148e63e586'
branch_labels = None
depends_on = None


# Standard library imports.

from json import dumps
import logging
import pprint


# External imports.

from alembic import op
import sqlalchemy as sa


log = logging.getLogger('keycloak')


def upgrade():

    op.execute('''

        ALTER TABLE IF EXISTS ONLY public."adverb_annotation_data" DROP CONSTRAINT IF EXISTS adverb_annotation_data_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."client" DROP CONSTRAINT IF EXISTS client_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."email" DROP CONSTRAINT IF EXISTS email_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."passhash" DROP CONSTRAINT IF EXISTS passhash_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."user_to_group_association" DROP CONSTRAINT IF EXISTS user_to_group_association_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."user_to_organization_association" DROP CONSTRAINT IF EXISTS user_to_organization_association_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."userblobs" DROP CONSTRAINT IF EXISTS userblobs_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."valency_annotation_data" DROP CONSTRAINT IF EXISTS valency_annotation_data_user_id_fkey;
        
        ALTER TABLE public."user" ADD COLUMN "id_v1" BIGINT;
        UPDATE public."user" SET "id_v1" = "id";

        ALTER TABLE public."user" ALTER COLUMN "id" DROP DEFAULT;

        ALTER TABLE ONLY public."adverb_annotation_data" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."client" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."email" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."passhash" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."user" ALTER COLUMN id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."user_to_group_association" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."user_to_organization_association" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."userblobs" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;        
        ALTER TABLE ONLY public."userrequest" ALTER COLUMN recipient_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(recipient_id), 12, '0')) :: uuid;
        ALTER TABLE ONLY public."valency_annotation_data" ALTER COLUMN user_id TYPE UUID USING ('00000000-0000-4000-8000-' || LPAD(to_hex(user_id), 12, '0')) :: uuid;
        
        ALTER TABLE ONLY public."adverb_annotation_data" ADD CONSTRAINT adverb_annotation_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;
        ALTER TABLE ONLY public."client" ADD CONSTRAINT client_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;
        ALTER TABLE ONLY public."email" ADD CONSTRAINT email_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;
        ALTER TABLE ONLY public."passhash" ADD CONSTRAINT passhash_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;
        ALTER TABLE ONLY public."user_to_group_association" ADD CONSTRAINT user_to_group_association_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;
        ALTER TABLE ONLY public."user_to_organization_association" ADD CONSTRAINT user_to_organization_association_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;
        ALTER TABLE ONLY public."userblobs" ADD CONSTRAINT userblobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;
        ALTER TABLE ONLY public."valency_annotation_data" ADD CONSTRAINT valency_annotation_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON UPDATE CASCADE;

        '''
    )


def downgrade():

    op.execute('''

        ALTER TABLE IF EXISTS ONLY public."adverb_annotation_data" DROP CONSTRAINT IF EXISTS adverb_annotation_data_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."client" DROP CONSTRAINT IF EXISTS client_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."email" DROP CONSTRAINT IF EXISTS email_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."passhash" DROP CONSTRAINT IF EXISTS passhash_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."user_to_group_association" DROP CONSTRAINT IF EXISTS user_to_group_association_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."user_to_organization_association" DROP CONSTRAINT IF EXISTS user_to_organization_association_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."userblobs" DROP CONSTRAINT IF EXISTS userblobs_user_id_fkey;
        ALTER TABLE IF EXISTS ONLY public."valency_annotation_data" DROP CONSTRAINT IF EXISTS valency_annotation_data_user_id_fkey;

        ALTER TABLE ONLY public."adverb_annotation_data" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."user" ALTER COLUMN id TYPE BIGINT USING ('x0000' || split_part(id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."client" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."email" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."passhash" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."user_to_group_association" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."user_to_organization_association" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."userblobs" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."userrequest" ALTER COLUMN recipient_id TYPE BIGINT USING ('x0000' || split_part(recipient_id :: text, '-', 5)) :: bit(64) :: bigint;
        ALTER TABLE ONLY public."valency_annotation_data" ALTER COLUMN user_id TYPE BIGINT USING ('x0000' || split_part(user_id :: text, '-', 5)) :: bit(64) :: bigint;

        ALTER TABLE ONLY public."user" DROP COLUMN id_v1;

        ALTER TABLE public."user" ALTER COLUMN "id" SET DEFAULT nextval('user_id_seq'::regclass);

        ALTER TABLE ONLY public."adverb_annotation_data" ADD CONSTRAINT adverb_annotation_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
        ALTER TABLE ONLY public."client" ADD CONSTRAINT client_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
        ALTER TABLE ONLY public."email" ADD CONSTRAINT email_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
        ALTER TABLE ONLY public."passhash" ADD CONSTRAINT passhash_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
        ALTER TABLE ONLY public."user_to_group_association" ADD CONSTRAINT user_to_group_association_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
        ALTER TABLE ONLY public."user_to_organization_association" ADD CONSTRAINT user_to_organization_association_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
        ALTER TABLE ONLY public."userblobs" ADD CONSTRAINT userblobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);
        ALTER TABLE ONLY public."valency_annotation_data" ADD CONSTRAINT valency_annotation_data_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);

        '''
    )
