import graphene
from lingvodoc.models import (
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    DictionaryPerspectiveToField as dbField,
    Language as dbLanguage,
    TranslationAtom as dbTranslationAtom,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry
)
from pyramid.request import Request

from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_
)



class Holder(graphene.Interface):
    id = graphene.List(graphene.Int)
    translation = graphene.String()
    dataType = graphene.String()

def fetch_object(attrib_name):
    def dec(func):
        def wrapper(*args, **kwargs):
            cls = args[0]
            if hasattr(cls, attrib_name):
                return getattr(cls, attrib_name)
            if not cls.dbObject:
                cls.dbObject = DBSession.query(cls.dbType).filter_by(client_id=cls.id[0], object_id=cls.id[1]).one()
            return func(*args, **kwargs)
        return wrapper
    return dec

class Field(graphene.ObjectType):
    class Meta:
        interfaces = (Holder, )

    def resolve_dataType(self):
        return 'field'
    dbType = dbField
    dbObject = None

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.field.get_translation(context.get('locale_id'))

class Entity(graphene.ObjectType):
    id = graphene.List(graphene.Int)
    content = graphene.String()
    fieldType = graphene.String()

    dbType = dbEntity
    dbObject = None
    @fetch_object('content')
    def resolve_content(self, args, context, info):
        return self.dbObject.content

    @fetch_object('fieldType')
    def resolve_fieldType(self, args, context, info):
        return self.dbObject.field.data_type


class LexicalEntry(graphene.ObjectType):
    id = graphene.List(graphene.Int)
    entities = graphene.List(Entity)


    def resolve_entities(self, args, context, info):
        if hasattr(self, 'entities'):
            return self.entities
        else:

            result = list()
            dbLex = DBSession.query(dbLexicalEntry).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
            for entity in dbLex.entity:
                result.append(Entity(id=[entity.client_id, entity.object_id]))
            return result[:2]

class Perspective(graphene.ObjectType):
    class Meta:
        interfaces = (Holder, )


    status = graphene.String()
    tree = graphene.List(Holder)
    fields = graphene.List(Field)
    lexicalEntries = graphene.List(LexicalEntry, offset = graphene.Int(), count = graphene.Int(), mode = graphene.String())
    stats = graphene.String()

    def resolve_dataType(self, args, context, info):
        return 'perspective'


    def resolve_translation(self, args, context, info):
        if hasattr(self, 'translation'):
            return self.translation
        else:
            dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
            return dbPersp.get_translation(context.get('locale_id'))

    def resolve_status(self, args, context, info):
        if hasattr(self, 'status'):
            return self.translation
        else:
            dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
            atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=dbPersp.state_translation_gist_client_id,
                                                              parent_object_id=dbPersp.state_translation_gist_object_id,
                                                              locale_id=int(context.get('locale_id'))).first()
            if atom:
                return atom.content
            else:
                return None

    def resolve_tree(self, args, context, info):
        dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
        result = list()
        iteritem = dbPersp
        while iteritem:
            id = [iteritem.client_id, iteritem.object_id]
            if type(iteritem) == dbPerspective:
                result.append(Perspective(id=id))
            if type(iteritem) == dbDictionary:
                result.append(Dictionary(id=id))
            if type(iteritem) == dbLanguage:
                result.append(Language(id=id))
            iteritem = iteritem.parent
        return result

    def resolve_fields(self, args, context, info):
        dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
        dbFields = dbPersp.dictionaryperspectivetofield
        result = list()
        for dbfield in dbFields:
            result.append(Field(id=[dbfield.client_id, dbfield.object_id]))
        return result

    def resolve_lexicalEntries(self, args, context, info):
        result = list()
        request = context.get('request')

        dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
        # lexes = DBSession.query(dbLexicalEntry).filter_by(parent=dbPersp)
        #
        # lexes_composite_list = [(lex.created_at,
        #                          lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
        #                          lex.marked_for_deletion, lex.additional_metadata,
        #                          lex.additional_metadata.get('came_from')
        #                          if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
        #                         for lex in lexes.all()]
        # for lex in lexes:
        #     dbentities = DBSession.query(dbEntity).filter_by(parent=lex).all()
        #     entities = [Entity(id=[ent.client_id, ent.object_id]) for ent in dbentities]
        #     result.append(LexicalEntry(id=[lex.client_id, lex.object_id], entities = entities))

        lex = DBSession.query(dbLexicalEntry).filter_by(parent=dbPersp).first()
        lexes_composite_list = [lex]
        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes_composite_list]
        sub_result = dbLexicalEntry.track_multiple(lexes_composite_list,
                                             int(request.cookies.get('locale_id') or 2),
                                             publish=None, accept=True)

        # sub_result = dbLexicalEntry.track_multiple(lexes_composite_list,
        #                                      int(request.cookies.get('locale_id') or 2),
        #                                      publish=None, accept=True)
        for entry in sub_result:
            entities = [Entity(id=[ent['client_id'], ent['object_id']],  fieldType=ent['data_type']) for ent in entry['contains']]

            result.append(LexicalEntry(id=[entry['client_id'], entry['object_id']], entities=entities))


        return result

class Language(graphene.ObjectType):
    class Meta:
        interfaces = (Holder, )

    def resolve_dataType(self, args, context, info):
        return 'language'


    def resolve_translation(self, args, context, info):
        if hasattr(self, 'translation'):
            return self.translation
        else:
            dbLang = DBSession.query(dbLanguage).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
            return dbLang.get_translation(context.get('locale_id'))


class Dictionary(graphene.ObjectType):
    class Meta:
        interfaces = (Holder, )
    status = graphene.String()

    def resolve_dataType(self, args, context, info):
        return 'dictionary'


    def resolve_translation(self, args, context, info):
        if hasattr(self, 'translation'):
            return self.translation
        else:
            dbdict = DBSession.query(dbDictionary).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
            # return dbdict.get_translation(2)
            return dbdict.get_translation(context.get('locale_id'))

    def resolve_status(self, args, context, info):
        if hasattr(self, 'status'):
            return self.status
        else:
            dbdict = DBSession.query(dbDictionary).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
            atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=dbdict.state_translation_gist_client_id,
                                                              parent_object_id=dbdict.state_translation_gist_object_id,
                                                              locale_id=int(context.get('locale_id'))).first()
            if atom:
                return atom.content
            else:
                return None

class Query(graphene.ObjectType):

    client = graphene.String()
    dictionaries = graphene.List(Dictionary, published=graphene.Boolean())
    dictionary = graphene.Field(Dictionary, id=graphene.List(graphene.Int))
    perspective = graphene.Field(Perspective, id=graphene.List(graphene.Int))
    entity = graphene.Field(Entity, id=graphene.List(graphene.Int))
    language = graphene.Field(Language, id=graphene.List(graphene.Int))
    def resolve_client(self, args, context, info):
        return context.get('client')

    def resolve_dictionaries(self, args, context, info):
        dbdicts = list()
        request = context.get('request')
        if args.get('published'):

            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Published'}
            headers = dict()
            if request.headers.get('Cookie'):
                headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)

            if 'error' not in resp.json:
                state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                    'client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Limited access'}  # todo: fix
            headers = dict()
            if request.headers.get('Cookie'):
                headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)

            if 'error' not in resp.json:
                limited_object_id, limited_client_id = resp.json['object_id'], resp.json['client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            dbdicts = DBSession.query(dbDictionary).filter(or_(and_(dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                                                                    dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id),
                                 and_(dbDictionary.state_translation_gist_object_id == limited_object_id,
                                      dbDictionary.state_translation_gist_client_id == limited_client_id))).\
                join(dbPerspective) \
                .filter(or_(and_(dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                             dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
                        and_(dbPerspective.state_translation_gist_object_id == limited_object_id,
                             dbPerspective.state_translation_gist_client_id == limited_client_id))).all()

        else:
            dbdicts = DBSession.query(dbDictionary).all()

        dictionaries_list = [Dictionary(id=[dbdict.client_id, dbdict.object_id]) for dbdict in dbdicts]
        return dictionaries_list

    def resolve_dictionary(self, args, context, info):
        id = args.get('id')
        return Dictionary(id=id)

    def resolve_perspective(self, args, context, info):
        id = args.get('id')
        return Perspective(id=id)

    def resolve_language(self, args, context, info):
        id = args.get('id')
        return Language(id=id)

    def resolve_entity(self, args, context, info):
        id = args.get('id')
        return Entity(id=id)

schema = graphene.Schema(query=Query)
