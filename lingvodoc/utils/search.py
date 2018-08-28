import json

import pympi
from lingvodoc.models import (
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    LexicalEntry as dbLexicalEntry,
    Entity as dbEntity,
    PublishingEntity as dbPublishingEntity,
    Field as dbField,
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

def eaf_words(eaf_obj):
    annotations = list()
    for tier in eaf_obj.tiers:
        if not eaf_obj.tiers[tier][1]:
            a = eaf_obj.tiers[tier][0]
            ann_data = [a[b][2]
                for b in a]
            ann_list = [x.lower() for x in ann_data]
            annotations += ann_list

        if eaf_obj.tiers[tier][1]:
            ann_data = []
            for aid, (ref, value, prev, _) in eaf_obj.tiers[tier][1].items():
                tier_data = eaf_obj.tiers[eaf_obj.annotations[ref]]
                if ref in tier_data[0]:
                    ann_data.append(value)
                if ref in tier_data[1]:
                    ann_data.append(value)
            ref_ann_list = [x.lower() for x in ann_data]
            annotations += ref_ann_list
        #for ann in ann_list + ref_ann_list:
        #    annotations.add(ann)
    annotations = set(annotations)
    return annotations

# auxiliary function for filling simplified permissions. Gets python dictionary, Perspective object and a list of pairs
# [("permission": boolean), ]
def fulfill_permissions_on_perspectives(intermediate, perspective, pairs):
    cl_id = str(perspective.client_id)
    obj_id = str(perspective.object_id)
    if cl_id not in intermediate:
        intermediate[cl_id] = dict()
    if obj_id not in intermediate[cl_id]:
        intermediate[cl_id][obj_id] = dict()
    for permission in pairs:
        intermediate[cl_id][obj_id][permission[0]] = permission[1]
    return




class FakeObject(object):
    pass



def find_lexical_entries_by_tags(tags, field_client_id, field_object_id, accepted, published=None):
    result = DBSession.query(dbLexicalEntry) \
        .join(dbLexicalEntry.entity) \
        .join(dbEntity.publishingentity) \
        .join(dbEntity.field) \
        .filter(dbEntity.content.in_(tags),
                dbEntity.marked_for_deletion == False,
                dbField.client_id == field_client_id,
                dbField.object_id == field_object_id)
    if accepted:
        result = result.filter(dbPublishingEntity.accepted == True)
    if published:
        result = result.filter(dbPublishingEntity.published == True)
    result = result.all()
    return result


def find_all_tags(lexical_entry, field_client_id, field_object_id, accepted, published=None):
    tag = None
    for entity in lexical_entry.entity:
        if not entity.marked_for_deletion and entity.field_client_id == field_client_id and entity.field_object_id == field_object_id:
            if accepted:
                if not entity.publishingentity.accepted:
                    continue
            if published:
                if not entity.publishingentity.published:
                    continue
            tag = entity.content
            break
    if not tag:
        return set()
    else:
        tags = {tag}
        new_tags =  {tag}
        while new_tags:
            lexical_entries = find_lexical_entries_by_tags(new_tags, field_client_id, field_object_id, accepted, published)
            new_tags = set()
            for lex in lexical_entries:
                entities = DBSession.query(dbEntity) \
                    .join(dbEntity.field) \
                    .join(dbEntity.publishingentity) \
                    .filter(dbEntity.parent == lex,
                            dbField.client_id == field_client_id,
                            dbField.object_id == field_object_id,
                            dbEntity.marked_for_deletion==False)
                if accepted:
                    entities = entities.filter(dbPublishingEntity.accepted == True)
                if published:
                    entities = entities.filter(dbPublishingEntity.published == True)

                entities = entities.all()
                for entity in entities:
                    if entity.content not in tags:
                        tags.add(entity.content)
                        new_tags.add(entity.content)
        return tags

def get_id_to_field_dict():
    with open('static_fields.json') as f:
        dict_with_lists = json.load(f)
        dict_with_tuples = {k: tuple(v) for k, v in dict_with_lists.items()}
        return dict_with_tuples
