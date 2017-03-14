
# Standard library imports.

import ast
import collections
import datetime
import io
import logging
import pdb
import pprint
import traceback

# External imports.

from pyramid.response import Response
from pyramid.view import view_config

from sqlalchemy import and_, BigInteger, cast, extract, func
from sqlalchemy.orm import aliased

# Lingvodoc imports.

from lingvodoc.models import (
    Client,
    DBSession,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    Entity,
    Field,
    LexicalEntry,
    PublishingEntity,
    TranslationAtom,
    TranslationGist,
    User,
)

from lingvodoc.views.v2.utils import message, unimplemented


log = logging.getLogger(__name__)


@view_config(route_name = 'stat_perspective', renderer = 'string')
def stat_perspective(request):
    """
    Gathers user participation statistics for a specified perspective in a given time interval
    [time_begin, time_end).

    Parameters 'time_begin' and 'time_end' are Unix timestamps and are specified by
    URL parameters 'time_begin', 'time_end' as either YYYY-MM-DDtHH:MM:SS-formatted dates or Unix timestamps
    as Python numeric literals.
    """

    log.debug('stat_perspective')

    try:

        perspective_client_id = request.matchdict.get('perspective_client_id')
        perspective_object_id = request.matchdict.get('perspective_object_id')

        def try_parse_datetime(time_string):
            """
            Tries to parse a time instance specified as either YYYY-MM-DDtHH:MM:SS-formatted date or Unix
            timestamp as Python numeric literal.

            Returns Unix timestamp as Python numeric value if succeeds and None otherwise.
            """

            try:
                return datetime.datetime \
                    .strptime(time_string, "%Y-%m-%dt%H:%M:%S") \
                    .replace(tzinfo = datetime.timezone.utc) \
                    .timestamp()

            except:
                pass

            try:
                return ast.literal_eval(time_string)

            except:
                pass

            return None

        # Trying to determine time interval.

        time_begin_string = request.params.get('time_begin', '0')
        time_begin = try_parse_datetime(time_begin_string)

        if time_begin is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_begin_string))}

        time_end_string = request.params.get('time_end', '2038-01-01t00:00:00')
        time_end = try_parse_datetime(time_end_string)

        if time_end is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_end_string))}

        log.debug('stat_perspective {0}/{1} from \'{2}\' ({3}) to \'{4}\' ({5})'.format(
            perspective_client_id, perspective_client_id,
            datetime.datetime.utcfromtimestamp(time_begin).isoformat(' '), time_begin,
            datetime.datetime.utcfromtimestamp(time_end).isoformat(' '), time_end))

        # Ok, now working, starting with perspective check.

        perspective = DBSession.query(DictionaryPerspective).filter_by(
            client_id = perspective_client_id,
            object_id = perspective_object_id).first()

        if not perspective:
            return {'error': message('No such perspective {0}/{1}.'.format(
                perspective_client_id, perspective_object_id))}

        # Getting lexical entries, using following base view:
        #
        # select
        #   coalesce((additional_metadata #>> '{merge, original_client_id}') :: bigint,
        #       client_id) as entry_client_id,
        #   coalesce((additional_metadata #>> '{merge, min_created_at}') :: bigint,
        #       extract(epoch from created_at)) as entry_created_at
        #   from lexicalentry where
        #       parent_client_id = perspective_client_id and
        #       parent_object_id = perspective_object_id and
        #       marked_for_deletion = false;

        entry_query = (DBSession.query(

            func.coalesce(
                cast(LexicalEntry.additional_metadata[('merge', 'original_client_id')].astext, BigInteger),
                LexicalEntry.client_id).label('entry_client_id'),

            func.coalesce(
                cast(LexicalEntry.additional_metadata[('merge', 'min_created_at')].astext, BigInteger),
                extract('epoch', LexicalEntry.created_at)).label('entry_created_at'))

            .filter(and_(
                LexicalEntry.parent_client_id == perspective_client_id,
                LexicalEntry.parent_object_id == perspective_object_id,
                LexicalEntry.marked_for_deletion == False)).subquery())

        entry_count_query = DBSession.query(
            entry_query.c.entry_client_id, func.count('*').label('entry_count')).filter(and_(
                entry_query.c.entry_created_at >= time_begin,
                entry_query.c.entry_created_at < time_end)).group_by(
                    entry_query.c.entry_client_id).subquery()

        entry_count_list = DBSession.query(
            Client.id, Client.user_id, Client.is_browser_client, entry_count_query.c.entry_count).join(
                entry_count_query, Client.id == entry_count_query.c.entry_client_id).all()

        # Counting lexical entries.

        user_data_dict = {}

        for client_id, user_id, is_browser, entry_count in entry_count_list:

            if user_id not in user_data_dict:
                user = DBSession.query(User).filter_by(id = user_id).first()

                user_data_dict[user_id] = {
                    'login': user.login, 'name': user.name,
                    'lexical entries': {'web': 0, 'desktop': 0, 'total': 0}}

            entry_data = user_data_dict[user_id]['lexical entries']

            entry_data['web' if is_browser else 'desktop'] += entry_count
            entry_data['total'] += entry_count

#       output = io.StringIO()
#       output.write('<html><table>')
#       output.write('<tr><td>' + '</td><td>'.join(['user', 'client', 'lexical entries']) + '</td></tr>')

#       for user_id, user_data in sorted(user_data_dict.items()):
#           return {'error': unimplemented())

#       output.write('</table></html>')

#       return Response(body = output.getvalue(), content_type = 'text/html')

        # Getting perspective's field data.

        locale_id = int(request.cookies.get('locale_id') or 2)

        field_data_list = DBSession.query(Field).filter(and_(
            DictionaryPerspectiveToField.parent_client_id == perspective_client_id,
            DictionaryPerspectiveToField.parent_object_id == perspective_object_id,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.client_id == DictionaryPerspectiveToField.field_client_id,
            Field.object_id == DictionaryPerspectiveToField.field_object_id,
            Field.marked_for_deletion == False)).all()

        simple_type_set = set(['image', 'link', 'markup', 'sound', 'text'])

        for field in field_data_list:
            data_type = field.data_type.lower()

            # Standard entity type, we should just count entities in the same as with entries.

            if data_type in simple_type_set:

                entity_query = (DBSession.query(

                    func.coalesce(
                        cast(Entity.additional_metadata[
                            ('merge', 'original_client_id')].astext, BigInteger),
                        Entity.client_id).label('entity_client_id'),

                    func.coalesce(
                        cast(Entity.additional_metadata[
                            ('merge', 'min_created_at')].astext, BigInteger),
                        extract('epoch', Entity.created_at)).label('entity_created_at'),

                    PublishingEntity.published)

                    .filter(and_(
                        LexicalEntry.parent_client_id == perspective_client_id,
                        LexicalEntry.parent_object_id == perspective_object_id,
                        LexicalEntry.marked_for_deletion == False,
                        Entity.parent_client_id == LexicalEntry.client_id,
                        Entity.parent_object_id == LexicalEntry.object_id,
                        Entity.field_client_id == field.client_id,
                        Entity.field_object_id == field.object_id,
                        Entity.marked_for_deletion == False,
                        PublishingEntity.client_id == Entity.client_id,
                        PublishingEntity.object_id == Entity.object_id)).subquery())

                # Grouping by clients and publishing status, adding user/client info.

                entity_count_query = DBSession.query(
                    entity_query.c.entity_client_id,
                    entity_query.c.published,
                    func.count('*').label('entity_count')).filter(and_(
                        entity_query.c.entity_created_at >= time_begin,
                        entity_query.c.entity_created_at < time_end)).group_by(
                            entity_query.c.entity_client_id,
                            entity_query.c.published).subquery()

                entity_count_list = DBSession.query(
                    Client.id, Client.user_id, Client.is_browser_client,
                    entity_count_query.c.published,
                    entity_count_query.c.entity_count).join(
                        entity_count_query, Client.id == entity_count_query.c.entity_client_id).all()

            # Grouping tags are counted in a special way.

            elif data_type == 'grouping tag':

                entity_query = (DBSession.query(

                    LexicalEntry.client_id,
                    LexicalEntry.object_id,

                    func.coalesce(
                        cast(Entity.additional_metadata[
                            ('merge', 'original_client_id')].astext, BigInteger),
                        Entity.client_id).label('entity_client_id'),

                    func.coalesce(
                        cast(Entity.additional_metadata[
                            ('merge', 'min_created_at')].astext, BigInteger),
                        extract('epoch', Entity.created_at)).label('entity_created_at'),

                    PublishingEntity.published)

                    .filter(and_(
                        LexicalEntry.parent_client_id == perspective_client_id,
                        LexicalEntry.parent_object_id == perspective_object_id,
                        LexicalEntry.marked_for_deletion == False,
                        Entity.parent_client_id == LexicalEntry.client_id,
                        Entity.parent_object_id == LexicalEntry.object_id,
                        Entity.field_client_id == field.client_id,
                        Entity.field_object_id == field.object_id,
                        Entity.marked_for_deletion == False,
                        PublishingEntity.client_id == Entity.client_id,
                        PublishingEntity.object_id == Entity.object_id)).subquery())

                # Grouping tags are grouped by lexical entries.

                entry_group_query = DBSession.query(
                    entity_query.c.entity_client_id,
                    entity_query.c.published).filter(and_(
                        entity_query.c.entity_created_at >= time_begin,
                        entity_query.c.entity_created_at < time_end)).group_by(
                            entity_query.c.client_id,
                            entity_query.c.object_id,
                            entity_query.c.entity_client_id,
                            entity_query.c.published).subquery()

                # Grouping by clients and publishing status, adding user/client info.

                entity_count_query = DBSession.query(
                    entry_group_query.c.entity_client_id,
                    entry_group_query.c.published,
                    func.count('*').label('entity_count')).group_by(
                        entry_group_query.c.entity_client_id,
                        entry_group_query.c.published).subquery()

                entity_count_list = DBSession.query(
                    Client.id, Client.user_id, Client.is_browser_client,
                    entity_count_query.c.published,
                    entity_count_query.c.entity_count).join(
                        entity_count_query, Client.id == entity_count_query.c.entity_client_id).all()

            # Unknown field data type.

            else:
                return {'error': message('Unknown field data type \'{0}\'.'.format(data_type))}

            # Counting entities.

            for client_id, user_id, is_browser, published, entity_count in entity_count_list:

                if user_id not in user_data_dict:
                    user = DBSession.query(User).filter_by(id = user_id).first()

                    user_data_dict[user_id] = {
                        'login': user.login, 'name': user.name,
                        'entities': {'published': {}, 'unpublished': {}, 'total': {}}}

                user_data = user_data_dict[user_id]

                if 'entities' not in user_data:
                    user_data['entities'] = {'published': {}, 'unpublished': {}, 'total': {}}

                entity_data = user_data['entities']

                # Counting entities by publishing status, data type and client type.

                client_string = 'web' if is_browser else 'desktop'
                published_string = 'published' if published else 'unpublished'

                for p_string in [published_string, 'total']:

                    if p_string not in entity_data:
                        entity_data[p_string] = {}

                    for d_string in [field.get_translation(locale_id), 'total']:

                        if d_string not in entity_data[p_string]:
                            entity_data[p_string][d_string] = {'web': 0, 'desktop': 0, 'total': 0}

                        for c_string in [client_string, 'total']:

                            entity_data[p_string][d_string][c_string] += entity_count

        # As of now (Tue Mar 14 22:29:29 UTC 2017), returning formatted textual JSON representation.

        return pprint.pformat(user_data_dict, width = 144)

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('stat_perspective: exception')
        log.debug('\n' + traceback_string)

        return {'error': message('\n' + traceback_string)}

