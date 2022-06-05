import graphene
import datetime
import time
from json import loads
import logging

import lingvodoc.models as models

from lingvodoc.models import (
    Client,
    DBSession,
    Email as dbEmail,
    Grant as dbGrant,
    User as dbUser,
)

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    DateTime,
    JSONString,
    IdHolder,
    CreatedAt,
    AdditionalMetadata,
    TranslationGistHolder,
    client_id_check,
    acl_check_by_id,
    ResponseError,
    del_object,
    ObjectVal,
    LingvodocID,
    fetch_object,
    TranslationHolder
)

from lingvodoc.schema.gql_user import User

import lingvodoc.utils as utils
from lingvodoc.utils.creation import create_gists_with_atoms

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified


# Setting up logging.
log = logging.getLogger(__name__)


class Grant(LingvodocObjectType):
    """
     #id                                | bigint                      | NOT NULL DEFAULT nextval('grant_id_seq'::regclass)
     #translation_gist_client_id        | bigint                      | NOT NULL
     #translation_gist_object_id        | bigint                      | NOT NULL
     #issuer_translation_gist_client_id | bigint                      | NOT NULL
     #issuer_translation_gist_object_id | bigint                      | NOT NULL
     #begin                             | date                        |
     #end                               | date                        |
     #created_at                        | timestamp without time zone | NOT NULL
     #issuer_url                        | character varying(2048)     | NOT NULL
     #grant_url                         | character varying(2048)     | NOT NULL
     #grant_number                      | character varying(1000)     | NOT NULL
     #owners                            | jsonb                       |
     #additional_metadata               | jsonb                       |
    """
    dbType = dbGrant
    issuer_translation_gist_id = LingvodocID()
    begin = graphene.Int()
    end = graphene.Int()
    issuer_url = graphene.String()
    grant_url = graphene.String()
    grant_number = graphene.String()
    owners = graphene.List(User)

    issuer = graphene.String()
    issuer_translations = ObjectVal()

    class Meta:
        interfaces = (CreatedAt,
                      TranslationGistHolder,
                      IdHolder,
                      AdditionalMetadata,
                      TranslationHolder
                    )

    @staticmethod
    def from_date(date):

        return (
            datetime.datetime
                .strptime(date, '%Y-%m-%d')
                .replace(tzinfo = datetime.timezone.utc)
                .timestamp())

    @fetch_object("issuer")
    def resolve_issuer(self, info):
        context = info.context
        return str(self.dbObject.get_issuer_translation(context.get('locale_id')))

    @fetch_object("issuer_translations")
    def resolve_issuer_translations(self, info):
        return self.dbObject.get_issuer_translations()

    @fetch_object("begin")
    def resolve_begin(self, info):
        return Grant.from_date(self.dbObject.begin)

    @fetch_object("end")
    def resolve_end(self, info):
        return Grant.from_date(self.dbObject.end)

    @fetch_object("issuer_translation_gist_id")
    def resolve_issuer_translation_gist_id(self, info):
        return (self.dbObject.issuer_translation_gist_client_id, self.dbObject.issuer_translation_gist_object_id)

    @fetch_object("grant_number")
    def resolve_grant_number(self, info):
        return self.dbObject.grant_number

    @fetch_object("issuer_url")
    def resolve_issuer_url(self, info):
        return self.dbObject.issuer_url

    @fetch_object("grant_url")
    def resolve_grant_url(self, info):
        return self.dbObject.grant_url

    @fetch_object("owners")
    def resolve_owners(self, info):

        __debug_flag__ = False

        # Analyzing query.

        if __debug_flag__:

            log.debug(f'\ninfo.field_asts:\n{info.field_asts}')

        email_flag = False

        for field in info.field_asts:

            if field.name.value != 'owners':
                continue

            for subfield in field.selection_set.selections:

                if subfield.name.value == 'email':

                    email_flag = True
                    break

        user_query = (

            DBSession
                .query(dbUser)

                .filter(

                    dbUser.id.in_(
                        utils.values_query(
                            self.dbObject.owners, models.SLBigInteger))))

        gql_user_list = []

        if email_flag:

            user_query = (

                user_query.options(
                    joinedload(dbUser.email)))

        for user in user_query:

            gql_user = User(id = user.id)
            gql_user.dbObject = user

            gql_user_list.append(gql_user)

        return gql_user_list

class CreateGrant(graphene.Mutation):
    """
    mutation {
        update_grant(grant_id: 4,
					issuer_url: "abc",
					grant_url: "def",
				begin:233, end:300) {
           grant {
               id
               begin
               end
               issuer_url
               grant_url
               grant_number

            }
            triumph
        }
    }


    {
        "data": {
            "create_grant": {
                "grant": {
                    "id": 4
                },
                "triumph": true
            }
        }
    }
    """
    class Arguments:
        issuer_translation_gist_id = LingvodocID()  # not required if atoms are given instead of gist_id
        translation_gist_id = LingvodocID()
        issuer_url = graphene.String(required=True)
        grant_url = graphene.String(required=True)
        grant_number = graphene.String(required=True)
        begin = graphene.Int(required=True)
        end = graphene.Int(required=True)
        translation_atoms = graphene.List(ObjectVal)
        issuer_translation_atoms = graphene.List(ObjectVal)
    grant = graphene.Field(Grant)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('create', 'grant')
    def mutate(root, info, **args):
        ids = args.get("id")
        client_id = ids[0] if ids else info.context["client_id"]
        object_id = ids[1] if ids else None
        issuer_translation_gist_id = args.get('issuer_translation_gist_id')
        issuer_translation_atoms = args.get("issuer_translation_atoms")
        issuer_translation_gist_id = create_gists_with_atoms(issuer_translation_atoms,
                                                             issuer_translation_gist_id,
                                                             [client_id,object_id],
                                                             gist_type="Grant")
        issuer_translation_gist_client_id, issuer_translation_gist_object_id = issuer_translation_gist_id
        translation_gist_id = args.get("translation_gist_id")
        translation_atoms = args.get("translation_atoms")
        translation_gist_id = create_gists_with_atoms(translation_atoms,
                                                      translation_gist_id,
                                                      [client_id,object_id],
                                                      gist_type="Grant")
        translation_gist_client_id, translation_gist_object_id = translation_gist_id
        issuer_url = args.get('issuer_url')
        grant_url = args.get('grant_url')
        grant_number = args.get('grant_number')

        begin = args.get('begin')
        begin_time = None
        if begin:
            begin_time = datetime.datetime.fromtimestamp(begin)

        end = args.get('end')
        end_time = None
        if end:
            end_time = datetime.datetime.fromtimestamp(end)

        client_id = info.context["client_id"]
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        dbgrant = dbGrant(issuer_translation_gist_client_id=issuer_translation_gist_client_id,
                      issuer_translation_gist_object_id=issuer_translation_gist_object_id,
                      translation_gist_client_id=translation_gist_client_id,
                      translation_gist_object_id=translation_gist_object_id,
                      issuer_url=issuer_url,
                      grant_url=grant_url,
                      grant_number=grant_number,
                      begin=begin_time,
                      end=end_time
                      )
        """ 
        dbgrant.grant_url = grant_url
        dbgrant.issuer_url = issuer_url
        dbgrant.grant_number = grant_number
        dbgrant.begin = begin
        dbgrant.end = end
        """

        DBSession.add(dbgrant)

        DBSession.flush()

        grant = Grant(id=dbgrant.id)
        grant.dbObject = dbgrant
        return CreateGrant(grant=grant, triumph=True)

class UpdateGrant(graphene.Mutation):
    """
    mutation {
        update_grant(grant_id: 4, issuer_url: "abc", grant_url: "def") {
           grant {
               id
               begin
               end
               issuer_url
               grant_url
               grant_number

            }
            triumph
        }
    }
    """
    class Arguments:
        grant_id = graphene.Int(required=True)  # this should be just id
        issuer_translation_gist_id = LingvodocID()
        translation_gist_id = LingvodocID()
        issuer_url = graphene.String()
        grant_url = graphene.String()
        begin = graphene.Int()
        end = graphene.Int()
        grant_number = graphene.String()
        additional_metadata = ObjectVal()

    grant = graphene.Field(Grant)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('create', 'grant')
    def mutate(root, info, **args):
        grant_id = args.get('grant_id')
        issuer_translation_gist_id = args.get('issuer_translation_gist_id')
        translation_gist_id = args.get('translation_gist_id')
        issuer_url = args.get('issuer_url')
        grant_url = args.get('grant_url')
        begin = args.get('begin')
        end = args.get('end')
        additional_metadata = args.get('additional_metadata')

        dbgrant = DBSession.query(dbGrant).filter_by(id=grant_id).first()
        if dbgrant:
            if issuer_translation_gist_id:
                dbgrant.issuer_translation_gist_client_id = issuer_translation_gist_id[0]
                dbgrant.issuer_translation_gist_object_id = issuer_translation_gist_id[1]
            if translation_gist_id:
                dbgrant.translation_gist_client_id = translation_gist_id[0]
                dbgrant.translation_gist_object_id = translation_gist_id[1]
            if issuer_url:
                dbgrant.issuer_url = issuer_url
            if grant_url:
                dbgrant.grant_url = grant_url
            if begin:
                dbgrant.begin = datetime.datetime.fromtimestamp(begin)
            if end:
                dbgrant.end = datetime.datetime.fromtimestamp(end)
            if additional_metadata:
                if additional_metadata.get('participant'):
                    raise ResponseError(message="Protected field")
                old_meta = dbgrant.additional_metadata
                if old_meta is None:
                    old_meta = dict()
                old_meta.update(additional_metadata)
                dbgrant.additional_metadata = old_meta
                # flag_modified(dbgrant, 'additional_metadata')
            grant = Grant(id=dbgrant.id)
            grant.dbObject = dbgrant
            return UpdateGrant(grant=grant, triumph=True)
        raise ResponseError(message="No such grant in the system")

# class DeleteGrant(graphene.Mutation):
#     """
#     mutation {
#         delete_grant(grant_id: 14) {
#             triumph
#         }
#     }
#     """
#     class Arguments:
#         grant_id = graphene.Int()
#
#     grant = graphene.Field(Grant)
#     triumph = graphene.Boolean()
#
#     @staticmethod
#     @acl_check_by_id('create', 'grant')
#     def mutate(root, info, **args):
#         grant_id = args.get('grant_id')
#         dbgrant = DBSession.query(dbGrant).filter_by(id=grant_id).first()
#         if not dbgrant:
#             raise ResponseError(message="No such grant in the system")
#
#         DBSession.delete(dbgrant)
#         grant = Grant(id=grant_id)
#         grant.dbObject = dbgrant
#         return DeleteGrant(grant=grant, triumph=True)
#
# class DeleteGrantOwners(graphene.Mutation):
#     class Arguments:
#         grant_id = graphene.Int()
#
#     @acl_check_by_id('approve', 'grant')
#     def mutate(root, info, **args):
#         grant_id = args.get("grant_id")
#         owners = args.get("owners")
