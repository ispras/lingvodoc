
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

from sqlalchemy import and_, BigInteger, cast, extract, func, tuple_
from sqlalchemy.orm import aliased

# Lingvodoc imports.

from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    ENGLISH_LOCALE,
    Entity,
    Field,
    LexicalEntry,
    PublishingEntity,
    RUSSIAN_LOCALE,
    TranslationAtom,
    TranslationGist,
    User,
    Group,
    BaseGroup,
    DictionaryPerspective
)

from lingvodoc.views.v2.utils import message, unimplemented
from lingvodoc.views.v2.utils import add_user_to_group
from lingvodoc.schema.gql_holders import ResponseError

log = logging.getLogger(__name__)
def translation_service_search(searchstring):
    translationatom = DBSession.query(TranslationAtom)\
        .join(TranslationGist).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service')\
        .order_by(TranslationAtom.client_id)\
        .first()
    response = translationgist_contents(translationatom.parent)
    return response


#: Set of statistically simple field types, statistics of entities belonging to fields with these types are
#: simple counts.
simple_field_type_set = set(['image', 'link', 'markup', 'sound', 'text'])


def stat_perspective(perspective_id, time_begin, time_end, locale_id=2):
    """
    Gathers user participation statistics for a specified perspective in a given time interval
    [time_begin, time_end).

    Parameters 'time_begin' and 'time_end' are Unix timestamps and are specified by URL parameters
    'time_begin', 'time_end' as either YYYY-MM-DDtHH:MM:SS-formatted dates or Unix timestamps as Python
    numeric literals.
    """

    #log.debug('stat_perspective')

    try:
        """


        # Trying to determine time interval.

        time_begin_string = request.params.get('time_begin', '0')
        time_begin = try_parse_datetime(time_begin_string) ####################

        if time_begin is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_begin_string))}

        time_end_string = request.params.get('time_end', '2038-01-01t00:00:00')
        time_end = try_parse_datetime(time_end_string)   ####################
        ###################################################################################################
        """
        # TODO: id check
        perspective_client_id = perspective_id[0] ###########
        perspective_object_id = perspective_id[1] ############
        if time_end is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_end_string))}

        log.debug('stat_perspective {0}/{1} from \'{2}\' ({3}) to \'{4}\' ({5})'.format(
            perspective_client_id, perspective_object_id,
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
        #     client_id) as entry_client_id,
        #   coalesce((additional_metadata #>> '{merge, min_created_at}') :: bigint,
        #     extract(epoch from created_at)) as entry_created_at
        #   from lexicalentry where
        #     parent_client_id = perspective_client_id and
        #     parent_object_id = perspective_object_id and
        #     marked_for_deletion = false;

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

        # Getting perspective's field data.

        #####locale_id = int(request.cookies.get('locale_id') or 2)

        field_data_list = DBSession.query(Field).filter(and_(
            DictionaryPerspectiveToField.parent_client_id == perspective_client_id,
            DictionaryPerspectiveToField.parent_object_id == perspective_object_id,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.client_id == DictionaryPerspectiveToField.field_client_id,
            Field.object_id == DictionaryPerspectiveToField.field_object_id,
            Field.marked_for_deletion == False)).all()

        for field in field_data_list:
            data_type = field.data_type.lower()

            # Standard entity type, we should just count entities in the same as with entries.

            if data_type in simple_field_type_set:

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

                # Grouping by clients and publishing status.

                entity_count_query = DBSession.query(
                    entity_query.c.entity_client_id,
                    entity_query.c.published,
                    func.count('*').label('entity_count')).filter(and_(
                        entity_query.c.entity_created_at >= time_begin,
                        entity_query.c.entity_created_at < time_end)).group_by(
                            entity_query.c.entity_client_id,
                            entity_query.c.published).subquery()

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

                # Grouping by clients and publishing status.

                entity_count_query = DBSession.query(
                    entry_group_query.c.entity_client_id,
                    entry_group_query.c.published,
                    func.count('*').label('entity_count')).group_by(
                        entry_group_query.c.entity_client_id,
                        entry_group_query.c.published).subquery()

            # Unknown field data type.

            else:
                return {'error': message('Unknown field data type \'{0}\'.'.format(data_type))}

            # Adding user/client info, getting final entity counts.

            entity_count_list = DBSession.query(
                Client.id, Client.user_id, Client.is_browser_client,
                entity_count_query.c.published,
                entity_count_query.c.entity_count).join(
                    entity_count_query, Client.id == entity_count_query.c.entity_client_id).all()

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

                    for f_string in [field.get_translation(locale_id), 'total']:

                        if f_string not in entity_data[p_string]:
                            entity_data[p_string][f_string] = {'web': 0, 'desktop': 0, 'total': 0}

                        for c_string in [client_string, 'total']:
                            entity_data[p_string][f_string][c_string] += entity_count

        # Returning gathered statistics.

        log.debug('stat_perspective {0}/{1} from \'{2}\' ({3}) to \'{4}\' ({5}):\n{6}'.format(
            perspective_client_id, perspective_object_id,
            datetime.datetime.utcfromtimestamp(time_begin).isoformat(' '), time_begin,
            datetime.datetime.utcfromtimestamp(time_end).isoformat(' '), time_end,
            pprint.pformat(user_data_dict, width = 144)))

        return user_data_dict

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('stat_perspective: exception')
        log.debug('\n' + traceback_string)

        return {'error': message('\n' + traceback_string)}


def stat_dictionary(dictionary_id, time_begin, time_end, locale_id=None):
    """
    Gathers cumulative user participation statistics for all perspectives of a specified dictionary in a
    given time interval [time_begin, time_end).

    Parameters 'time_begin' and 'time_end' are Unix timestamps and are specified by URL parameters in the
    same way as for 'stat_perspective'.
    """

    log.debug('stat_dictionary')

    try:
        """
        # Trying to determine time interval.

        time_begin_string = request.params.get('time_begin', '0')
        time_begin = try_parse_datetime(time_begin_string) ######################

        if time_begin is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_begin_string))}

        time_end_string = request.params.get('time_end', '2038-01-01t00:00:00')
        time_end = try_parse_datetime(time_end_string)    ###################

        if time_end is None:
            return {'error': message('Invalid time representation \'{0}\'.'.format(time_end_string))}
        """
        dictionary_client_id = dictionary_id[0]#request.matchdict.get('dictionary_client_id')
        dictionary_object_id = dictionary_id[1]#request.matchdict.get('dictionary_object_id')
        log.debug('stat_dictionary {0}/{1} from \'{2}\' ({3}) to \'{4}\' ({5})'.format(
            dictionary_client_id, dictionary_object_id,
            datetime.datetime.utcfromtimestamp(time_begin).isoformat(' '), time_begin,
            datetime.datetime.utcfromtimestamp(time_end).isoformat(' '), time_end))

        # Ok, now working, starting with dictionary check.

        dictionary = DBSession.query(Dictionary).filter_by(
            client_id = dictionary_client_id,
            object_id = dictionary_object_id).first()

        if not dictionary:
            return {'error': message('No such dictionary {0}/{1}.'.format(
                dictionary_client_id, dictionary_object_id))}

        primary_locale_id = int(locale_id or 2)

        secondary_locale_id = (ENGLISH_LOCALE
            if primary_locale_id != ENGLISH_LOCALE else RUSSIAN_LOCALE)

        # And now we are going to count lexical entries, we begin with basic perspective/lexical entry view.

        entry_query = (DBSession.query(

            func.coalesce(
                cast(LexicalEntry.additional_metadata[('merge', 'original_client_id')].astext, BigInteger),
                LexicalEntry.client_id).label('entry_client_id'),

            func.coalesce(
                cast(LexicalEntry.additional_metadata[('merge', 'min_created_at')].astext, BigInteger),
                extract('epoch', LexicalEntry.created_at)).label('entry_created_at'),

            DictionaryPerspective.state_translation_gist_client_id.label('state_client_id'),
            DictionaryPerspective.state_translation_gist_object_id.label('state_object_id'))

            .filter(and_(
                DictionaryPerspective.parent_client_id == dictionary_client_id,
                DictionaryPerspective.parent_object_id == dictionary_object_id,
                DictionaryPerspective.marked_for_deletion == False,
                LexicalEntry.parent_client_id == DictionaryPerspective.client_id,
                LexicalEntry.parent_object_id == DictionaryPerspective.object_id,
                LexicalEntry.marked_for_deletion == False)).subquery())

        # Selecting lexical entries inside the specified time interval, grouping by clients and perspective
        # states.

        entry_count_query = DBSession.query(
            entry_query.c.entry_client_id,
            entry_query.c.state_client_id,
            entry_query.c.state_object_id,
            func.count('*').label('entry_count')).filter(and_(
                entry_query.c.entry_created_at >= time_begin,
                entry_query.c.entry_created_at < time_end)).group_by(
                    entry_query.c.entry_client_id,
                    entry_query.c.state_client_id, entry_query.c.state_object_id).subquery()

        # Queries for translations of perspective states, works analogously to 'get_translation()' method in
        # the 'models' module, just through SQL.

        StateTranslation = aliased(TranslationGist, name = 'StateTranslation')
        StatePrimaryAtom = aliased(TranslationAtom, name = 'StatePrimaryAtom')
        StateSecondaryAtom = aliased(TranslationAtom, name = 'StateSecondaryAtom')

        state_primary_query = DBSession.query(StatePrimaryAtom.content).filter(and_(
            StatePrimaryAtom.parent_client_id == StateTranslation.client_id,
            StatePrimaryAtom.parent_object_id == StateTranslation.object_id,
            StatePrimaryAtom.locale_id == primary_locale_id)).limit(1).subquery()

        state_secondary_query = DBSession.query(StateSecondaryAtom.content).filter(and_(
            StateSecondaryAtom.parent_client_id == StateTranslation.client_id,
            StateSecondaryAtom.parent_object_id == StateTranslation.object_id,
            StateSecondaryAtom.locale_id == secondary_locale_id)).limit(1).subquery()

        perspective_state_query = DBSession.query(
            StateTranslation.client_id, StateTranslation.object_id, func.coalesce(
                state_primary_query.as_scalar(),
                state_secondary_query.as_scalar(), 'UNDEFINED').label('content')).subquery()

        # Adding client and user info and perspective state translations, grouping by users, web/desktop
        # clients and perspective states, aggregating entry counts.

        entry_count_list = (DBSession.query(

            Client.user_id, Client.is_browser_client,
            func.sum(entry_count_query.c.entry_count),
            perspective_state_query.c.content)

            .select_from(entry_count_query)

            .join(Client,
                Client.id == entry_count_query.c.entry_client_id)

            .join(perspective_state_query, and_(
                perspective_state_query.c.client_id == entry_count_query.c.state_client_id,
                perspective_state_query.c.object_id == entry_count_query.c.state_object_id))

            .group_by(Client.user_id, Client.is_browser_client, perspective_state_query.c.content)).all()

        # Aggregating lexical entry statistics.

        user_data_dict = {}

        for user_id, is_browser, entry_count, perspective_state in entry_count_list:

            if user_id not in user_data_dict:
                user = DBSession.query(User).filter_by(id = user_id).first()

                user_data_dict[user_id] = {
                    'login': user.login, 'name': user.name,
                    'lexical entries': {}}

            # For each user we aggregate by perspective state and client type.

            entry_data = user_data_dict[user_id]['lexical entries']
            client_string = 'web' if is_browser else 'desktop'

            for s_string in [perspective_state, 'total']:

                if s_string not in entry_data:
                    entry_data[s_string] = {'web': 0, 'desktop': 0, 'total': 0}

                for c_string in [client_string, 'total']:
                    entry_data[s_string][c_string] += int(entry_count)

        # Getting info of all fields of all perspectives of the dictionary.

        field_data_list = DBSession.query(Field).filter(and_(
            DictionaryPerspective.parent_client_id == dictionary_client_id,
            DictionaryPerspective.parent_object_id == dictionary_object_id,
            DictionaryPerspective.marked_for_deletion == False,
            DictionaryPerspectiveToField.parent_client_id == DictionaryPerspective.client_id,
            DictionaryPerspectiveToField.parent_object_id == DictionaryPerspective.object_id,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.client_id == DictionaryPerspectiveToField.field_client_id,
            Field.object_id == DictionaryPerspectiveToField.field_object_id,
            Field.marked_for_deletion == False)).distinct().all()

        # Sorting fields into simple and grouping categories.

        simple_field_id_list = []
        grouping_field_id_list = []

        for field in field_data_list:
            data_type = field.data_type.lower()

            if data_type in simple_field_type_set:
                simple_field_id_list.append((field.client_id, field.object_id))

            elif data_type == 'grouping tag':
                grouping_field_id_list.append((field.client_id, field.object_id))

            else: return {'error':
                message('Unknown field data type \'{0}\'.'.format(data_type))}

        # Some parts of the counting and aggregation process are shared for simple and grouping fields, so
        # we process both these field types together.

        simple_field_id_list.sort()
        grouping_field_id_list.sort()

        for field_id_list, field_type in [
            (simple_field_id_list, 'simple'),
            (grouping_field_id_list, 'grouping')]:

            # We are going to count entites of fields of simple type.

            if field_type == 'simple':

                entity_query = (DBSession.query(

                    func.coalesce(
                        cast(Entity.additional_metadata[
                            ('merge', 'original_client_id')].astext, BigInteger),
                        Entity.client_id).label('entity_client_id'),

                    func.coalesce(
                        cast(Entity.additional_metadata[
                            ('merge', 'min_created_at')].astext, BigInteger),
                        extract('epoch', Entity.created_at)).label('entity_created_at'),

                    DictionaryPerspective.state_translation_gist_client_id.label('state_client_id'),
                    DictionaryPerspective.state_translation_gist_object_id.label('state_object_id'),

                    Entity.field_client_id,
                    Entity.field_object_id,

                    PublishingEntity.published)

                    .filter(and_(
                        DictionaryPerspective.parent_client_id == dictionary_client_id,
                        DictionaryPerspective.parent_object_id == dictionary_object_id,
                        DictionaryPerspective.marked_for_deletion == False,
                        LexicalEntry.parent_client_id == DictionaryPerspective.client_id,
                        LexicalEntry.parent_object_id == DictionaryPerspective.object_id,
                        LexicalEntry.marked_for_deletion == False,
                        Entity.parent_client_id == LexicalEntry.client_id,
                        Entity.parent_object_id == LexicalEntry.object_id,
                        Entity.marked_for_deletion == False,
                        tuple_(Entity.field_client_id, Entity.field_object_id).in_(field_id_list),
                        PublishingEntity.client_id == Entity.client_id,
                        PublishingEntity.object_id == Entity.object_id)).subquery())

                # Selecting entities inside the specified time interval, grouping by clients, perspective
                # states, fields and publishing status.

                entity_count_query = (DBSession.query(

                    entity_query.c.entity_client_id,
                    entity_query.c.state_client_id, entity_query.c.state_object_id,
                    entity_query.c.field_client_id, entity_query.c.field_object_id,
                    entity_query.c.published,
                    func.count('*').label('entity_count'))

                    .filter(and_(
                        entity_query.c.entity_created_at >= time_begin,
                        entity_query.c.entity_created_at < time_end)).group_by(
                            entity_query.c.entity_client_id,
                            entity_query.c.state_client_id, entity_query.c.state_object_id,
                            entity_query.c.field_client_id, entity_query.c.field_object_id,
                            entity_query.c.published).subquery())

            # We are going to count entites of fields of grouping type.

            else:

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

                    DictionaryPerspective.state_translation_gist_client_id.label('state_client_id'),
                    DictionaryPerspective.state_translation_gist_object_id.label('state_object_id'),

                    Entity.field_client_id,
                    Entity.field_object_id,

                    PublishingEntity.published)

                    .filter(and_(
                        DictionaryPerspective.parent_client_id == dictionary_client_id,
                        DictionaryPerspective.parent_object_id == dictionary_object_id,
                        DictionaryPerspective.marked_for_deletion == False,
                        LexicalEntry.parent_client_id == DictionaryPerspective.client_id,
                        LexicalEntry.parent_object_id == DictionaryPerspective.object_id,
                        LexicalEntry.marked_for_deletion == False,
                        Entity.parent_client_id == LexicalEntry.client_id,
                        Entity.parent_object_id == LexicalEntry.object_id,
                        Entity.marked_for_deletion == False,
                        tuple_(Entity.field_client_id, Entity.field_object_id).in_(field_id_list),
                        PublishingEntity.client_id == Entity.client_id,
                        PublishingEntity.object_id == Entity.object_id)).subquery())

                # Grouping tags are first grouped by lexical entries.

                entry_group_query = (DBSession.query(

                    entity_query.c.entity_client_id,
                    entity_query.c.state_client_id, entity_query.c.state_object_id,
                    entity_query.c.field_client_id, entity_query.c.field_object_id,
                    entity_query.c.published)

                    .filter(and_(
                        entity_query.c.entity_created_at >= time_begin,
                        entity_query.c.entity_created_at < time_end)).group_by(

                            entity_query.c.client_id,
                            entity_query.c.object_id,
                            entity_query.c.entity_client_id,
                            entity_query.c.state_client_id, entity_query.c.state_object_id,
                            entity_query.c.field_client_id, entity_query.c.field_object_id,
                            entity_query.c.published).subquery())

                # Grouping by clients, perspective states, fields and publishing status.

                entity_count_query = (DBSession.query(

                    entry_group_query.c.entity_client_id,
                    entry_group_query.c.state_client_id, entry_group_query.c.state_object_id,
                    entry_group_query.c.field_client_id, entry_group_query.c.field_object_id,
                    entry_group_query.c.published,
                    func.count('*').label('entity_count'))

                    .group_by(
                        entry_group_query.c.entity_client_id,
                        entry_group_query.c.state_client_id, entry_group_query.c.state_object_id,
                        entry_group_query.c.field_client_id, entry_group_query.c.field_object_id,
                        entry_group_query.c.published).subquery())

            # Queries for translations of field names.

            FieldTranslation = aliased(TranslationGist, name = 'FieldTranslation')
            FieldPrimaryAtom = aliased(TranslationAtom, name = 'FieldPrimaryAtom')
            FieldSecondaryAtom = aliased(TranslationAtom, name = 'FieldSecondaryAtom')

            field_primary_query = DBSession.query(FieldPrimaryAtom.content).filter(and_(
                FieldPrimaryAtom.parent_client_id == FieldTranslation.client_id,
                FieldPrimaryAtom.parent_object_id == FieldTranslation.object_id,
                FieldPrimaryAtom.locale_id == primary_locale_id)).limit(1).subquery()

            field_secondary_query = DBSession.query(FieldSecondaryAtom.content).filter(and_(
                FieldSecondaryAtom.parent_client_id == FieldTranslation.client_id,
                FieldSecondaryAtom.parent_object_id == FieldTranslation.object_id,
                FieldSecondaryAtom.locale_id == secondary_locale_id)).limit(1).subquery()

            # Getting mapping from field ids to field names.

            field_name_query = (DBSession.query(

                Field.client_id, Field.object_id,
                func.coalesce(
                    field_primary_query.as_scalar(),
                    field_secondary_query.as_scalar(), 'UNDEFINED').label('content'))

                .filter(and_(
                    Field.translation_gist_client_id == FieldTranslation.client_id,
                    Field.translation_gist_object_id == FieldTranslation.object_id)).subquery())

            # Grouping entities and aggregating entity counts.

            entity_count_list = (DBSession.query(

                Client.user_id,
                Client.is_browser_client,
                func.sum(entity_count_query.c.entity_count),
                perspective_state_query.c.content,
                field_name_query.c.content,
                entity_count_query.c.published)

                .select_from(entity_count_query)

                # Adding client/user info and perspective state / field name translations

                .join(Client,
                    Client.id == entity_count_query.c.entity_client_id)

                .join(perspective_state_query, and_(
                    perspective_state_query.c.client_id == entity_count_query.c.state_client_id,
                    perspective_state_query.c.object_id == entity_count_query.c.state_object_id))

                .join(field_name_query, and_(
                    field_name_query.c.client_id == entity_count_query.c.field_client_id,
                    field_name_query.c.object_id == entity_count_query.c.field_object_id))

                # Grouping by users, web/desktop clients, perspective states, field names and publishing
                # status.

                .group_by(
                    Client.user_id,
                    Client.is_browser_client,
                    perspective_state_query.c.content,
                    field_name_query.c.content,
                    entity_count_query.c.published)).all()

            # Aggregating statistics for entities of simple type.

            for (user_id, is_browser, entity_count,
                perspective_state, field_name, published) in entity_count_list:

                if user_id not in user_data_dict:
                    user = DBSession.query(User).filter_by(id = user_id).first()

                    user_data_dict[user_id] = {
                        'login': user.login, 'name': user.name,
                        'entities': {}}

                user_data = user_data_dict[user_id]

                if 'entities' not in user_data:
                    user_data['entities'] = {}

                # For each user we aggregate by perspective state, publishing status, field name and client
                # type.

                entity_data = user_data['entities']

                client_string = 'web' if is_browser else 'desktop'
                published_string = 'published' if published else 'unpublished'

                for s_string in [perspective_state, 'total']:

                    if s_string not in entity_data:
                        entity_data[s_string] = {'published': {}, 'unpublished': {}, 'total': {}}

                    for p_string in [published_string, 'total']:
                        local_entity_data = entity_data[s_string][p_string]

                        for f_string in [field_name, 'total']:

                            if f_string not in local_entity_data:
                                local_entity_data[f_string] = {'web': 0, 'desktop': 0, 'total': 0}

                            for c_string in [client_string, 'total']:
                                local_entity_data[f_string][c_string] += int(entity_count)

        # Returning gathered statistics.

        log.debug('stat_dictionary {0}/{1} from \'{2}\' ({3}) to \'{4}\' ({5}):\n{6}'.format(
            dictionary_client_id, dictionary_object_id,
            datetime.datetime.utcfromtimestamp(time_begin).isoformat(' '), time_begin,
            datetime.datetime.utcfromtimestamp(time_end).isoformat(' '), time_end,
            pprint.pformat(user_data_dict, width = 144)))

        return user_data_dict

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('stat_dictionary: exception')
        log.debug('\n' + traceback_string)

        return {'error': message('\n' + traceback_string)}
