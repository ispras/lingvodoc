from lingvodoc.models import (
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession)
#from lingvodoc.views.v2.translations import translationgist_contents


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


def recursive_sort(langs, visited, stack, result):
    for lang in langs:
        parent = (lang.parent_client_id, lang.parent_object_id)
        if parent == (None, None):
            parent = None
        previous = None
        siblings = None
        if 'younger_siblings' in lang.additional_metadata:
            siblings = lang.additional_metadata['younger_siblings']
        if siblings:
            previous = siblings[len(siblings) - 1]
            previous = tuple(previous)
        ids = (lang.client_id, lang.object_id)
        if (not parent or parent in visited) and (not previous or previous in visited) and ids not in visited:
            level = 0
            if previous:
                subres = [(res[1], res[2]) for res in result]
                index = subres.index(previous)
                level = result[index][0]
                limit = len(result)
                while index < limit:
                    if result[index][0] < level:
                        index = index - 1
                        break
                    index += 1

                result.insert(index + 1,
                              [level, lang.client_id, lang.object_id, lang])

            elif parent and previous is None:
                subres = [(res[1], res[2]) for res in result]
                index = subres.index(parent)
                level = result[index][0] + 1
                result.insert(index + 1,
                              [level, lang.client_id, lang.object_id, lang])
            else:
                result.append([level, lang.client_id, lang.object_id, lang])

            visited.add(ids)

            if lang in stack:
                stack.remove(lang)

            recursive_sort(list(stack), visited, stack, result)
        else:
            stack.add(lang)
    return
