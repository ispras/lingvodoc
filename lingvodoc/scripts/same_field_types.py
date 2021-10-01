import logging
import argparse
import sys
import csv
from datetime import datetime

from lingvodoc.models import (
    DBSession,
    Field,
    TranslationAtom,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    LexicalEntry,
    Entity
)
import transaction

from sqlalchemy import and_, exc, func, tuple_
from pyramid.paster import bootstrap, setup_logging

DEFAULT_LOCALE_ID = 1

log = logging.getLogger(__name__)
stream = logging.StreamHandler()
log.addHandler(stream)


def get_fields_translation_data(session=DBSession):
    """
    Obtaining Field table with all translations(TranslationAtom)
    of it's name from DB session and returning it as:

        dict {
            (client_id, object_id): dict {
                'field': models.Field,
                'translations': dict {
                    (int) locale_id: models.TranslationAtom,
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
        log.warning('Failed to obtain fields translation data at ' + __name__)
        log.warning(ex)

    return fields_data


def _field_distribution_by_locale(session, locale_id=DEFAULT_LOCALE_ID):
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

    fields_data = get_fields_translation_data(session)
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


def same_locale_fields(session=DBSession, locale_id=DEFAULT_LOCALE_ID):
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
    field_dst = _field_distribution_by_locale(session, locale_id)
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

    return _equal_translations_r(tr_a, tr_b) and \
           _equal_translations_r(tr_b, tr_a) and \
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
    field_dst = _field_distribution_by_locale(session)
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


def _collapse_field(from_field, to_field, session):
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

        session.query(DictionaryPerspectiveToField) \
            .filter(and_(DictionaryPerspectiveToField.field_client_id == from_field['client_id'],
                         DictionaryPerspectiveToField.field_object_id == from_field['object_id'])) \
            .update(
            {
                'field_client_id': to_field['client_id'],
                'field_object_id': to_field['object_id']
            }
        )

        session.query(Entity) \
            .filter(and_(Entity.field_client_id == from_field['client_id'],
                         Entity.field_object_id == from_field['object_id'])) \
            .update(
            {
                'field_client_id': to_field['client_id'],
                'field_object_id': to_field['object_id'],
                'additional_metadata': {
                    'merged_from_field': [from_field['client_id'], from_field['object_id']]
                }
            }
        )

        session.query(Field).filter(and_(Field.client_id == from_field['client_id'],
                                         Field.object_id == from_field['object_id'])) \
            .update(
            {
                'marked_for_deletion': True,
                'additional_metadata': {
                    'merged_from_field': [to_field['client_id'], to_field['object_id']]
                }
            }
        )


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
            _collapse_field(from_field, to_field, session)

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
    res = str(field_data['field'].client_id) + sep + \
          str(field_data['field'].object_id) + sep + \
          datetime.utcfromtimestamp(field_data['field'].created_at).strftime('%Y-%m-%d %H:%M:%S') + sep + \
          '|' + sep + \
          ' '.join([str(i) + ' ' + str(field_data['translations'][i].content) for i in field_data['translations']]) + \
          end
    if field_data.get('merged_to', None) is None:
        res = '[intact] ' + res
    else:
        res = '[merged] ' + res
    return res


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


def _mark_fields_transl_dict(fields_transl_dict, mapping):
    for field_id in fields_transl_dict:
        flag = False
        merged_to_id = 0
        for d in mapping:
            if field_id[0] == d['from']['client_id'] and field_id[1] == d['from']['object_id']:
                flag = True
                merged_to_id = (d['to']['client_id'], d['to']['object_id'])
                break
        if flag:
            fields_transl_dict[field_id]['merged_to'] = merged_to_id


def log_field_info(mapping, session=DBSession):
    fields_transl_dict = get_fields_translation_data(session)
    _mark_fields_transl_dict(fields_transl_dict, mapping)

    def field_data_locale_key(x):
        tmp = x['translations'].get(DEFAULT_LOCALE_ID, None)
        if not tmp:
            return ' '
        return tmp.content

    fields_log_list = [fields_transl_dict[key] for key in fields_transl_dict]
    fields_log_list.sort(key=field_data_locale_key)
    log.info('\nMarked fields will be deleted')
    for f in fields_log_list:
        log.info(_str_field_data(f))

    log.info('\nLogging field mapping info:')
    for pair in mapping:
        from_id = (pair['from']['client_id'], pair['from']['object_id'])
        to_id = (pair['to']['client_id'], pair['to']['object_id'])
        from_field = fields_transl_dict.get(from_id, None)
        to_field = fields_transl_dict.get(to_id, None)
        if from_field and to_field:
            log.info('from: ' + _str_field_data(from_field) + '\n' \
                     + 'to:   ' + _str_field_data(to_field) + '\n')
        else:
            if not from_field:
                log.info('Could not obtain field ' + str(from_id))
            if not to_field:
                log.info('Could no obtain field ' + str(to_id) + '\n')


def _dictionary_perspective_url(client_id, object_id):
    return 'http://lingvodoc.ru/dictionary/1/1/perspective/' + str(client_id) + '/' + str(object_id) + '/view'


def _get_fields_usage_data(session):
    f_client_id = Field.client_id.label('field_client_id')
    f_object_id = Field.object_id.label('field_object_id')
    dp_client_id = DictionaryPerspective.client_id.label('dictionary_perspective_client_id')
    dp_object_id = DictionaryPerspective.object_id.label('dictionary_perspective_object_id')
    dp_marked_for_deletion = \
        DictionaryPerspective.marked_for_deletion.label('dictionary_perspective_marked_for_deletion')

    subquery = session.query(f_client_id, f_object_id, dp_client_id, dp_object_id, dp_marked_for_deletion)
    subquery = subquery.select_from(Field).join(DictionaryPerspectiveToField,
                                                and_(DictionaryPerspectiveToField.field_client_id == Field.client_id,
                                                     DictionaryPerspectiveToField.field_object_id == Field.object_id))
    subquery = subquery.filter(DictionaryPerspective.marked_for_deletion == False,
                                    Field.marked_for_deletion == False)
    subquery = subquery.join(DictionaryPerspective,
                             and_(DictionaryPerspectiveToField.parent_client_id == DictionaryPerspective.client_id,
                                  DictionaryPerspectiveToField.parent_object_id == DictionaryPerspective.object_id))
    subquery = subquery.distinct(Field.client_id, Field.object_id,
                                 DictionaryPerspective.client_id, DictionaryPerspective.object_id)
    subquery = subquery.order_by(Field.client_id, Field.object_id,
                                 DictionaryPerspective.client_id, DictionaryPerspective.object_id)

    log.info(subquery)

    fields_usage = dict()
    try:
        for data in subquery.all():
            field_id = (data.field_client_id, data.field_object_id)

            if not fields_usage.get(field_id, None):
                fields_usage[field_id] = {
                    'URLs': list(),
                    'metrics': {
                        'dp': {
                            'sum': 0,
                            'deleted': 0
                        },
                        'le': {
                            'sum': 0,
                            'deleted': 0
                        }
                    }
                }
            fields_usage[field_id]['URLs'].append(
                _dictionary_perspective_url(
                    data.dictionary_perspective_client_id, data.dictionary_perspective_object_id
                )
            )

    except exc.SQLAlchemyError as ex:
        log.warning('Failed to obtain fields usage URLs at ' + __name__)
        log.warning(ex)
        raise

    subquery = subquery.subquery('subquery')
    query = session.query('subquery.field_client_id', 'subquery.field_object_id',
                          func.count('*'), 'subquery.dictionary_perspective_marked_for_deletion')
    query = query.select_from(subquery).group_by('subquery.field_client_id',
                                                 'subquery.field_object_id',
                                                 'subquery.dictionary_perspective_marked_for_deletion')
    query = query.order_by('subquery.field_client_id', 'subquery.field_object_id')

    log.info(query)
    try:
        for data in query.all():
            usage = fields_usage.get((data[0], data[1]), None)
            if usage:
                if data[3]:
                    usage['metrics']['dp']['deleted'] += data[2]
                usage['metrics']['dp']['sum'] += data[2]

    except exc.SQLAlchemyError as ex:
        log.warning('Failed to obtain fields dictionary perspective metrics at ' + __name__)
        log.warning(ex)
        raise

    query = session.query('subquery.field_client_id', 'subquery.field_object_id',
                          func.count('*'), 'subquery.dictionary_perspective_marked_for_deletion')
    query = query.select_from(LexicalEntry)
    query = query.join(subquery, and_('subquery.dictionary_perspective_client_id = lexicalentry.parent_client_id',
                       'subquery.dictionary_perspective_object_id = lexicalentry.parent_object_id'))
    query = query.filter('lexicalentry.marked_for_deletion = false')
    query = query.group_by('subquery.field_client_id', 'subquery.field_object_id',
                           'subquery.dictionary_perspective_marked_for_deletion')

    log.info(query)
    try:
        for data in query.all():
            usage = fields_usage.get((data[0], data[1]), None)
            if usage:
                if data[3]:
                    usage['metrics']['le']['deleted'] += data[2]
                usage['metrics']['le']['sum'] += data[2]

    except exc.SQLAlchemyError as ex:
        log.warning('Failed to obtain fields lexical entry metrics at ' + __name__)
        log.warning(ex)
        raise

    return fields_usage


def log_csv_field_info(path, mapping, session=DBSession):
    fields_transl_dict = get_fields_translation_data(session)
    _mark_fields_transl_dict(fields_transl_dict, mapping)
    fields_usage_dict = _get_fields_usage_data(session)

    with open(path, 'w') as f:
        writer = csv.writer(f)

        locale_set = set()
        for field_id in fields_transl_dict:
            for locale in fields_transl_dict[field_id]['translations']:
                locale_set.add(locale)
        locale_list = sorted([*locale_set])
        locale_header = ['locale #' + str(x) for x in locale_list]

        header = ['id', 'merged_to', *locale_header, 'created_at', 'dict_perspective_count',
                  'lexical_entry_count', 'URLs']
        writer.writerow(header)

        none_str = '-'
        for field_id in fields_transl_dict:
            row = [str(field_id)]
            field_transl = fields_transl_dict[field_id]

            merged_to = field_transl.get('merged_to', None)
            if merged_to is None:
                row.append(none_str)
            else:
                row.append(str(merged_to))

            for locale in locale_list:
                translation = field_transl['translations'].get(locale, None)
                if translation is None:
                    row.append(none_str)
                else:
                    row.append(translation.content)

            row.append(datetime.utcfromtimestamp(
                field_transl['field'].created_at
            ).strftime('%Y-%m-%d %H:%M:%S'))

            field_usage = fields_usage_dict.get(field_id, None)
            if field_usage is None:
                row.append('0/0')
                row.append('0/0')
                row.append('')
            else:
                row.append(str(field_usage['metrics']['dp']['sum']) + '/' + str(field_usage['metrics']['dp']['deleted']))
                row.append(str(field_usage['metrics']['le']['sum']) + '/' + str(field_usage['metrics']['le']['deleted']))
                row.append(' '.join(field_usage['URLs'][:10:]))

            writer.writerow(row)


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
    # setup_logging(args.config_uri)
    env = bootstrap(args.config_uri)

    log.setLevel(logging.INFO)
    stream.setLevel(logging.INFO)

    session = DBSession

    # Logging info about fields marked for collapse and fields intact
    log_field_info(mapping, session)
    log_csv_field_info('/tmp/log.csv', mapping, session)

    # try:
    #     collapse_field_mapping(mapping, session)
    # except exc.SQLAlchemyError as ex:
    #     log.warning('Failed to collapse fields at ' + __name__)
    #     log.warning(ex)
    #
    #     transaction.abort()
    # else:
    #     transaction.commit()


if __name__ == '__main__':
    main()
