import graphene
from sqlalchemy import and_
from lingvodoc.models import (
    DictionaryPerspective as dbPerspective,
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    DBSession
)

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    TranslationHolder,
    StateHolder,
    fetch_object
)

from lingvodoc.schema.gql_dictionary import Dictionary
from lingvodoc.schema.gql_dictipersptofield import DictionaryPerspectiveToField
from lingvodoc.schema.gql_lexicalentry import LexicalEntry
from lingvodoc.schema.gql_language import Language


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
    lexicalEntries = graphene.List(LexicalEntry, offset = graphene.Int(), count = graphene.Int(), mode = graphene.String())
    #stats = graphene.String() # ?


    dbType = dbPerspective
    dbObject = None

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder, TranslationHolder)


    @fetch_object()
    def resolve_additional_metadata(self, args, context, info):
        return self.dbObject.additional_metadata

    @fetch_object('data_type')
    def resolve_data_type(self, args, context, info):
        return 'perspective'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object('status')
    def resolve_status(self, args, context, info):
        atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=self.dbObject.state_translation_gist_client_id,
                                                          parent_object_id=self.dbObject.state_translation_gist_object_id,
                                                          locale_id=int(context.get('locale_id'))).first()
        if atom:
            return atom.content
        else:
            return None

    @fetch_object() # TODO: ?
    def resolve_tree(self, args, context, info):
        # print(self.dbObject)
        # print(DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one())

        result = list()
        iteritem = self.dbObject
        while iteritem:
            #print(type(iteritem))
            id = [iteritem.client_id, iteritem.object_id]
            if type(iteritem) == dbPerspective:
                result.append(DictionaryPerspective(id=id))
            if type(iteritem) == dbDictionary:
                result.append(Dictionary(id=id))
            if type(iteritem) == dbLanguage:
                result.append(Language(id=id))
            iteritem = iteritem.parent

        return result

    @fetch_object() # TODO: ?
    def resolve_fields(self, args, context, info):
        locale_id = context.get("locale_id")
        dbFields = self.dbObject.dictionaryperspectivetofield
        result = list()
        for dbfield in dbFields:
            gr_field_obj = DictionaryPerspectiveToField(id=[dbfield.client_id, dbfield.object_id])
            gr_field_obj.dbObject = dbfield
            result.append(gr_field_obj)
        return result

    def resolve_lexicalEntries(self, args, context, info):
        result = list()
        request = context.get('request')

        #dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
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
        #print(context["request"].body)
        #Request.
        for entry in sub_result:
            entities = []
            for ent in entry['contains']:
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
                    #context["request"].body = str(context["request"].body).replace("self_id", "").encode("utf-8")
                if not "content" in ent:
                    ent["content"] = None
                # if not "additional_metadata" in ent:
                #     ent["additional_metadata"] = None
                #print(ent)
                if "additional_metadata" in ent:
                    ent["additional_metadata_string"] = ent["additional_metadata"]
                    #print(ent["additional_metadata_string"])
                    del ent["additional_metadata"]
                gr_entity_object = Entity(id=[ent['client_id'],
                                       ent['object_id']],
                                       #link_id = (ent["link_client_id"], ent["link_object_id"]),
                                       parent_id = (ent["parent_client_id"], ent["parent_object_id"]),

                                   #content=ent.get('content'),
                                   #fieldType=ent['data_type'],
                                   ** ent)
                #print(ent)
                entities.append(gr_entity_object)
            #del entry["entries"]
            del entry["published"]
            del entry["contains"]
            del entry["level"]
            gr_lexicalentry_object = LexicalEntry(id=[entry['client_id'], entry['object_id']], entities=entities, **entry)

            result.append(gr_lexicalentry_object)


        return result
