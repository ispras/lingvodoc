import graphene
from sqlalchemy import and_
from lingvodoc.models import (
    DictionaryPerspective as dbPerspective,
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    Client,
    User as dbUser,
    TranslationGist as dbTranslationGist,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    ObjectTOC,
    DBSession
)

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    TranslationHolder,
    StateHolder,
    fetch_object,
    client_id_check,
    del_object,
    ResponseError,
    acl_check_by_id,
    ObjectVal
)

from lingvodoc.schema.gql_dictionary import Dictionary
from lingvodoc.schema.gql_dictipersptofield import DictionaryPerspectiveToField
from lingvodoc.schema.gql_lexicalentry import LexicalEntry
from lingvodoc.schema.gql_language import Language
from lingvodoc.schema.gql_entity import Entity

from lingvodoc.views.v2.utils import add_user_to_group

from lingvodoc.views.v2.translations import translationgist_contents


def translation_service_search(searchstring):
    translationatom = DBSession.query(dbTranslationAtom)\
        .join(dbTranslationGist).\
        filter(dbTranslationAtom.content == searchstring,
               dbTranslationAtom.locale_id == 2,
               dbTranslationGist.type == 'Service')\
        .order_by(dbTranslationAtom.client_id)\
        .first()
    response = translationgist_contents(translationatom.parent)
    return response


class DictionaryPerspective(graphene.ObjectType):
    """
     #created_at                       | timestamp without time zone | NOT NULL
     #object_id                        | bigint                      | NOT NULL
     #client_id                        | bigint                      | NOT NULL
     #parent_object_id                 | bigint                      |
     #parent_client_id                 | bigint                      |
     #translation_gist_client_id       | bigint                      | NOT NULL
     #translation_gist_object_id       | bigint                      | NOT NULL
     #state_translation_gist_client_id | bigint                      | NOT NULL
     #state_translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion              | boolean                     | NOT NULL
     #is_template                      | boolean                     | NOT NULL
     #import_source                    | text                        |
     #import_hash                      | text                        |
     #additional_metadata              | jsonb                       |
     + .translation
     + status
     + tree
    """
    data_type = graphene.String()

    is_template = graphene.Boolean()
    status = graphene.String()
    import_source = graphene.String()
    import_hash = graphene.String()

    tree = graphene.List(CommonFieldsComposite, )  # TODO: check it
    fields = graphene.List(DictionaryPerspectiveToField)
    lexicalEntries = graphene.List(LexicalEntry, offset=graphene.Int(),
                                   count=graphene.Int(),
                                   mode=graphene.String())
    # stats = graphene.String() # ?

    dbType = dbPerspective
    dbObject = None

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder, TranslationHolder)

    # @fetch_object()
    # def resolve_additional_metadata(self, args, context, info):
    #     return self.dbObject.additional_metadata

    # @fetch_object('translation')
    # def resolve_translation(self, args, context, info):
    #     return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object('status')
    def resolve_status(self, info):
        atom = DBSession.query(dbTranslationAtom).filter_by(
            parent_client_id=self.dbObject.state_translation_gist_client_id,
            parent_object_id=self.dbObject.state_translation_gist_object_id,
            locale_id=int(info.context.get('locale_id'))
        ).first()
        if atom:
            return atom.content
        else:
            return None

    @fetch_object()  # TODO: ?
    def resolve_tree(self, info):
        result = list()
        iteritem = self.dbObject
        while iteritem:
            id = [iteritem.client_id, iteritem.object_id]
            if type(iteritem) == dbPerspective:
                result.append(DictionaryPerspective(id=id))
            if type(iteritem) == dbDictionary:
                result.append(Dictionary(id=id))
            if type(iteritem) == dbLanguage:
                result.append(Language(id=id))
            iteritem = iteritem.parent

        return result

    @fetch_object()  # TODO: ?
    def resolve_fields(self, info):
        locale_id = info.context.get("locale_id")
        dbfields = self.dbObject.dictionaryperspectivetofield
        result = list()
        for dbfield in dbfields:
            gr_field_obj = DictionaryPerspectiveToField(id=[dbfield.client_id, dbfield.object_id])
            gr_field_obj.dbObject = dbfield
            result.append(gr_field_obj)
        return result

    @acl_check_by_id('view', 'approve_entities')
    def resolve_lexicalentries(self, info):
        result = list()
        request = info.context.get('request')
        # dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
        lexes = DBSession.query(dbLexicalEntry).filter_by(parent=self.dbObject)

        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes.all()]
        # for lex in lexes:
        #     dbentities = DBSession.query(dbEntity).filter_by(parent=lex).all()
        #     entities = [Entity(id=[ent.client_id, ent.object_id]) for ent in dbentities]
        #     result.append(LexicalEntry(id=[lex.client_id, lex.object_id], entities = entities))
        sub_result = dbLexicalEntry.track_multiple(lexes_composite_list,
                                                   int(request.cookies.get('locale_id') or 2),
                                                   publish=None, accept=True)

        for entry in sub_result:
            entities = []
            for ent in entry['contains']:

                # del attributes that Entity class doesn`t have
                # the code below has to be refactored

                del ent["contains"]
                del ent["level"]
                del ent["accepted"]
                del ent["entity_type"]
                del ent["published"]
                if "link_client_id" in ent and "link_object_id" in ent:
                    ent["link_id"] = (ent["link_client_id"], ent["link_object_id"])
                else:
                    ent["link_id"] = None
                ent["field_id"] = (ent["field_client_id"], ent["field_object_id"])
                if "self_client_id" in ent and "self_object_id" in ent:
                    ent["self_id"] = (ent["self_client_id"], ent["self_object_id"])
                else:
                    ent["self_id"] = None
                    # context["request"].body = str(context["request"].body).replace("self_id", "").encode("utf-8")
                if "content" not in ent:
                    ent["content"] = None
                if "additional_metadata" in ent:

                    # used in AdditionalMetadata interface (gql_holders.py) and sets metadata dictionary

                    ent["additional_metadata_string"] = ent["additional_metadata"]
                    del ent["additional_metadata"]
                gr_entity_object = Entity(id=[ent['client_id'],
                                       ent['object_id']],
                                       # link_id = (ent["link_client_id"], ent["link_object_id"]),
                                       parent_id = (ent["parent_client_id"], ent["parent_object_id"]),
                                       **ent  # all other args from sub_result
                                          )
                #print(ent)
                entities.append(gr_entity_object)
            # del entry["entries"]
            del entry["published"]
            del entry["contains"]
            del entry["level"]
            gr_lexicalentry_object = LexicalEntry(id=[entry['client_id'],
                                                      entry['object_id']],
                                                  entities=entities, **entry)

            result.append(gr_lexicalentry_object)
        return result


class CreateDictionaryPerspective(graphene.Mutation):
    """
    example:
    mutation  {
            create_perspective(id:[949,2491], parent_id:[449,2491], translation_gist_id: [714, 3], is_template: true,
             additional_metadata: {hash:"1234567"}, import_source: "source", import_hash: "hash") {
                triumph
                perspective{
                    id
                    is_template
                }
            }
    }

    (this example works)
    returns:

    {
      "create_perspective": {
        "triumph": true,
        "perspective": {
          "id": [
            949,
            2491
          ],
          "is_template": true
        }
      }
    }
    """

    class Arguments:
        id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        is_template = graphene.Boolean()
        latitude = graphene.String()
        longitude = graphene.String()
        additional_metadata = ObjectVal()
        import_source = graphene.String()
        import_hash = graphene.String()

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    def create_perspective(client_id=None,
                           object_id=None,
                           parent_client_id=None,
                           parent_object_id=None,
                           translation_gist_client_id=None,
                           translation_gist_object_id=None,
                           latitude=None,
                           longitude=None,
                           additional_metadata=None,
                           is_template=None,
                           import_source=None,
                           import_hash=None
                           ):
        parent = DBSession.query(dbDictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            raise ResponseError(message="No such dictionary in the system")
        coord = {}

        if latitude:
            coord['latitude'] = latitude
        if longitude:
            coord['longitude'] = longitude

        if additional_metadata:
            additional_metadata.update(coord)
        else:
            additional_metadata = coord

        resp = translation_service_search("WiP")
        state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']

        dbperspective = dbPerspective(client_id=client_id,
                                      object_id=object_id,
                                      state_translation_gist_object_id=state_translation_gist_object_id,
                                      state_translation_gist_client_id=state_translation_gist_client_id,
                                      parent=parent,
                                      import_source=import_source,
                                      import_hash=import_hash,
                                      additional_metadata=additional_metadata,
                                      translation_gist_client_id=translation_gist_client_id,
                                      translation_gist_object_id=translation_gist_object_id
                                      )
        if is_template is not None:
            dbperspective.is_template = is_template
        DBSession.add(dbperspective)
        DBSession.flush()
        owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
        owner = owner_client.user
        if not object_id:
            for base in DBSession.query(dbBaseGroup).filter_by(perspective_default=True):
                client = DBSession.query(Client).filter_by(id=client_id).first()
                user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
                new_group = dbGroup(parent=base,
                                    subject_object_id=dbperspective.object_id,
                                    subject_client_id=dbperspective.client_id)
                add_user_to_group(user, new_group)
                add_user_to_group(owner, new_group)
                DBSession.add(new_group)
                DBSession.flush()
        return dbperspective

    @staticmethod
    @client_id_check()
    @acl_check_by_id('create', 'perspective', id_key = "parent_id")
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        parent_id = args.get('parent_id')
        parent_client_id = parent_id[0]
        parent_object_id = parent_id[1]
        translation_gist_id = args.get('translation_gist_id')
        translation_gist_client_id = translation_gist_id[0]
        translation_gist_object_id = translation_gist_id[1]
        is_template = args.get('is_template')
        import_source = args.get('import_source')
        import_hash = args.get('import_hash')
        latitude = args.get('latitude')
        longitude = args.get('longitude')
        additional_metadata = args.get('additional_metadata')
        dbperspective = CreateDictionaryPerspective\
            .create_perspective(client_id=client_id,
                                object_id=object_id,
                                parent_client_id=parent_client_id,
                                parent_object_id=parent_object_id,
                                translation_gist_client_id=translation_gist_client_id,
                                translation_gist_object_id=translation_gist_object_id,
                                latitude=latitude,
                                longitude=longitude,
                                additional_metadata=additional_metadata,
                                is_template=is_template,
                                import_source=import_source,
                                import_hash=import_hash
                                )
        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
        perspective.dbObject = dbperspective
        return CreateDictionaryPerspective(perspective=perspective, triumph=True)


class UpdateDictionaryPerspective(graphene.Mutation):
    """
    example:
      mutation  {
            update_perspective(id:[949,2491], parent_id:[449,2491], translation_gist_id: [714, 3], is_template: false) {
                triumph
                perspective{
                    id
                    is_template
                }
            }
    }

    (this example works)
    returns:

    {
      "update_perspective": {
        "triumph": true,
        "perspective": {
          "id": [
            949,
            2491
          ],
          "is_template": false
        }
      }
    }
    """
    class Arguments:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        is_template = graphene.Boolean()

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    @acl_check_by_id('edit', 'perspective')
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0]
        object_id = id[1]
        parent_id = args.get('parent_id')
        dictionary_client_id = parent_id[0]
        dictionary_object_id = parent_id[1]

        dictionary = DBSession.query(dbDictionary).filter_by(client_id=dictionary_client_id,
                                                             object_id=dictionary_object_id).first()
        if not dictionary:
            raise ResponseError(message="No such dictionary in the system")

        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbperspective or dbperspective.marked_for_deletion:
            raise ResponseError(message="Error: No such perspective in the system")

        if dbperspective.parent != dictionary:
            raise ResponseError(message="No such pair of dictionary/perspective in the system")
        translation_gist_id = args.get("translation_gist_id")
        translation_gist_client_id = translation_gist_id[0] if translation_gist_id else None
        translation_gist_object_id = translation_gist_id[1] if translation_gist_id else None
        if translation_gist_client_id:
            dbperspective.translation_gist_client_id = translation_gist_client_id
        if translation_gist_object_id:
            dbperspective.translation_gist_object_id = translation_gist_object_id
        parent_id = args.get("parent_id")
        parent_client_id = parent_id[0] if parent_id else None
        parent_object_id = parent_id[1] if parent_id else None
        if parent_client_id:
            dbperspective.parent_client_id = parent_client_id
        if parent_object_id:
            dbperspective.parent_object_id = parent_object_id

        is_template = args.get('is_template')
        if is_template is not None:
            dbperspective.is_template = is_template

        perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id],
                                            is_template=dbperspective.is_template)
        perspective.dbObject = dbperspective
        return UpdateDictionaryPerspective(perspective=perspective, triumph=True)


class DeleteDictionaryPerspective(graphene.Mutation):
    """
    example:
      mutation  {
            delete_perspective(id:[949,2491], parent_id:[449,2491]) {
                triumph
                perspective{
                    id
                    is_template
                }
            }
    }

    (this example works)
    returns:

    {
      "delete_perspective": {
        "triumph": true,
        "perspective": {
          "id": [
            949,
            2491
          ],
          "is_template": false
        }
      }
    }
    """
    class Arguments:
        id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)

    perspective = graphene.Field(DictionaryPerspective)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    @acl_check_by_id('delete', 'perspective')
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0]
        object_id = id[1]
        parent_id = args.get('parent_id')
        parent_client_id = parent_id[0]
        parent_object_id = parent_id[1]

        parent = DBSession.query(dbDictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            raise ResponseError(message="No such dictionary in the system")

        dbperspective = DBSession.query(dbPerspective).filter_by(client_id=client_id, object_id=object_id).first()

        if dbperspective and not dbperspective.marked_for_deletion:
            if dbperspective.parent != parent:
                raise ResponseError(message="No such pair of dictionary/perspective in the system")
            del_object(dbperspective)
            objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=dbperspective.client_id,
                                                             object_id=dbperspective.object_id).one()
            del_object(objecttoc)

            perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id],
                                                is_template=dbperspective.is_template)
            perspective.dbObject = dbperspective
            return DeleteDictionaryPerspective(perspective=perspective, triumph=True)
        raise ResponseError(message="No such entity in the system")
