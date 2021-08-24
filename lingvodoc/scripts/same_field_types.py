from ..models import (
    DBSession,
    Field,
    TranslationAtom,
    DictionaryPerspectiveToField,
    Entity
)
from sqlalchemy import and_, exc
import transaction
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


def _equal_translations_r(tr_a, tr_b):
    for locale_id in tr_a:
        tmp = tr_b.get(locale_id, None)
        if not tmp or tr_a[locale_id].content != tmp.content:
            return False
    return True


def _equal_field_types(field_a, field_b):
    return field_a.data_type_translation_gist_object_id == field_b.data_type_translation_gist_object_id and \
           field_a.data_type_translation_gist_client_id == field_b.data_type_translation_gist_client_id


def _equal_fields(data_a, data_b):
    tr_a = data_a['translations']
    tr_b = data_b['translations']
    fld_a = data_a['field']
    fld_b = data_b['field']

    return _equal_translations_r(tr_a, tr_b) and\
        _equal_translations_r(tr_b, tr_a) and\
        _equal_field_types(fld_a, fld_b)


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

                if _equal_fields(field_dst[field_hash][i], field_dst[field_hash][idx_list[0]]):
                    idx_list.append(i)
                    unique_field_flag = False

            if unique_field_flag:
                tmp_list.append([i])

        for idx_list in tmp_list:
            if len(idx_list) > 1:
                res.append([field_dst[field_hash][idx] for idx in idx_list])

    return res


def _collapse_field_in_table(from_field, to_field, table, session, commit=False):
    session.query(table) \
        .filter(and_(table.field_client_id == from_field['client_id'],
                     table.field_object_id == from_field['object_id'])) \
        .update({'field_client_id': to_field['client_id'], 'field_object_id': to_field['object_id']})

    if commit:
        transaction.commit()


def collapse_field(from_field, to_field, session=DBSession, commit=False):
    '''
    from_field and to_field are:
        dict {
            'client_id': int,
            'object_id': int
        }

    By the end of function execution every use of from_field in database
    will be replaced by to_field, from_field will be marked for deletion
    '''

    try:
        log.info('Collapse of field (' + str(from_field['client_id']) + ', ' + str(from_field['object_id']) +
                 ') to_field (' + str(to_field['client_id']) + ', ' + str(to_field['object_id']) +
                 ') started at ' + __name__)

        _collapse_field_in_table(from_field, to_field, table=DictionaryPerspectiveToField,
                                 session=session, commit=False)

        _collapse_field_in_table(from_field, to_field, table=Entity,
                                 session=session, commit=False)

        session.query(Field).filter(and_(Field.client_id == from_field['client_id'],
                                         Field.object_id == from_field['object_id']))\
            .update({'marked_for_deletion': True})

        if commit:
            log.info('Successful field collapse at ' + __name__)
            transaction.commit()

    except exc.SQLAlchemyError as ex:
        log.warning('Failed to collapse field (' + str(from_field['client_id']) + ', ' +
                    str(from_field['object_id']) + ') to_field (' + str(to_field['client_id']) +
                    ', ' + str(to_field['object_id']) + ') at ' + __name__)
        log.warning(ex)

        if commit:
            transaction.abort()


def collapse_field_mapping(field_mapping, session=DBSession, commit_all_at_once=False):
    '''
    field_mapping is:
        list [
            dict {
                'from': dict {
                        'client_id': int,
                        'object_id': int
                    },
                'to': dict {
                        'client_id': int,
                        'object_id': int
                    }
            },
            ...
        ]

    By the end of function execution every use of 'from' fields in database
    will be replaced by 'to' fields, 'from' fields will be marked for deletion
    '''
    try:
        for field_pair in field_mapping:
            from_field = field_pair['from']
            to_field = field_pair['to']
            collapse_field(from_field, to_field, session, not commit_all_at_once)

        if commit_all_at_once:
            transaction.commit()

    except exc.SQLAlchemyError as ex:
        log.warning('Failed to collapse field mapping at ' + __name__)
        log.warning(ex)

        if commit_all_at_once:
            transaction.abort()


def generate_field_mapping(field_groups):
    '''
    Returns mapping for collapse_field_mapping made from field groups:
        list [
            dict {
                'from': dict {
                        'client_id': int,
                        'object_id': int
                    },
                'to': dict {
                        'client_id': int,
                        'object_id': int
                    }
            },
            ...
        ]
    '''
    res = []
    for group in field_groups:
        earliest_date = group[0]['field'].created_at
        earliest_idx = 0
        for i in range(0, len(group)):
            if earliest_date > group[i]['field'].created_at:
                earliest_date = group[i]['field'].created_at
                earliest_idx = i

        to_field = {'client_id': group[earliest_idx]['field'].client_id,
                    'object_id': group[earliest_idx]['field'].object_id}

        for i in range(0, len(group)):
            if i != earliest_idx:
                res.append({
                    'from': {
                        'client_id': group[i]['field'].client_id,
                        'object_id': group[i]['field'].object_id
                    },
                    'to': to_field
                })

    return res
