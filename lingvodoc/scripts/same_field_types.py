from ..models import (
    DBSession,
    Field,
    TranslationAtom,
    TranslationGist,
    CompositeIdMixin
)
from sqlalchemy import and_

DEFAULT_LOCALE_ID = 1


def get_fields_data(session):
    query = session.query(Field.client_id, Field.object_id, Field.data_type_translation_gist_client_id,
                        Field.data_type_translation_gist_object_id, TranslationAtom.locale_id,
                        TranslationAtom.content)
    query = query.join(TranslationAtom, and_(TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                                         TranslationAtom.parent_object_id == Field.translation_gist_object_id))
    query = query.filter(Field.marked_for_deletion == False)

    fields = dict()
    for res in query.all():
        field_id = (res.client_id, res.object_id)
        if not fields.get(field_id, None):
            fields[(res.client_id, res.object_id)] = {
                'type_id': (res.data_type_translation_gist_client_id, res.data_type_translation_gist_object_id),
                'translations': dict()
            }
        fields[field_id]['translations'][res.locale_id] = res.content
    return fields


def field_distribution_by_locale(session=DBSession, locale_id = DEFAULT_LOCALE_ID):
    fields = get_fields_data(session)
    field_dst = dict()

    for field_id in fields:
        field_hash = (fields[field_id]['type_id'], fields[field_id]['translations'].get(locale_id, ''))
        if not field_dst.get(field_hash, None):
            field_dst[field_hash] = []
        field_data = fields[field_id]
        field_data['id'] = field_id
        field_dst[field_hash].append(field_data)

    return field_dst


def same_locale_fields(session=DBSession, locale_id = DEFAULT_LOCALE_ID):
    field_dst = field_distribution_by_locale(session, locale_id)
    res = []

    for field_hash in field_dst:
        if len(field_dst[field_hash]) > 1:
            res.append([field['id'] for field in field_dst[field_hash]])

    return res


def exact_same_fields(session=DBSession):
    field_dst = field_distribution_by_locale(session)
    res = []

    for field_hash in field_dst:
        tmp_list = []
        for i in range(0, len(field_dst[field_hash])):
            unique_field_flag = True
            for idx_list in tmp_list:
                if field_dst[field_hash][i]['translations'] == field_dst[field_hash][idx_list[0]]['translations']:
                    idx_list.append(i)
                    unique_field_flag = False

            if unique_field_flag:
                tmp_list.append([i])

        for idx_list in tmp_list:
            if len(idx_list) > 1:
                res.append([field_dst[field_hash][idx]['id'] for idx in idx_list])

    return res
