
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

from sqlalchemy import (
    and_,
    BigInteger,
    cast,
    extract,
    Float,
    func,
    tuple_)

from sqlalchemy.orm import aliased

# Lingvodoc imports.

from lingvodoc.schema.gql_holders import ResponseError

from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    ENGLISH_LOCALE,
    Entity,
    Field,
    Group,
    Language,
    LexicalEntry,
    PublishingEntity,
    RUSSIAN_LOCALE,
    TranslationAtom,
    TranslationGist,
    User)

from lingvodoc.utils import ids_to_id_query
from lingvodoc.utils.creation import add_user_to_group
from lingvodoc.schema.gql_holders import ResponseError

from lingvodoc.cache.caching import CACHE

log = logging.getLogger(__name__)


#: Set of statistically simple field types, statistics of entities belonging to fields with these types are
#: simple counts.
simple_field_type_set = set(['image', 'link', 'markup', 'sound', 'text', "directed link"])


def time_format(
    time_begin,
    time_end):

    if time_begin:

        time_begin_str = (

            '\'{}\' ({})'.format(
                datetime.datetime.utcfromtimestamp(time_begin).isoformat(' '),
                time_begin))

    else:
        
        time_begin_str = 'None'

    if time_end:

        time_end_str = (

            '\'{}\' ({})'.format(
                datetime.datetime.utcfromtimestamp(time_end).isoformat(' '),
                time_end))

    else:
        
        time_end_str = 'None'

    return (
        time_begin_str, time_end_str)


def with_time_filter(
    query,
    column,
    time_begin,
    time_end):

    if time_begin is not None:

        query = (

            query.filter(
                column >= time_begin))

    if time_end is not None:

        query = (

            query.filter(
                column < time_end))

    return query


def new_format(current_statistics):

    new_format_statistics = []

    for key, stat_dict in current_statistics.items():

        new_dict = {
            'user_id': key,
            'name': stat_dict['name']}

        # NOTE: 'lexical_entries' with underscore '_' for the new format.

        if 'lexical entries' in stat_dict:
            new_dict['lexical_entries'] = stat_dict['lexical entries']

        if 'entities' in stat_dict:
            new_dict['entities'] = stat_dict['entities']

        new_format_statistics.append(new_dict)

    log.debug(
        '\nnew format:\n' +
        pprint.pformat(
            new_format_statistics, width = 144))

    return new_format_statistics


entry_client_id_e = (

    func.coalesce(

        cast(
            LexicalEntry.additional_metadata[('merge', 'original_client_id')].astext,
            BigInteger),

        LexicalEntry.client_id)

        .label('entry_client_id'))


entry_created_at_e = (

    func.coalesce(

        cast(
            LexicalEntry.additional_metadata[('merge', 'min_created_at')].astext,
            Float),

        extract(
            'epoch',
            LexicalEntry.created_at))

        .label('entry_created_at'))


entity_client_id_e = (

    func.coalesce(
        cast(
            Entity.additional_metadata[
                ('merge', 'original_client_id')].astext,
            BigInteger),
        Entity.client_id)

        .label('entity_client_id'))


entity_created_at_e = (

    func.coalesce(
        cast(
            Entity.additional_metadata[
                ('merge', 'min_created_at')].astext,
            Float),
        extract(
            'epoch',
            Entity.created_at))

        .label('entity_created_at'))


def stat_perspective(
    perspective_id,
    time_begin = None,
    time_end = None,
    locale_id = None):
    """
    Gathers user participation statistics for a specified perspective in a given time interval
    [time_begin, time_end).

    Parameters 'time_begin' and 'time_end' are Unix timestamps if specified.

    Significant difference compared to perspective statistics in views/v2/statistics.py is also statistics
    of unaccepted entities.
    """

    try:

        time_begin_str, time_end_str = (

            time_format(
                time_begin,
                time_end))

        log.debug(
            f'\nstat_perspective {perspective_id} from {time_begin_str} to {time_end_str}')

        # Ok, now working, starting with perspective check.

        perspective = (
            DictionaryPerspective.get(perspective_id))

        if not perspective:
            raise ResponseError(f'No perspective {perspective_id}.')

        # Getting lexical entries, using following base view:
        #
        # select
        #   coalesce((additional_metadata #>> '{merge, original_client_id}') :: bigint,
        #     client_id) as entry_client_id,
        #   coalesce((additional_metadata #>> '{merge, min_created_at}') :: float,
        #     extract(epoch from created_at)) as entry_created_at
        #   from lexicalentry where
        #     parent_client_id = perspective_client_id and
        #     parent_object_id = perspective_object_id and
        #     marked_for_deletion = false;

        entry_query = (

            DBSession

                .query(
                    entry_client_id_e,
                    entry_created_at_e)

                .filter(
                    LexicalEntry.parent_client_id == perspective_id[0],
                    LexicalEntry.parent_object_id == perspective_id[1],
                    LexicalEntry.marked_for_deletion == False)

                .subquery())

        entry_count_query = (

            with_time_filter(

                DBSession.query(
                    entry_query.c.entry_client_id,
                    func.count('*').label('entry_count')),

                entry_query.c.entry_created_at,
                time_begin,
                time_end)

                .group_by(entry_query.c.entry_client_id)
                .subquery())

        entry_count_list = (

            DBSession

                .query(
                    Client.id,
                    Client.user_id,
                    Client.is_browser_client,
                    entry_count_query.c.entry_count)

                .join(
                    entry_count_query,
                    Client.id == entry_count_query.c.entry_client_id)

                .all())

        # Counting lexical entries.

        user_data_dict = {}

        if entry_count_list:

            user_data_total = {
                'login': None,
                'name': None,
                'lexical entries': {'web': 0, 'desktop': 0, 'total': 0}}

            user_data_dict[None] = user_data_total

        for client_id, user_id, is_browser, entry_count in entry_count_list:

            if user_id not in user_data_dict:

                user = User.get(user_id)

                user_data_dict[user_id] = {
                    'login': user.login,
                    'name': user.name,
                    'lexical entries': {'web': 0, 'desktop': 0, 'total': 0}}

            entry_data = (
                user_data_dict[user_id]['lexical entries'])

            entry_data_total = (
                user_data_total['lexical entries'])

            client_string = (
                'web' if is_browser else 'desktop')

            entry_data[client_string] += entry_count
            entry_data_total[client_string] += entry_count

            entry_data['total'] += entry_count
            entry_data_total['total'] += entry_count

        # Getting perspective's field data.

        field_data_list = (

            DBSession
                .query(Field)

                .filter(
                    DictionaryPerspectiveToField.parent_client_id == perspective_id[0],
                    DictionaryPerspectiveToField.parent_object_id == perspective_id[1],
                    DictionaryPerspectiveToField.marked_for_deletion == False,
                    Field.client_id == DictionaryPerspectiveToField.field_client_id,
                    Field.object_id == DictionaryPerspectiveToField.field_object_id,
                    Field.marked_for_deletion == False)

                .all())

        for field in field_data_list:

            data_type = field.data_type.lower()

            # Standard entity type, we should just count entities in the same as with entries.

            if data_type in simple_field_type_set:

                entity_query = (

                    DBSession

                        .query(
                            entity_client_id_e,
                            entity_created_at_e,                        

                            PublishingEntity.published,
                            PublishingEntity.accepted)

                        .filter(
                            LexicalEntry.parent_client_id == perspective_id[0],
                            LexicalEntry.parent_object_id == perspective_id[1],
                            LexicalEntry.marked_for_deletion == False,
                            Entity.parent_client_id == LexicalEntry.client_id,
                            Entity.parent_object_id == LexicalEntry.object_id,
                            Entity.field_client_id == field.client_id,
                            Entity.field_object_id == field.object_id,
                            Entity.marked_for_deletion == False,
                            PublishingEntity.client_id == Entity.client_id,
                            PublishingEntity.object_id == Entity.object_id)

                        .subquery())

                # Grouping by clients and publishing status.

                entity_count_query = (

                    with_time_filter(

                        DBSession.query(
                            entity_query.c.entity_client_id,
                            entity_query.c.published,
                            entity_query.c.accepted,
                            func.count('*').label('entity_count')),

                        entity_query.c.entity_created_at,
                        time_begin,
                        time_end)

                        .group_by(
                            entity_query.c.entity_client_id,
                            entity_query.c.published,
                            entity_query.c.accepted)

                        .subquery())

            # Grouping tags are counted in a special way.

            elif data_type == 'grouping tag':

                entity_query = (

                    DBSession

                        .query(
                            LexicalEntry.client_id,
                            LexicalEntry.object_id,

                            entity_client_id_e,
                            entity_created_at_e,

                            PublishingEntity.published,
                            PublishingEntity.accepted)

                        .filter(
                            LexicalEntry.parent_client_id == perspective_id[0],
                            LexicalEntry.parent_object_id == perspective_id[1],
                            LexicalEntry.marked_for_deletion == False,

                            Entity.parent_client_id == LexicalEntry.client_id,
                            Entity.parent_object_id == LexicalEntry.object_id,
                            Entity.field_client_id == field.client_id,
                            Entity.field_object_id == field.object_id,
                            Entity.marked_for_deletion == False,

                            PublishingEntity.client_id == Entity.client_id,
                            PublishingEntity.object_id == Entity.object_id)

                        .subquery())

                # Grouping tags are grouped by lexical entries.

                entry_group_query = (

                    with_time_filter(

                        DBSession.query(
                            entity_query.c.entity_client_id,
                            entity_query.c.published,
                            entity_query.c.accepted),

                        entity_query.c.entity_created_at,
                        time_begin,
                        time_end)

                        .group_by(
                            entity_query.c.client_id,
                            entity_query.c.object_id,
                            entity_query.c.entity_client_id,
                            entity_query.c.published,
                            entity_query.c.accepted)

                        .subquery())

                # Grouping by clients and publishing status.

                entity_count_query = (

                    DBSession

                        .query(
                            entry_group_query.c.entity_client_id,
                            entry_group_query.c.published,
                            entry_group_query.c.accepted,
                            func.count('*').label('entity_count'))

                        .group_by(
                            entry_group_query.c.entity_client_id,
                            entry_group_query.c.published,
                            entry_group_query.c.accepted)

                        .subquery())

            # Unknown field data type.

            else:

                raise ResponseError(f'Unknown field data type \'{data_type}\'.')

            # Adding user/client info, getting final entity counts.

            entity_count_list = (

                DBSession

                    .query(
                        Client.user_id,
                        Client.is_browser_client,
                        entity_count_query.c.published,
                        entity_count_query.c.accepted,
                        entity_count_query.c.entity_count)

                    .join(
                        entity_count_query,
                        Client.id == entity_count_query.c.entity_client_id)

                    .all())

            # Counting entities.

            for user_id, is_browser, published, accepted, entity_count in entity_count_list:

                if user_id not in user_data_dict:

                    user = User.get(user_id)

                    user_data_dict[user_id] = {
                        'login': user.login,
                        'name': user.name,
                        'entities': {
                            'published': {},
                            'unpublished': {},
                            'total': {},
                            'unaccepted': {}}}

                user_data = user_data_dict[user_id]

                if 'entities' not in user_data:

                    user_data['entities'] = {
                        'published': {},
                        'unpublished': {},
                        'total': {},
                        'unaccepted': {}}

                if 'entities' not in user_data_total:

                    user_data_total['entities'] = {
                        'published': {},
                        'unpublished': {},
                        'total': {},
                        'unaccepted': {}}

                # Counting entities by publishing status, data type and client type.

                entity_data = (
                    user_data['entities'])

                entity_data_total = (
                    user_data_total['entities'])

                client_string = (
                    'web' if is_browser else 'desktop')

                published_string = (
                    'published' if published else 'unpublished')

                for p_string in [published_string, 'total']:

                    if p_string not in entity_data:

                        entity_data[p_string] = {}

                    if p_string not in entity_data_total:

                        entity_data_total[p_string] = {}

                    for f_string in [field.get_translation(locale_id), 'total']:

                        if f_string not in entity_data[p_string]:

                            entity_data[p_string][f_string] = {
                                'web': 0,
                                'desktop': 0,
                                'total': 0,
                                'field_id': [field.client_id, field.object_id]}

                        if f_string not in entity_data_total[p_string]:

                            entity_data_total[p_string][f_string] = {
                                'web': 0,
                                'desktop': 0,
                                'total': 0,
                                'field_id': [field.client_id, field.object_id]}

                        for c_string in [client_string, 'total']:

                            entity_data[p_string][f_string][c_string] += entity_count
                            entity_data_total[p_string][f_string][c_string] += entity_count

                # Also counting unaccepted entities.
                #
                # They do not count towards top-level total, everything there is counted through published /
                # unpublished accounting just above.

                if accepted:
                    continue

                if 'unaccepted' not in entity_data:
                    entity_data['unaccepted'] = {}

                if 'unaccepted' not in entity_data_total:
                    entity_data_total['unaccepted'] = {}

                for f_string in [field.get_translation(locale_id), 'total']:

                    if f_string not in entity_data['unaccepted']:

                        entity_data['unaccepted'][f_string] = {
                            'web': 0,
                            'desktop': 0,
                            'total': 0,
                            'field_id': [field.client_id, field.object_id]}

                    if f_string not in entity_data_total['unaccepted']:

                        entity_data_total['unaccepted'][f_string] = {
                            'web': 0,
                            'desktop': 0,
                            'total': 0,
                            'field_id': [field.client_id, field.object_id]}

                    for c_string in [client_string, 'total']:

                        entity_data['unaccepted'][f_string][c_string] += entity_count
                        entity_data_total['unaccepted'][f_string][c_string] += entity_count

        # Returning gathered statistics.

        log.debug(
            f'\nstat_perspective {perspective_id} from {time_begin_str} to {time_end_str}:\n' +
            pprint.pformat(
                user_data_dict, width = 144))

        return user_data_dict

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = (

            ''.join(
                traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1])

        log.warning('stat_perspective: exception')
        log.warning('\n' + traceback_string)

        raise (

            ResponseError(
                'Exception:\n' + traceback_string))


def stat_condition_list(
    condition_list,
    time_begin = None,
    time_end = None,
    locale_id = None):
    """
    Gathers cumulative user participation statistics for all perspectives by an SQLAlchemy query condition
    list, in a given time interval [time_begin, time_end).

    Parameters 'time_begin' and 'time_end' are Unix timestamps if specified.
    """

    primary_locale_id = (
        int(locale_id or ENGLISH_LOCALE))

    secondary_locale_id = (
        ENGLISH_LOCALE if primary_locale_id != ENGLISH_LOCALE else
        RUSSIAN_LOCALE)

    # And now we are going to count lexical entries, we begin with basic perspective/lexical entry view.

    entry_query = (

        DBSession

            .query(
                entry_client_id_e,
                entry_created_at_e,
                DictionaryPerspective.state_translation_gist_client_id.label('state_client_id'),
                DictionaryPerspective.state_translation_gist_object_id.label('state_object_id'))

            .filter(
                *condition_list,

                LexicalEntry.parent_client_id == DictionaryPerspective.client_id,
                LexicalEntry.parent_object_id == DictionaryPerspective.object_id,
                LexicalEntry.marked_for_deletion == False)

            .subquery())

    # Selecting lexical entries inside the specified time interval, grouping by clients and perspective
    # states.

    entry_count_query = (

        with_time_filter(

            DBSession
                .query(
                    entry_query.c.entry_client_id,
                    entry_query.c.state_client_id,
                    entry_query.c.state_object_id,
                    func.count('*').label('entry_count')),

            entry_query.c.entry_created_at,
            time_begin,
            time_end)

            .group_by(
                entry_query.c.entry_client_id,
                entry_query.c.state_client_id,
                entry_query.c.state_object_id)

            .subquery())

    # Queries for translations of perspective states, works analogously to 'get_translation()' method in
    # the 'models' module, just through SQL.

    StateTranslation = (
        aliased(TranslationGist, name = 'StateTranslation'))

    StatePrimaryAtom = (
        aliased(TranslationAtom, name = 'StatePrimaryAtom'))

    StateSecondaryAtom = (
        aliased(TranslationAtom, name = 'StateSecondaryAtom'))

    state_primary_query = (

        DBSession
            .query(StatePrimaryAtom.content)

            .filter(
                StatePrimaryAtom.parent_client_id == StateTranslation.client_id,
                StatePrimaryAtom.parent_object_id == StateTranslation.object_id,
                StatePrimaryAtom.locale_id == primary_locale_id)

            .limit(1)
            .subquery())

    state_secondary_query = (

        DBSession
            .query(StateSecondaryAtom.content)

            .filter(
                StateSecondaryAtom.parent_client_id == StateTranslation.client_id,
                StateSecondaryAtom.parent_object_id == StateTranslation.object_id,
                StateSecondaryAtom.locale_id == secondary_locale_id)

            .limit(1)
            .subquery())

    perspective_state_query = (

        DBSession

            .query(
                StateTranslation.client_id,
                StateTranslation.object_id,

                func.coalesce(
                    state_primary_query.as_scalar(),
                    state_secondary_query.as_scalar(),
                    'UNDEFINED')

                    .label('content'))

            .subquery())

    # Adding client and user info and perspective state translations, grouping by users, web/desktop
    # clients and perspective states, aggregating entry counts.

    entry_count_list = (

        DBSession

            .query(
                Client.user_id,
                Client.is_browser_client,
                func.sum(entry_count_query.c.entry_count),
                perspective_state_query.c.content)

            .select_from(entry_count_query)

            .join(
                Client,
                Client.id == entry_count_query.c.entry_client_id)

            .join(
                perspective_state_query,
                and_(
                    perspective_state_query.c.client_id == entry_count_query.c.state_client_id,
                    perspective_state_query.c.object_id == entry_count_query.c.state_object_id))

            .group_by(
                Client.user_id,
                Client.is_browser_client,
                perspective_state_query.c.content)

            .all())

    # Aggregating lexical entry statistics.

    user_data_dict = {}

    if entry_count_list:

        user_data_total = {
            'login': None,
            'name': None,
            'lexical entries': {}}

        user_data_dict[None] = user_data_total

    for user_id, is_browser, entry_count, perspective_state in entry_count_list:

        if user_id not in user_data_dict:

            user = User.get(user_id)

            user_data_dict[user_id] = {
                'login': user.login,
                'name': user.name,
                'lexical entries': {}}

        # For each user we aggregate by perspective state and client type.

        entry_data = (
            user_data_dict[user_id]['lexical entries'])

        entry_data_total = (
            user_data_total['lexical entries'])

        client_string = (
            'web' if is_browser else 'desktop')

        for s_string in [perspective_state, 'total']:

            if s_string not in entry_data:

                entry_data[s_string] = {'web': 0, 'desktop': 0, 'total': 0}

            if s_string not in entry_data_total:

                entry_data_total[s_string] = {'web': 0, 'desktop': 0, 'total': 0}

            for c_string in [client_string, 'total']:

                entry_count_value = int(entry_count)

                entry_data[s_string][c_string] += entry_count_value
                entry_data_total[s_string][c_string] += entry_count_value

    # Getting info of all fields of all perspectives of the dictionary.

    field_data_list = (

        DBSession
            .query(Field)

            .filter(
                *condition_list,

                DictionaryPerspectiveToField.parent_client_id == DictionaryPerspective.client_id,
                DictionaryPerspectiveToField.parent_object_id == DictionaryPerspective.object_id,
                DictionaryPerspectiveToField.marked_for_deletion == False,

                Field.client_id == DictionaryPerspectiveToField.field_client_id,
                Field.object_id == DictionaryPerspectiveToField.field_object_id,
                Field.marked_for_deletion == False)

            .distinct()
            .all())

    # Sorting fields into simple and grouping categories.

    simple_field_id_list = []
    grouping_field_id_list = []

    for field in field_data_list:

        data_type = field.data_type.lower()

        if data_type in simple_field_type_set:

            simple_field_id_list.append(field.id)

        elif data_type == 'grouping tag':

            grouping_field_id_list.append(field.id)

        else:

            raise ResponseError(f'Unknown field data type \'{data_type}\'.')

    # Some parts of the counting and aggregation process are shared for simple and grouping fields, so
    # we process both these field types together.

    simple_field_id_list.sort()
    grouping_field_id_list.sort()

    for field_id_list, field_type in [
        (simple_field_id_list, 'simple'),
        (grouping_field_id_list, 'grouping')]:

        # We are going to count entites of fields of simple type.

        if field_type == 'simple':

            entity_query = (

                DBSession.query(
                    entity_client_id_e,
                    entity_created_at_e,

                    DictionaryPerspective.state_translation_gist_client_id.label('state_client_id'),
                    DictionaryPerspective.state_translation_gist_object_id.label('state_object_id'),

                    Entity.field_client_id,
                    Entity.field_object_id,

                    PublishingEntity.published)

                .filter(
                    *condition_list,

                    LexicalEntry.parent_client_id == DictionaryPerspective.client_id,
                    LexicalEntry.parent_object_id == DictionaryPerspective.object_id,
                    LexicalEntry.marked_for_deletion == False,

                    Entity.parent_client_id == LexicalEntry.client_id,
                    Entity.parent_object_id == LexicalEntry.object_id,
                    Entity.marked_for_deletion == False,

                    tuple_(
                        Entity.field_client_id,
                        Entity.field_object_id)

                        .in_(
                            ids_to_id_query(field_id_list)),

                    PublishingEntity.client_id == Entity.client_id,
                    PublishingEntity.object_id == Entity.object_id)

                .subquery())

            # Selecting entities inside the specified time interval, grouping by clients, perspective
            # states, fields and publishing status.

            entity_count_query = (

                with_time_filter(

                    DBSession.query(
                        entity_query.c.entity_client_id,

                        entity_query.c.state_client_id,
                        entity_query.c.state_object_id,

                        entity_query.c.field_client_id,
                        entity_query.c.field_object_id,

                        entity_query.c.published,
                        func.count('*').label('entity_count')),

                    entity_query.c.entity_created_at,
                    time_begin,
                    time_end)

                    .group_by(
                        entity_query.c.entity_client_id,

                        entity_query.c.state_client_id,
                        entity_query.c.state_object_id,

                        entity_query.c.field_client_id,
                        entity_query.c.field_object_id,

                        entity_query.c.published)

                    .subquery())

        # We are going to count entites of fields of grouping type.

        else:

            entity_query = (

                DBSession

                    .query(
                        LexicalEntry.client_id,
                        LexicalEntry.object_id,

                        entity_client_id_e,
                        entity_created_at_e,

                        DictionaryPerspective.state_translation_gist_client_id.label('state_client_id'),
                        DictionaryPerspective.state_translation_gist_object_id.label('state_object_id'),

                        Entity.field_client_id,
                        Entity.field_object_id,

                        PublishingEntity.published)

                .filter(
                    *condition_list,

                    LexicalEntry.parent_client_id == DictionaryPerspective.client_id,
                    LexicalEntry.parent_object_id == DictionaryPerspective.object_id,
                    LexicalEntry.marked_for_deletion == False,

                    Entity.parent_client_id == LexicalEntry.client_id,
                    Entity.parent_object_id == LexicalEntry.object_id,
                    Entity.marked_for_deletion == False,

                    tuple_(
                        Entity.field_client_id,
                        Entity.field_object_id)

                        .in_(
                            ids_to_id_query(field_id_list)),

                    PublishingEntity.client_id == Entity.client_id,
                    PublishingEntity.object_id == Entity.object_id)

                .subquery())

            # Grouping tags are first grouped by lexical entries.

            entry_group_query = (

                with_time_filter(

                    DBSession.query(
                        entity_query.c.entity_client_id,

                        entity_query.c.state_client_id,
                        entity_query.c.state_object_id,

                        entity_query.c.field_client_id,
                        entity_query.c.field_object_id,

                        entity_query.c.published),

                    entity_query.c.entity_created_at,
                    time_begin,
                    time_end)

                    .group_by(
                        entity_query.c.client_id,
                        entity_query.c.object_id,

                        entity_query.c.entity_client_id,

                        entity_query.c.state_client_id,
                        entity_query.c.state_object_id,

                        entity_query.c.field_client_id,
                        entity_query.c.field_object_id,

                        entity_query.c.published)

                    .subquery())

            # Grouping by clients, perspective states, fields and publishing status.

            entity_count_query = (

                DBSession

                    .query(
                        entry_group_query.c.entity_client_id,

                        entry_group_query.c.state_client_id,
                        entry_group_query.c.state_object_id,

                        entry_group_query.c.field_client_id,
                        entry_group_query.c.field_object_id,

                        entry_group_query.c.published,
                        func.count('*').label('entity_count'))

                    .group_by(
                        entry_group_query.c.entity_client_id,

                        entry_group_query.c.state_client_id,
                        entry_group_query.c.state_object_id,

                        entry_group_query.c.field_client_id,
                        entry_group_query.c.field_object_id,

                        entry_group_query.c.published)

                    .subquery())

        # Queries for translations of field names.

        FieldTranslation = (
            aliased(TranslationGist, name = 'FieldTranslation'))

        FieldPrimaryAtom = (
            aliased(TranslationAtom, name = 'FieldPrimaryAtom'))

        FieldSecondaryAtom = (
            aliased(TranslationAtom, name = 'FieldSecondaryAtom'))

        field_primary_query = (

            DBSession
                .query(FieldPrimaryAtom.content)

                .filter(
                    FieldPrimaryAtom.parent_client_id == FieldTranslation.client_id,
                    FieldPrimaryAtom.parent_object_id == FieldTranslation.object_id,
                    FieldPrimaryAtom.locale_id == primary_locale_id)

                .limit(1)
                .subquery())

        field_secondary_query = (

            DBSession
                .query(FieldSecondaryAtom.content)

                .filter(
                    FieldSecondaryAtom.parent_client_id == FieldTranslation.client_id,
                    FieldSecondaryAtom.parent_object_id == FieldTranslation.object_id,
                    FieldSecondaryAtom.locale_id == secondary_locale_id)

                .limit(1)
                .subquery())

        # Getting mapping from field ids to field names.

        field_name_query = (

            DBSession

                .query(
                    Field.client_id,
                    Field.object_id,

                    func.coalesce(
                        field_primary_query.as_scalar(),
                        field_secondary_query.as_scalar(), 'UNDEFINED')

                        .label('content'))

                .filter(
                    Field.translation_gist_client_id == FieldTranslation.client_id,
                    Field.translation_gist_object_id == FieldTranslation.object_id)

                .subquery())

        # Grouping entities and aggregating entity counts.

        entity_count_list = (

            DBSession

                .query(
                    Client.user_id,
                    Client.is_browser_client,
                    func.sum(entity_count_query.c.entity_count),
                    perspective_state_query.c.content,
                    field_name_query.c.content,
                    entity_count_query.c.published)

                .select_from(
                    entity_count_query)

                # Adding client/user info and perspective state / field name translations

                .join(
                    Client,
                    Client.id == entity_count_query.c.entity_client_id)

                .join(
                    perspective_state_query,
                    and_(
                        perspective_state_query.c.client_id == entity_count_query.c.state_client_id,
                        perspective_state_query.c.object_id == entity_count_query.c.state_object_id))

                .join(
                    field_name_query,
                    and_(
                        field_name_query.c.client_id == entity_count_query.c.field_client_id,
                        field_name_query.c.object_id == entity_count_query.c.field_object_id))

                # Grouping by users, web/desktop clients, perspective states, field names and publishing
                # status.

                .group_by(
                    Client.user_id,
                    Client.is_browser_client,
                    perspective_state_query.c.content,
                    field_name_query.c.content,
                    entity_count_query.c.published)

                .all())

        # Aggregating statistics for entities of simple type.

        for (user_id, is_browser, entity_count,
            perspective_state, field_name, published) in entity_count_list:

            if user_id not in user_data_dict:

                user = User.get(user_id)

                user_data_dict[user_id] = {
                    'login': user.login, 'name': user.name,
                    'entities': {}}

            user_data = user_data_dict[user_id]

            if 'entities' not in user_data:

                user_data['entities'] = {}

            if 'entities' not in user_data_total:

                user_data_total['entities'] = {}

            # For each user we aggregate by perspective state, publishing status, field name and client
            # type.

            entity_data = (
                user_data['entities'])

            entity_data_total = (
                user_data_total['entities'])

            client_string = (
                'web' if is_browser else 'desktop')

            published_string = (
                'published' if published else 'unpublished')

            for s_string in [perspective_state, 'total']:

                if s_string not in entity_data:

                    entity_data[s_string] = {'published': {}, 'unpublished': {}, 'total': {}}

                if s_string not in entity_data_total:

                    entity_data_total[s_string] = {'published': {}, 'unpublished': {}, 'total': {}}

                for p_string in [published_string, 'total']:

                    local_entity_data = (
                        entity_data[s_string][p_string])

                    local_entity_data_total = (
                        entity_data_total[s_string][p_string])

                    for f_string in [field_name, 'total']:

                        if f_string not in local_entity_data:

                            local_entity_data[f_string] = {'web': 0, 'desktop': 0, 'total': 0}

                        if f_string not in local_entity_data_total:

                            local_entity_data_total[f_string] = {'web': 0, 'desktop': 0, 'total': 0}

                        for c_string in [client_string, 'total']:

                            entity_count_value = int(entity_count)

                            local_entity_data[f_string][c_string] += entity_count_value
                            local_entity_data_total[f_string][c_string] += entity_count_value

    return user_data_dict


def stat_dictionary(
    dictionary_id,
    time_begin = None,
    time_end = None,
    locale_id = None):
    """
    Gathers cumulative user participation statistics for all perspectives of a specified dictionary in a
    given time interval [time_begin, time_end).

    Parameters 'time_begin' and 'time_end' are Unix timestamps if specified.
    """

    try:

        time_begin_str, time_end_str = (

            time_format(
                time_begin,
                time_end))

        log.debug(
            f'\nstat_dictionary {dictionary_id} from {time_begin_str} to {time_end_str}')

        # Starting with dictionary check.

        dictionary = (
            Dictionary.get(dictionary_id))

        if not dictionary:
            raise ResponseError(f'No dictionary {dictionary_id}.')

        # Getting statistics for all perspectives of a single dictionary.

        condition_list = [

            DictionaryPerspective.parent_client_id == dictionary_id[0],
            DictionaryPerspective.parent_object_id == dictionary_id[1],
            DictionaryPerspective.marked_for_deletion == False]

        user_data_dict = (

            stat_condition_list(
                condition_list,
                time_begin,
                time_end,
                locale_id))

        # Returning gathered statistics.

        log.debug(
            f'\nstat_dictionary {dictionary_id} from {time_begin_str} to {time_end_str}:\n' +
            pprint.pformat(
                user_data_dict, width = 144))

        return user_data_dict

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = (

            ''.join(
                traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1])

        log.warning('stat_dictionary: exception')
        log.warning('\n' + traceback_string)

        raise (

            ResponseError(
                'Exception:\n' + traceback_string))


def stat_language(
    language_id,
    time_begin = None,
    time_end = None,
    dictionaries = False,
    corpora = False,
    locale_id = None):

    try:

        time_begin_str, time_end_str = (

            time_format(
                time_begin,
                time_end))

        log.debug(
            f'\nstat_language {language_id}'
            f'\n from {time_begin_str} to {time_end_str},'
            f'\n dictionaries: {dictionaries}, corpora: {corpora}')

        # Ok, now working, starting with language check and checking if we actually need to get any data.

        language = (
            Language.get(language_id))

        if not language:
            raise ResponseError(f'No language {language_id}.')

        if (not dictionaries and
            not corpora):

            return {}

        # Base language-recursive CTE.

        base_cte = (

            ids_to_id_query(
                (language_id,),
                explicit_cast = True)

                .cte(recursive = True))

        recursive_query = (

            DBSession

                .query(
                    Language.client_id,
                    Language.object_id)

                .filter(
                    Language.parent_client_id == base_cte.c.client_id,
                    Language.parent_object_id == base_cte.c.object_id,
                    Language.marked_for_deletion == False))

        language_cte = (
            base_cte.union(recursive_query))

        # Source perspective conditions, with dictionary/corpora conditions if required.

        condition_list = [

            Dictionary.parent_client_id == language_cte.c.client_id,
            Dictionary.parent_object_id == language_cte.c.object_id,
            Dictionary.marked_for_deletion == False,

            DictionaryPerspective.parent_client_id == Dictionary.client_id,
            DictionaryPerspective.parent_object_id == Dictionary.object_id,
            DictionaryPerspective.marked_for_deletion == False]

        if dictionaries and corpora:
            pass

        elif dictionaries:

            condition_list.append(
                Dictionary.category == 0)

        elif corpora:

            condition_list.append(
                Dictionary.category == 1)

        # Getting and returning statistics for all perspectives.

        user_data_dict = (

            stat_condition_list(
                condition_list,
                time_begin,
                time_end,
                locale_id))

        log.debug(
            f'\nstat_language {language_id}'
            f'\n from {time_begin_str} to {time_end_str},'
            f'\n dictionaries: {dictionaries}, corpora: {corpora}' +
            pprint.pformat(
                user_data_dict, width = 144))

        return user_data_dict

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = (

            ''.join(
                traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1])

        log.warning('stat_language: exception')
        log.warning('\n' + traceback_string)

        raise (

            ResponseError(
                'Exception:\n' + traceback_string))

