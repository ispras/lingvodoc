
# Standard library imports.

import ast
import collections
import datetime
import logging
import pdb
import pprint
import traceback

# External imports.

from pyramid.view import view_config

from sqlalchemy import and_, func
from sqlalchemy.orm import aliased

# Lingvodoc imports.

from lingvodoc.models import (
    Client,
    DBSession,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    Field,
    LexicalEntry,
    TranslationAtom,
    TranslationGist,
)

from lingvodoc.views.v2.utils import message, unimplemented


log = logging.getLogger(__name__)


@view_config(route_name = 'stat_perspective', renderer = 'json')
def stat_perspective(request):
    """
    Gathers user participation statistics for a specified perspective in a given time interval
    [time_begin, time_end).

    Parameters 'time_begin' and 'time_end' are Unix timestamps and are specified by
    URL parameters 'time_begin', 'time_end' as either YYYY-MM-DDtHH:MM:SS-formatted dates or Unix timestamps
    as Python numeric literals.
    """

    log.debug('stat_perspective')
    return {'error': unimplemented()}

    try:

        perspective_client_id = request.matchdict.get('perspective_client_id')
        perspective_object_id = request.matchdict.get('perspective_object_id')

        def try_parse_datetime(time_string):
            """
            Tries to parse a time instance specified as either YYYY-MM-DDtHH:MM:SS-formatted date or Unix
            timestamp as Python numeric literal.

            Returns datetime object with UTC timezone if succeeds and None otherwise.
            """

            try:
                return datetime.datetime.strptime(time_string, "%Y-%m-%dt%H:%M:%S")
            except ValueError:
                pass

            try:
                return datetime.datetime.utcfromtimestamp(ast.literal_eval(time_string))
            except SyntaxError:
                pass

            return None

        # Trying to determine time interval.

        time_begin_string = request.params.get('time_begin')
        time_begin = try_parse_datetime(time_begin_string)

        if time_begin is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_begin_string))}

        time_end_string = request.params.get('time_end')
        time_end = try_parse_datetime(time_end_string)

        if time_end is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_end_string))}

        log.debug('stat_perspective {0}/{1} from \'{2}\' to \'{3}\''.format(
            perspective_client_id, perspective_client_id,
            time_begin.isoformat(' '),
            time_end.isoformat(' ')))

        # Ok, now working, starting with perspective check.

        perspective = DBSession.query(DictionaryPerspective).filter_by(
            client_id = perspective_client_id,
            object_id = perspective_object_id).first()

        if not perspective:
            return {'error': message('No such perspective {0}/{1}.'.format(
                perspective_client_id, perspective_object_id))}

        user_data_dict = collections.defaultdict(collections.Counter)

        # Counting lexical entries.

#       entry_created_at = func.coalesce(
#           LexicalEntry.additional_metadata['merge']['min_created_at'],
#           extract('epoch', LexicalEntry.created_at))

#       entry_client_id = func.coalesce(
#           LexicalEntry.additional_metadata['merge']['original_client_id'],
#           LexicalEntry.client_id)

#       entry_query = DBSession.query(
#           entry_created_at.label('entry_created_at'),
#           entry_client_id.label('entry_client_id')).filter(and_(
#               LexicalEntry.parent_client_id == perspective_client_id,
#               LexicalEntry.parent_object_id == perspective_object_id,
#               LexicalEntry.marked_for_deletion == False,
#               entry_created_at >= time_begin,
#               entry_created_at < time_end)).all()

#       entry_count_query = DBSession.query(
#           LexicalEntry.client_id, func.count('*').label('entry_count')).filter(and_(
#               LexicalEntry.parent_client_id == perspective_client_id,
#               LexicalEntry.parent_object_id == perspective_object_id,
#               LexicalEntry.marked_for_deletion == False,
#               LexicalEntry.created_at >= time_begin,
#               LexicalEntry.created_at < time_end)).group_by(LexicalEntry.client_id).subquery()

#       entry_count_list = DBSession.query(
#           Client.id, Client.user_id, Client.is_browser_client, entry_count_query.c.entry_count).join(
#               entry_count_query, Client.id == entry_count_query.c.client_id).all()

#       for client_id, user_id, is_browser, entry_count in entry_count_list:
#           client_string = 'web' if is_browser else 'desktop'

#           user_data_dict[user_id][(client_id, client_string, 'lexical entity')] += entry_count

        # Getting perspective's field data.

        locale_id = int(request.cookies.get('locale_id') or 2)

#       FieldNameGist = aliased(TranslationGist)
#       FieldNameAtom = aliased(TranslationAtom)
#       FieldTypeNameGist = aliased(TranslationGist)
#       FieldTypeNameAtom = aliased(TranslationAtom)

        field_data_list = DBSession.query(Field).filter(and_(
            DictionaryPerspectiveToField.parent_client_id == perspective_client_id,
            DictionaryPerspectiveToField.parent_object_id == perspective_object_id,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.client_id == DictionaryPerspectiveToField.field_client_id,
            Field.object_id == DictionaryPerspectiveToField.field_object_id,
            Field.marked_for_deletion == False)).all()

#           FieldNameGist.client_id == Field.translation_gist_client_id,
#           FieldNameGist.object_id == Field.translation_gist_object_id,
#           FieldNameGist.marked_for_deletion == False,
#           FieldNameAtom.parent_client_id == FieldNameGist.client_id,
#           FieldNameAtom.parent_client_id == FieldNameGist.client_id,
#           FieldNameAtom.marked_for_deletion == False,
#           FieldNameAtom.locale_id == locale_id,
#           FieldTypeNameGist.client_id == Field.data_type_translation_gist_client_id,
#           FieldTypeNameGist.object_id == Field.data_type_translation_gist_object_id,
#           FieldTypeNameGist.marked_for_deletion == False,
#           FieldTypeNameAtom.parent_client_id == FieldTypeNameGist.client_id,
#           FieldTypeNameAtom.parent_client_id == FieldTypeNameGist.client_id,
#           FieldTypeNameAtom.marked_for_deletion == False,
#           FieldTypeNameAtom.locale_id == 2)).count()

        simple_type_set = set(['image', 'link', 'markup', 'sound', 'text'])

        for field in field_data_list:
            if field.data_type.lower() in simple_type_set:

                entity_count_query = DBSession.query(
                    Entity.client_id, func.count('*').label('entity_count')).filter(and_(
                        Entity.parent_client_id == perspective_client_id,
                        Entity.parent_object_id == perspective_object_id,
                        Entity.marked_for_deletion == False,
                        Entity.created_at >= time_begin,
                        Entity.created_at < time_end)).group_by(Entity.client_id).subquery()

            else:
                return {'error': unimplemented()}

        return {'error': unimplemented()}

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('stat_perspective: exception')
        log.debug('\n' + traceback_string)

        return {'error': message('\n' + traceback_string)}

