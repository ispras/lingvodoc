import logging
import argparse
import sys

from lingvodoc.models import (
    DBSession,
    Field,
    TranslationAtom,
    DictionaryPerspectiveToField,
    Entity
)
import transaction

from sqlalchemy import and_, exc
from pyramid.paster import bootstrap, setup_logging

DEFAULT_LOCALE_ID = 1

log = logging.getLogger(__name__)
stream = logging.StreamHandler()
log.addHandler(stream)


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


def _collapse_field_in_table(from_field, to_field, table, session):
    session.query(table) \
        .filter(and_(table.field_client_id == from_field['client_id'],
                     table.field_object_id == from_field['object_id'])) \
        .update({'field_client_id': to_field['client_id'], 'field_object_id': to_field['object_id']})


def collapse_field(from_field, to_field, session=DBSession):
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
                                 session=session)

        _collapse_field_in_table(from_field, to_field, table=Entity,
                                 session=session)

        session.query(Field).filter(and_(Field.client_id == from_field['client_id'],
                                         Field.object_id == from_field['object_id']))\
            .update({'marked_for_deletion': True})


    except exc.SQLAlchemyError as ex:
        log.warning('Failed to collapse field (' + str(from_field['client_id']) + ', ' +
                    str(from_field['object_id']) + ') to_field (' + str(to_field['client_id']) +
                    ', ' + str(to_field['object_id']) + ') at ' + __name__)
        log.warning(ex)
        raise


def collapse_field_mapping(field_mapping, session=DBSession):
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
            collapse_field(from_field, to_field, session)

    except exc.SQLAlchemyError as ex:
        log.warning('Failed to collapse field mapping at ' + __name__)
        log.warning(ex)
        raise


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


# Just some handy string converters
def _str_field_data(field_data, sep=' ', end=''):
    return str(field_data['field'].client_id) + sep + str(field_data['field'].object_id) + sep +\
            str(field_data['field'].created_at) + sep + '|' + sep + ' '.join([str(i) + ' '  +\
            str(field_data['translations'][i].content) for i in field_data['translations']]) + end


def _str_fields_data_dict(fields_data_dict, sep='\n\t', end='\n'):
    res = ''
    for field_data_id in fields_data_dict:
        res += str(field_data_id) + sep + _str_field_data(fields_data_dict[field_data_id], sep=' ', end=sep)
    res += end
    return res


def _str_fields_data_list(fields_data_list, sep='\n', end='\n'):
    res = ''
    for data in fields_data_list:
        res += _str_field_data(data, sep=' ', end=sep)
    res += end
    return res


def _str_field_dst(field_dst):
    res = ''
    for field_hash in field_dst:
        res += str(field_hash) + '\n\t' + _str_fields_data_list(field_dst[field_hash], sep='\n\t')
    return res


def _str_same_fields(res):
    str_res = ''
    for l in res:
        str_res += _str_fields_data_list(l)
    return str_res


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'config_uri',
        help='Configuration file, e.g., development.ini',
    )
    return parser.parse_args(argv[1:])


def main(argv=None):
    if argv is None:
        argv = sys.argv

    mapping = [
        {
            'from': {'client_id': 3924, 'object_id': 5},
            'to': {'client_id': 66, 'object_id': 12}
        }, {
            'from': {'client_id': 3924, 'object_id': 8},
            'to': {'client_id': 66, 'object_id': 12}
        }, {
            'from': {'client_id': 3924, 'object_id': 11},
            'to': {'client_id': 66, 'object_id': 12}
        }, {
            'from': {'client_id': 3924, 'object_id': 180},
            'to': {'client_id': 66, 'object_id': 12}
        }, {
            'from': {'client_id': 3924, 'object_id': 183},
            'to': {'client_id': 66, 'object_id': 12}
        }, {
            'from': {'client_id': 1244, 'object_id': 119},
            'to': {'client_id': 66, 'object_id': 8}
        }, {
            'from': {'client_id': 671, 'object_id': 14204},
            'to': {'client_id': 66, 'object_id': 8}
        }, {
            'from': {'client_id': 1207, 'object_id': 382},
            'to': {'client_id': 1072, 'object_id': 21}
        }, {
            'from': {'client_id': 1327, 'object_id': 4},
            'to': {'client_id': 1321, 'object_id': 9}
        }, {
            'from': {'client_id': 1347, 'object_id': 4},
            'to': {'client_id': 1346, 'object_id': 7}
        }, {
            'from': {'client_id': 1346, 'object_id': 31},
            'to': {'client_id': 1346, 'object_id': 10}
        }, {
            'from': {'client_id': 1346, 'object_id': 154},
            'to': {'client_id': 1346, 'object_id': 148}
        }, {
            'from': {'client_id': 1346, 'object_id': 70},
            'to': {'client_id': 1346, 'object_id': 67}
        }, {
            'from': {'client_id': 1346, 'object_id': 142},
            'to': {'client_id': 1346, 'object_id': 139}
        }, {
            'from': {'client_id': 2187, 'object_id': 37},
            'to': {'client_id': 2187, 'object_id': 27}
        }, {
            'from': {'client_id': 1479, 'object_id': 796},
            'to': {'client_id': 1479, 'object_id': 793}
        }, {
            'from': {'client_id': 1589, 'object_id': 13},
            'to': {'client_id': 1589, 'object_id': 10}
        }, {
            'from': {'client_id': 3498, 'object_id': 5},
            'to': {'client_id': 2888, 'object_id': 10}
        }, {
            'from': {'client_id': 3924, 'object_id': 141},
            'to': {'client_id': 66, 'object_id': 6}
        }, {
            'from': {'client_id': 3924, 'object_id': 144},
            'to': {'client_id': 66, 'object_id': 6}
        }, {
            'from': {'client_id': 3924, 'object_id': 147},
            'to': {'client_id': 66, 'object_id': 6}
        }, {
            'from': {'client_id': 3924, 'object_id': 150},
            'to': {'client_id': 66, 'object_id': 6}
        }, {
            'from': {'client_id': 3924, 'object_id': 156},
            'to': {'client_id': 3924, 'object_id': 153}
        }, {
            'from': {'client_id': 3924, 'object_id': 159},
            'to': {'client_id': 3924, 'object_id': 153}
        }, {
            'from': {'client_id': 3924, 'object_id': 162},
            'to': {'client_id': 3924, 'object_id': 153}
        }, {
            'from': {'client_id': 3924, 'object_id': 165},
            'to': {'client_id': 3924, 'object_id': 153}
        }, {
            'from': {'client_id': 3924, 'object_id': 173},
            'to': {'client_id': 3924, 'object_id': 153}
        }, {
            'from': {'client_id': 3924, 'object_id': 177},
            'to': {'client_id': 3924, 'object_id': 153}
        }, {
            'from': {'client_id': 3924, 'object_id': 169},
            'to': {'client_id': 3924, 'object_id': 153}
        }, {
            'from': {'client_id': 1643, 'object_id': 166},
            'to': {'client_id': 66, 'object_id': 6}
        }, {
            'from': {'client_id': 748, 'object_id': 1392},
            'to': {'client_id': 66, 'object_id': 6}
        }, {
            'from': {'client_id': 1349, 'object_id': 73},
            'to': {'client_id': 2187, 'object_id': 4}
        }, {
            'from': {'client_id': 2187, 'object_id': 27},
            'to': {'client_id': 2187, 'object_id': 4}
        }, {
            'from': {'client_id': 748, 'object_id': 1397},
            'to': {'client_id': 1, 'object_id': 212}
        }, {
            'from': {'client_id': 1642, 'object_id': 540},
            'to': {'client_id': 1642, 'object_id': 537}
        }, {
            'from': {'client_id': 3498, 'object_id': 58},
            'to': {'client_id': 3498, 'object_id': 13}
        }, {
            'from': {'client_id': 3498, 'object_id': 54},
            'to': {'client_id': 3498, 'object_id': 17}
        }, {
            'from': {'client_id': 1372, 'object_id': 9103},
            'to': {'client_id': 1207, 'object_id': 385}
        }
    ]

    args = parse_args(argv)
    #setup_logging(args.config_uri)
    env = bootstrap(args.config_uri)

    log.setLevel(logging.INFO)
    stream.setLevel(logging.INFO)

    # Logging info about fields marked for collapse and fields intact
    session = DBSession
    fields_dict = get_fields_data(session)

    fields_log_list = []
    for field_id in fields_dict:
        flag = False
        for d in mapping:
            if field_id[0] == d['from']['client_id'] and field_id[1] == d['from']['object_id']:
                flag = True
                break
        if not flag:
            fields_log_list.append(('[intact] ', fields_dict[field_id]))
        else:
            fields_log_list.append(('[marked] ', fields_dict[field_id]))

    def field_data_locale_key(x):
        tmp = x[1]['translations'].get(DEFAULT_LOCALE_ID, None)
        if not tmp:
            return ' '
        return tmp.content

    fields_log_list.sort(key=field_data_locale_key)
    log.info('\nMarked fields will be deleted')
    for f in fields_log_list:
        log.info(f[0] + _str_field_data(f[1]))

    log.info('\nLogging field mapping info:')
    for pair in mapping:
        log.info('from: ' + _str_field_data(fields_dict[(pair['from']['client_id'], pair['from']['object_id'])]) + '\n'\
                 + 'to:   ' + _str_field_data(fields_dict[(pair['to']['client_id'], pair['to']['object_id'])]) + '\n')
    # End of logging

    #try:
    #    collapse_field_mapping(mapping, session)
    #except exc.SQLAlchemyError as ex:
    #    log.warning('Failed to collapse fields at ' + __name__)
    #    log.warning(ex)
    #
    #    transaction.abort()
    #else:
    #    transaction.commit()


if __name__ == '__main__':
    main()
