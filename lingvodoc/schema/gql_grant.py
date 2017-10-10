import graphene
import datetime
from lingvodoc.models import (
    Grant as dbGrant,
    User as dbUser,
    Client,
    DBSession
)
from lingvodoc.schema.gql_holders import (
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
    LingvodocID
)
from sqlalchemy.orm.attributes import flag_modified

class Grant(graphene.ObjectType):
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
    dbObject = None
    issuer_translation_gist_id = graphene.Int()
    begin = DateTime()
    end = DateTime()
    issuer_url = graphene.String()
    grant_url = graphene.String()
    grant_number = graphene.String()
    owners = JSONString()

    class Meta:
        interfaces = (CreatedAt,
                      TranslationGistHolder,
                      IdHolder,
                      AdditionalMetadata
                    )
    pass

class CreateGrant(graphene.Mutation):
    """
    mutation {
        create_grant(issuer_translation_gist_id:[1,1], translation_gist_id: [949, 101], issuer_url: "abc", grant_url: "def", grant_number: "123", begin: [1,7,2017], end: [2,7,2017]) {
           grant {
               id
            }
            triumph
        }
    }

    {
      "create_grant": {
        "grant": {
          "id": 4
        },
        "triumph": true
      }
    }
    """
    class Arguments:
        issuer_translation_gist_id = LingvodocID()
        translation_gist_id = LingvodocID()
        issuer_url = graphene.String()
        grant_url = graphene.String()
        grant_number = graphene.String()
        begin = LingvodocID()
        end = LingvodocID()

    grant = graphene.Field(Grant)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        issuer_translation_gist_client_id, issuer_translation_gist_object_id = args.get('issuer_translation_gist_id')
        translation_gist_client_id, translation_gist_object_id = args.get('translation_gist_id')
        issuer_url = args.get('issuer_url')
        grant_url = args.get('grant_url')
        grant_number = args.get('grant_number')

        begin_tuple = args.get('begin')
        begin_day = begin_tuple[0]
        begin_month = begin_tuple[1]
        begin_year = begin_tuple[2]
        if begin_day is None or begin_month is None or begin_year is None:
            return ResponseError(message="Error: day, month or year of the begin date is missing")
        begin = datetime.date(begin_year, begin_month, begin_day)

        end_tuple = args.get('end')
        end_day = end_tuple[0]
        end_month = end_tuple[1]
        end_year = end_tuple[2]
        if end_day is None or end_month is None or end_year is None:
            return ResponseError(message="Error: day, month or year of the end date is missing")
        end = datetime.date(end_year, end_month, end_day)

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
                      begin=begin,
                      end=end
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
        update_grant(grant_id: 14, issuer_url: "abc", grant_url: "def") {
           grant {
               id
               begin
               end
               issuer_url
               grant_url
               grant_number
               translation_gist_client_id
               translation_gist_object_id
            }
            triumph
        }
    }
    """
    class Arguments:
        grant_id = graphene.Int()
        issuer_translation_gist_id = LingvodocID()
        translation_gist_id = LingvodocID()
        issuer_url = graphene.String()
        grant_url = graphene.String()
        begin = graphene.String()
        end = graphene.String()
        additional_metadata = ObjectVal()

    grant = graphene.Field(Grant)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
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
                dbgrant.begin = datetime.datetime.strptime(begin, "%d.%M.%Y").date()
            if end:
                dbgrant.end = datetime.datetime.strptime(end, "%d.%M.%Y").date()
            if additional_metadata:
                if additional_metadata.get('participant'):
                    raise ResponseError(message="Protected field")
                old_meta = dbgrant.additional_metadata
                old_meta.update(additional_metadata)
                dbgrant.additional_metadata = old_meta
                flag_modified(dbgrant, 'additional_metadata')

            grant = Grant(id=dbgrant.id)
            grant.dbObject = dbgrant
            return UpdateGrant(grant=grant, triumph=True)
        raise ResponseError(message="No such grunt in the system")

class DeleteGrant(graphene.Mutation):
    """
    mutation {
        delete_grant(grant_id: 14) {
            triumph
        }
    }
    """
    class Arguments:
        grant_id = graphene.Int()

    grant = graphene.Field(Grant)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        grant_id = args.get('grant_id')
        dbgrant = DBSession.query(dbGrant).filter_by(id=grant_id).first()
        if not dbgrant:
            raise ResponseError(message="No such grunt in the system")

        DBSession.delete(dbgrant)
        grant = Grant(id=grant_id)
        grant.dbObject = dbgrant
        return DeleteGrant(grant=grant, triumph=True)