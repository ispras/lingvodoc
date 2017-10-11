import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    Relationship,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    Content,
    client_id_check,
    acl_check_by_id,
    ResponseError,
    LocaleId,
    LingvodocID
)
from lingvodoc.models import (
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Client,
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    DBSession
)

from lingvodoc.views.v2.utils import check_client_id, add_user_to_group
from lingvodoc.cache.caching import CACHE


class TranslationAtom(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #locale_id           | bigint                      | NOT NULL
     #marked_for_deletion | boolean                     | NOT NULL
     #content             | text                        | NOT NULL
     #additional_metadata | jsonb                       |
     example:
         query myQuery {
            translationatom( id: [449, 47]) {
                id
                content
            }
         }

    """
    dbType = dbTranslationAtom
    dbObject = None

    class Meta:
        interfaces = (CompositeIdHolder, Relationship, AdditionalMetadata, CreatedAt, MarkedForDeletion,  Content,
                      LocaleId)
    pass


class CreateTranslationAtom(graphene.Mutation):
    """
    example:
    mutation  {
        create_translationatom(id: [949,11], parent_id: [1, 47], locale_id: 2, content: "some content") {
            translationatom {
                id
                content
            }
            triumph
        }
    }
    (this example works)
    returns:

     {
      "create_translationatom": {
        "translationatom": {
          "id": [
            949,
            11
          ],
          "content": "some content"
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)
        parent_id = LingvodocID()
        locale_id = graphene.Int()
        content = graphene.String()

    translationatom = graphene.Field(TranslationAtom)
    triumph = graphene.Boolean()

    @staticmethod
    def create_dbtranslationatom(id=None,
                                 locale_id=2,
                                 content=None,
                                 parent_id=None,):

            client_id, object_id = id
            parent_client_id, parent_object_id = parent_id

            client = DBSession.query(Client).filter_by(id=client_id).first()
            user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            if not user:
                raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

            parent = DBSession.query(dbTranslationGist).filter_by(client_id=parent_client_id,
                                                                  object_id=parent_object_id).first()

            if parent.marked_for_deletion:
                raise ResponseError(message="Error: no such translationgist in the system.")
            dbtranslationatom = dbTranslationAtom(client_id=client_id,
                                                  object_id=object_id,
                                                  parent=parent,
                                                  locale_id=locale_id,
                                                  content=content)
            DBSession.add(dbtranslationatom)
            DBSession.flush()
            if not object_id:
                basegroups = []
                basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can edit translationatom").first()]
                if not object_id:
                    groups = []
                    for base in basegroups:
                        group = dbGroup(subject_client_id=dbtranslationatom.client_id,
                                        subject_object_id=dbtranslationatom.object_id,
                                        parent=base)
                        groups += [group]
                    for group in groups:
                        add_user_to_group(user, group)
            return dbtranslationatom

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        ids = args.get("id")
        client_id = ids[0] if ids else info.context["client_id"]
        object_id = ids[1] if ids else None
        id = [client_id, object_id]

        parent_id = args.get('parent_id')
        locale_id = args.get('locale_id')
        content = args.get('content')

        dbtranslationatom = CreateTranslationAtom.create_dbtranslationatom(id=id,
                                                     locale_id=locale_id,
                                                     content=content,
                                                     parent_id=parent_id)
        translationatom = TranslationAtom(id=[dbtranslationatom.client_id, dbtranslationatom.object_id],
                                          content=dbtranslationatom.content)
        translationatom.dbObject = dbtranslationatom
        return CreateTranslationAtom(translationatom=translationatom, triumph=True)


class UpdateTranslationAtom(graphene.Mutation):
    """
    example:
    mutation {
        update_translationatom(id: [949,11], content: "new content") {
            translationatom {
                id
                content
            }
            triumph
        }
    }

    now returns:

    {
      "update_translationatom": {
        "translationatom": {
          "id": [
            949,
            11
          ],
          "content": "new content"
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)
        content = graphene.String(required=True)

    translationatom = graphene.Field(TranslationAtom)
    triumph = graphene.Boolean()
    locale_id = graphene.Int()

    @staticmethod
    @acl_check_by_id('edit', 'translations')
    def mutate(root, info, **args):
        content = args.get('content')
        id = args.get('id')
        client_id = id[0]
        object_id = id[1]
        locale = locale = args.get("locale_id")

        dbtranslationatom = DBSession.query(dbTranslationAtom).\
            filter_by(client_id=client_id, object_id=object_id).first()
        if dbtranslationatom:
            key = "translation:%s:%s:%s" % (
                str(dbtranslationatom.parent_client_id),
                str(dbtranslationatom.parent_object_id),
                str(dbtranslationatom.locale_id))
            CACHE.rem(key)
            if content:
                dbtranslationatom.content = content
            if locale:
                dbtranslationatom.locale_id = locale

            translationatom = TranslationAtom(id=[dbtranslationatom.client_id, dbtranslationatom.object_id],
                                              content=dbtranslationatom.content, locale_id=locale)
            translationatom.dbObject = dbtranslationatom
            return UpdateTranslationAtom(translationatom=translationatom, triumph=True)
        raise ResponseError(message="Error: no such translationatom in the system")
