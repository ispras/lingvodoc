from lingvodoc.schema.gql_translationgist import (
    TranslationGist
)

from lingvodoc.models import (
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession
)
def translation_gist_search(searchstring):
        translationatom = DBSession.query(dbTranslationAtom) \
            .join(dbTranslationGist). \
            filter(dbTranslationAtom.content == searchstring,
                   dbTranslationAtom.locale_id == 2,
                   dbTranslationGist.type == 'Service') \
            .first()

        if translationatom and translationatom.parent:
            translationgist = translationatom.parent

            # translationatoms_list = list()
            # for translationatom in translationgist.translationatom:
            #     translationatoms_list.append(translationatom)
            # translationgist_object = TranslationGist(id=[translationgist.client_id, translationgist.object_id],
            #                                          type=translationgist.type,
            #                                          created_at=translationgist.created_at,
            #                                          translationatoms=translationatoms_list)
            return translationgist