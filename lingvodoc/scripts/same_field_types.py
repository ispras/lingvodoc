from ..models import (
    DBSession,
    Field,
    TranslationAtom
)
from sqlalchemy import and_, exc
import logging

DEFAULT_LOCALE_ID = 1

log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)


def get_fields_data(session):
    """
    Obtaining Field table with all translations(TranslationAtom)
    of it's name from DB session and returning it as:

        dict {
            (client_id, object_id): dict {
                'field': models.Field,
                'translations': dict {
                    locale_id: models.TranslationAtom,
                    ...
                }
            },
            ...
        }

    """

    query = session.query(Field, TranslationAtom)
    query = query.join(TranslationAtom, and_(TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                                         TranslationAtom.parent_object_id == Field.translation_gist_object_id))
    query = query.filter(Field.marked_for_deletion == False)

    fields_data = dict()
    try:
        for data in query.all():

            field_id = (data.Field.client_id, data.Field.object_id)

            if not fields_data.get(field_id, None):
                fields_data[field_id] = {
                    'field': data.Field,
                    'translations': dict()
                }
            fields_data[field_id]['translations'][data.TranslationAtom.locale_id] = data.TranslationAtom
    except exc.SQLAlchemyError as ex:
        log.warning('Failed to obtain fields_data at ' + __name__)
        log.warning(ex)

    return fields_data


def field_distribution_by_locale(session=DBSession, locale_id = DEFAULT_LOCALE_ID):
    '''
    Returning Fields with all translations grouped by Field's data type
    name and Field's translation from chosen locale (field_hash as a whole)

        dict {
            field_hash: dict {
                'field': models.Field
                'translations': dict {
                    locale_id: models.TranslationAtom,
                    ...
                }
            }
            ...
        }

    '''

    fields_data = get_fields_data(session)
    field_dst = dict()

    for field_id in fields_data:
        # field_hash = (fields[field_id]['type_id'], fields[field_id]['translations'].get(locale_id, ''))
        translation = fields_data[field_id]['translations'].get(locale_id, None)
        if translation:
            field_hash = (fields_data[field_id]['field'].data_type_translation_gist_client_id,
                          fields_data[field_id]['field'].data_type_translation_gist_object_id,
                          translation.content)
            if not field_dst.get(field_hash, None):
                field_dst[field_hash] = []
            data = fields_data[field_id]
            field_dst[field_hash].append(data)

    return field_dst


def same_locale_fields(session=DBSession, locale_id = DEFAULT_LOCALE_ID):
    '''
    Returning groupings of similar Fields based on their name
    in chosen locale and data type

        list [
            list [
                dict {
                    'field': models.Field
                    'translations': dict {
                        locale_id: models.TranslationAtom,
                        ...
                    }
                },
                ...
            ],
            ...
        ]

    '''
    field_dst = field_distribution_by_locale(session, locale_id)
    res = []

    for field_hash in field_dst:
        if len(field_dst[field_hash]) > 1:
            res.append([data for data in field_dst[field_hash]])

    return res


def translations_r_cmp(tr_a, tr_b):
    for locale_id in tr_a:
        tmp = tr_b.get(locale_id, None)
        if not tmp or tr_a[locale_id].content != tmp.content:
            return False
    return True


def fields_cmp(data_a, data_b):
    tr_a = data_a['translations']
    tr_b = data_b['translations']
    return translations_r_cmp(tr_a, tr_b) and translations_r_cmp(tr_b, tr_a) and\
           data_a['field'].data_type_translation_gist_object_id == data_b['field'].data_type_translation_gist_object_id and \
           data_a['field'].data_type_translation_gist_client_id == data_b['field'].data_type_translation_gist_client_id


def exact_same_fields(session=DBSession):
    '''
    Returning groupings of Fields with completely
    identical names and data types

        list [
            list [
                dict {
                    'field': models.Field
                    'translations': dict {
                        locale_id: models.TranslationAtom,
                        ...
                    }
                },
                ...
            ],
            ...
        ]

    '''
    field_dst = field_distribution_by_locale(session)
    res = []

    for field_hash in field_dst:
        tmp_list = []
        for i in range(0, len(field_dst[field_hash])):
            unique_field_flag = True
            for idx_list in tmp_list:

                if fields_cmp(field_dst[field_hash][i], field_dst[field_hash][idx_list[0]]):
                    idx_list.append(i)
                    unique_field_flag = False

            if unique_field_flag:
                tmp_list.append([i])

        for idx_list in tmp_list:
            if len(idx_list) > 1:
                res.append([field_dst[field_hash][idx] for idx in idx_list])

    return res
