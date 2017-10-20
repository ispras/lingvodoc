import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    CreatedAt,
    MarkedForDeletion,
    TypeHolder,
    client_id_check,
    acl_check_by_id,
    ResponseError,
    fetch_object,
    LingvodocID
)

from lingvodoc.models import (
    TranslationGist as dbTranslationGist,
    Client,
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    ObjectTOC as dbObjectTOC,
    DBSession,
    TranslationAtom as dbTranslationAtom
)
from lingvodoc.views.v2.utils import check_client_id, add_user_to_group
from lingvodoc.schema.gql_translationatom import TranslationAtom

class TranslationGist(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #marked_for_deletion | boolean                     | NOT NULL
     #type                | text                        |

     {"variables": {}, "query": "query QUERYNAME { translationgist(id:[578, 6]){id created_at}}"   }

    """
    dbType = dbTranslationGist
    dbObject = None
    translationatoms = graphene.List(TranslationAtom)

    class Meta:
        interfaces = (CompositeIdHolder,
                      CreatedAt,
                      MarkedForDeletion,
                      TypeHolder

                      )

    @fetch_object() # TODO: fix that
    def resolve_translationatoms(self, info):
        result = list()
        for dbatom in self.dbObject.translationatom:
            atom =  TranslationAtom(id=[dbatom.client_id, dbatom.object_id])
            atom.dbObject = dbatom
            result.append(atom)
        return result


class CreateTranslationGist(graphene.Mutation):
    """
    example:
    mutation {
        create_translationgist(id: [949,22], type: "some type") {
            translationgist {
                id
                type
            }
            triumph
        }
    }
    (this example works)
    returns:
    {
        "data": {
            "create_translationgist": {
                "translationgist": {
                    "id": [
                        1197,
                        206
                    ],
                    "type": "some type"
                },
                "triumph": true
            }
        }
    }
    """

    class Arguments:
        id = LingvodocID()
        type = graphene.String(required=True)

    translationgist = graphene.Field(TranslationGist)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        type = args.get('type')
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        dbtranslationgist = dbTranslationGist(client_id=client_id, object_id=object_id, type=type)
        DBSession.add(dbtranslationgist)
        DBSession.flush()
        basegroups = list()
        basegroups.append(DBSession.query(dbBaseGroup).filter_by(name="Can delete translationgist").first())
        if not object_id:
            groups = []
            for base in basegroups:
                group = dbGroup(subject_client_id=dbtranslationgist.client_id, subject_object_id=dbtranslationgist.object_id,
                              parent=base)
                groups += [group]
            for group in groups:
                add_user_to_group(user, group)

        translationgist = TranslationGist(id=[dbtranslationgist.client_id, dbtranslationgist.object_id])
        translationgist.dbObject = dbtranslationgist
        return CreateTranslationGist(translationgist=translationgist, triumph=True)

class DeleteTranslationGist(graphene.Mutation):
    """
    example:
    mutation {
        delete_translationgist(id: [949,22]) {
            translationgist {
                id
            }
            triumph
        }
    }

    now returns:
    {
      "delete_translationgist": {
        "translationgist": {
          "id": [
            949,
            22
          ]
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)

    translationgist = graphene.Field(TranslationGist)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'translations')
    def mutate(root, info, **args):
        id = args.get('id')
        client_id, object_id= id
        dbtranslationgist = DBSession.query(dbTranslationGist).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbtranslationgist or dbtranslationgist.marked_for_deletion:
            raise ResponseError(message="No such translationgist in the system")
        dbtranslationgist.marked_for_deletion = True
        objecttoc = DBSession.query(dbObjectTOC).filter_by(client_id=dbtranslationgist.client_id,
                                                         object_id=dbtranslationgist.object_id).one()
        objecttoc.marked_for_deletion = True
        for translationatom in dbtranslationgist.translationatom:
            translationatom.marked_for_deletion = True
            objecttoc = DBSession.query(dbObjectTOC).filter_by(client_id=translationatom.client_id,
                                                             object_id=translationatom.object_id).one()
            objecttoc.marked_for_deletion = True

        translationgist = TranslationGist(id=[dbtranslationgist.client_id, dbtranslationgist.object_id])
        translationgist.dbObject = dbtranslationgist
        return DeleteTranslationGist(translationgist=translationgist, triumph=True)
