
# Standard library imports.

import collections
import copy
import itertools
import json
import logging
import math
import pprint
import traceback

# External imports.

import pylev
from pyramid.response import Response
from pyramid.request import Request
from pyramid.view import view_config

from sqlalchemy import and_, BigInteger, cast, extract, func, tuple_, create_engine
from sqlalchemy.orm import aliased

from pyramid.view import view_config

from sqlalchemy.orm.attributes import flag_modified

from transaction import manager

# Lingvodoc imports.

from lingvodoc.cache.caching import initialize_cache, TaskStatus

import lingvodoc.merge_perspectives as merge_perspectives
from lingvodoc.merge_perspectives import mergeDicts
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
    DictionaryPerspective,
    ObjectTOC
)

from lingvodoc.views.v2.utils import message, unimplemented
from lingvodoc.utils.creation import add_user_to_group
from lingvodoc.schema.gql_holders import ResponseError

from lingvodoc.views.v2.utils import (
    message,
    remove_deleted,
    unimplemented
)

from lingvodoc.queue.celery import celery


log = logging.getLogger(__name__)


def check_user_merge_permissions(
    request, user,
    dictionary_client_id, dictionary_object_id,
    perspective_client_id, perspective_object_id):
    """
    Checks if the user has permissions required to merge lexical entries and entities, i.e. permissions to
    create and delete them, via perspective user role subrequest.
    """

    create_base_group = DBSession.query(BaseGroup).filter_by(
        subject = 'lexical_entries_and_entities', action = 'create').first()

    delete_base_group = DBSession.query(BaseGroup).filter_by(
        subject = 'lexical_entries_and_entities', action = 'delete').first()

    #
    # Getting perspective permissions for all users.
    #
    # NOTE:
    #
    # Obviously theoretically we can make this check more efficient by querying for the specified user, but
    # at the moment we need correctness provided by a subrequest more then efficiency provided by a direct
    # DB query.
    #
    # If the need arises, we would add to roles REST API user-specific perspective roles method.
    #

    url = request.route_url('perspective_roles',
        client_id = dictionary_client_id,
        object_id = dictionary_object_id,
        perspective_client_id = perspective_client_id,
        perspective_object_id = perspective_object_id)

    subrequest = Request.blank(url)
    subrequest.method = 'GET'
    subrequest.headers = request.headers

    result = request.invoke_subrequest(subrequest)

    log.debug('check_user_merge_permissions: user {0}, perspective {1}/{2}: roles\n{3}'.format(
        user.id, perspective_client_id, perspective_object_id, pprint.pformat(result.json)))

    # Checking if the user themselves can create and delete lexical entries and entities.

    if (user.id in result.json['roles_users'][create_base_group.name] and
        user.id in result.json['roles_users'][delete_base_group.name]):

        return True

    # Checking if the user has required permissions through one of their organizations.

    organization_create = any(organization_id in user.organizations
        for organization_id in result.json['roles_organizations'][create_base_group.name])

    organization_delete = any(organization_id in user.organizations
        for organization_id in result.json['roles_organizations'][delete_base_group.name])

    if organization_create and organization_delete:
        return True

    # Ok, so the user doesn't have permissions.

    return False




#: Set of statistically simple field types, statistics of entities belonging to fields with these types are
#: simple counts.


def merge_suggestions(request, perspective_client_id, perspective_object_id, algorithm, threshold=0.1,
                      entity_type_primary='Transcription', entity_type_secondary='Translation', levenshtein=1,
                      field_selection_list=None, locale_id=2):
    """
    Finds groups of mergeable lexical entries according to specified criteria.
    """

    if algorithm not in {'simple', 'fields'}:
        raise ResponseError('Unknown entity matching algorithm \'{0}\'.'.format(algorithm))

    # Getting merge suggestions options.

    log.debug('merge_suggestions {0}/{1}'.format(
        perspective_client_id, perspective_object_id))

    # Checking if the user has sufficient permissions to perform suggested merges.

    user = Client.get_user_by_client_id(request.authenticated_userid)

    perspective = DBSession.query(DictionaryPerspective).filter_by(
        client_id = perspective_client_id, object_id = perspective_object_id).first()

    user_has_permissions = check_user_merge_permissions(
        request, user,
        perspective.parent_client_id, perspective.parent_object_id,
        perspective_client_id, perspective_object_id)

    # Getting data of the undeleted lexical entries of the perspective.

    lexical_entry_list = list(DBSession.query(LexicalEntry).filter_by(
        parent_client_id = perspective_client_id,
        parent_object_id = perspective_object_id,
        marked_for_deletion = False).all())

    if not lexical_entry_list:

        log.debug('merge_suggestions {0}/{1}: 0 lexical entries'.format(
            perspective_client_id, perspective_object_id))

        return {
            'entry_data': [],
            'match_result': [],
            'user_has_permissions': user_has_permissions}

    entry_data_list = [l.track(False, locale_id) for l in lexical_entry_list]
    remove_deleted(entry_data_list)

    log.debug('merge_suggestions {0}/{1}: {2} lexical entries'.format(
        perspective_client_id, perspective_object_id, len(entry_data_list)))

    # Matching lexical entries.

    if algorithm == 'simple':

        match_result_list = match_simple(entry_data_list,
            entity_type_primary, entity_type_secondary, threshold, levenshtein)

    else:
        match_result_list = match_fields(entry_data_list, field_selection_list, threshold)

    log.debug('merge_suggestions {0}/{1}: {2} matches'.format(
        perspective_client_id, perspective_object_id, len(match_result_list)))

    if not match_result_list:

        return {
            'match_result': [],
            'user_has_permissions': user_has_permissions}

    # Returning match data together with data of matching lexical entries.
    return {
        'match_result': [
            {"lexical_entries": [list(id_a), list(id_b)],
             "confidence": confidence}
            for id_a, id_b, confidence in match_result_list],

        'user_has_permissions': user_has_permissions}


def match_simple(entry_data_list, entity_type_primary, entity_type_secondary, threshold, levenshtein):
    """
    Matches lexical entries via an old, simple algorithm.

    Approximate description of the simple matching algorithm was reconstructed from the source code of
    functions parse_response and mergeDicts. Algorithms works as follows.

    Each lexical entry L is transformed into a feature vector V(L) given two text entity fields F1, F2:

    V(L) = [(f1, f2) | f1 in parts(E1), E1 in F1(L), f2 in parts(E2), E2 in F2(L)]

    E1 in F1(L) means that entity E1 is an entity of lexical entry L belonging to the field F1.

    parts(E) takes text contents of an entity E, removes all parenthesized substrings, splits by a set of
    punctuation characters and removes beginning/ending whitespace, see function getWordParts of the module
    merge_perspectives.

    Matching degree M(L1, L2) of a pair of lexical entries L1, L2:

    M(L1, L2) =
      count[(f11, f12) ~= (f21, f22) | (f11, f12) in V(L1), (f21, f22) in V(L2)] /
        (length(V(L1)) + length(V(L2)))

    f11, f12, f21, f22 --- feature strings.
    ~= --- feature matching relation.

    Features (f11, f12), (f21, f22) match if f11 == f21 и levenshtein(f12, f22) <= d.

    L1 and L2 are deemed sufficiently similar of M(L1, L2) >= t, where t is a matching threshold (with
    default value of 0.2).

    Matching result is a list of all similar enough pairs of lexical entries with their matching degrees.
    """

    def parse_response(entry_data):
        """
        Contructs description of a lexical entry to be used for matching.
        """

        word_list = map(lambda x: x.get('content', ''), filter(
            lambda x: x['entity_type'] == entity_type_primary and not x['marked_for_deletion'],
            entry_data['contains']))

        translation_list = map(lambda x: x.get('content', ''), filter(
            lambda x: x['entity_type'] == entity_type_secondary and not x['marked_for_deletion'],
            entry_data['contains']))

        return [
            (word, translation, (entry_data['client_id'], entry_data['object_id']))
                for word in word_list
                for translation in translation_list]

    # Matching lexical entries.

    match_data_list = list(
        itertools.chain.from_iterable(map(parse_response, entry_data_list)))

    if not match_data_list:
        return []

    return mergeDicts(
        match_data_list, match_data_list, float(threshold), int(levenshtein))


def match_fields(entry_data_list, field_selection_list, threshold):
    """
    Matches lexical entries via a newer, more flexible algorithm (cf. match_simple).

    Description of this algorithm follows.

    Each lexical entry L transformed into a feature vector V(L) given fields F1, ..., Fn:

    V(L) = V(F1, L) + ... + V(Fn, L)

    V(F, L) | F is a text field = [(F, x) | x in parts(F, E), E in F(L)]
    V(F, L) | F is a link field = [(F, link_id(E)) | E in F(L)]
    V(F, L) | F is a hash field = [(F, hash(E)) | E in F(L)]

    parts(F, E) should take contents of an entity E, remove all parenthesized substring, split by
    punctuation characters and/or by whitespace and remove beginning/ending whitespace.

    Matching degree M(L1, L2) of a pair of lexical entries L1, L2:

    M(L1, L2) =
      count[(f1, x1) ~= (f2, x2) | (f1, x1) in V(L1), (f2, x2) in V(L2)] /
        (length(V(L1)) + length(V(L2)))

    f1, f2 --- fields from the list F1, ..., Fn.
    x1, x2 --- feature strings, link ids or hashes depending on fields f1 and f2.
    ~= --- feature matching relation.

    Features (f1, x1), (f2, x2) match, if f1 = f2 = F and
      case F is a text field: levenshtein(x1, x2) <= d(F),
      case F is a link or hash field: x1 = x2.

    L1 and L2 are deemed sufficiently similar of M(L1, L2) >= t, where t is a matching threshold (with
    default value of 0.2).

    Matching result is a list of all similar enough pairs of lexical entries with their matching degrees.
    """

    def make_extractor(field_selection):
        """
        Makes feature extractor based on field selection info.
        """

        def extract_text(entity_data):
            """
            Extracts list of text features based on field selection options.
            """

            content, n = merge_perspectives.braces.subn("", entity_data.get('content', ''))
            while n > 0:
                content, n = merge_perspectives.braces.subn("", content)

            content_list = [content]

            if field_selection['split_punctuation']:
                content_list = itertools.chain(*[
                    merge_perspectives.punct.split(content) for content in content_list])

            if field_selection['split_space']:
                content_list = itertools.chain(*[
                    merge_perspectives.punct.split(content) for content in content_list])

            feature_set = set(content.strip() for content in content_list)
            feature_set.discard('')

            return feature_set

        # Choosing extractor based on field selection type.

        if field_selection['type'] == 'text':
            return extract_text

        elif field_selection['type'] == 'hash':
            return (lambda entity_data: (yield entity_data['additional_metadata']['hash']))

        else:
            raise Exception('Unknown field type \'{0}\'.'.format(field_selection['type']))

    # Sorting field selections by fields.

    field_data_dict = {}

    for field_selection in field_selection_list:
        field_id = (field_selection['field_id'][0], field_selection['field_id'][1])

        if field_id not in field_data_dict:
            field_data_dict[field_id] = ([field_selection], [])

        else:
            field_data_dict[field_id][0].append(field_selection)

    # Sorting entities by fields.

    for entry_data in entry_data_list:
        for entity_data in entry_data['contains']:

            maybe_field_data = field_data_dict.get(
                (entity_data['field_client_id'], entity_data['field_object_id']))

            if maybe_field_data is not None:
                maybe_field_data[1].append(entity_data)

    # Memoized computation of Levenshtein distance.

    levenshtein_cache = {}

    def levenshtein(string_a, string_b):
        """
        Computes Levenshtein distances with memoization.
        """

        if string_a > string_b:
            string_a, string_b = string_b, string_a

        result = levenshtein_cache.get((string_a, string_b))

        if result is not None:
            return result

        result = pylev.levenshtein(string_a, string_b)
        levenshtein_cache[(string_a, string_b)] = result

        return result

    # Processing entity data by fields and fields selections.

    count_dict = collections.Counter()
    match_dict = collections.Counter()

    for field_id, (field_selection_list, entity_data_list) in field_data_dict.items():

        for field_selection in field_selection_list:
            extractor = make_extractor(field_selection)

            # Processing discrete features.

            if (field_selection['type'] != 'text' or
                field_selection['levenshtein'] <= 0):

                feature_dict = collections.defaultdict(set)

                for entity_data in entity_data_list:
                    entry_id = (entity_data['parent_client_id'], entity_data['parent_object_id'])

                    for feature in extractor(entity_data):
                        feature_dict[feature].add(entry_id)

                log.debug('feature_dict:\n' + pprint.pformat(feature_dict))

                for entry_id_set in feature_dict.values():
                    entry_id_list = sorted(entry_id_set)

                    for index, entry_id in enumerate(entry_id_list):
                        count_dict[entry_id] += 1

                        for other_id in entry_id_list[index + 1:]:
                            match_dict[(entry_id, other_id)] += 1

            # Processing Levenshtein-comparable features.

            else:
                limit = field_selection['levenshtein']

                entry_feature_dict = collections.defaultdict(set)
                feature_entry_dict = collections.defaultdict(set)

                for entity_data in entity_data_list:
                    entry_id = (entity_data['parent_client_id'], entity_data['parent_object_id'])

                    for feature in extractor(entity_data):
                        entry_feature_dict[entry_id].add(feature)
                        feature_entry_dict[feature].add(entry_id)

                for entry_id, feature_set in entry_feature_dict.items():
                    count_dict[entry_id] += len(feature_set)

                log.debug('entry_feature_dict:\n' + pprint.pformat(entry_feature_dict))
                log.debug('feature_entry_dict:\n' + pprint.pformat(feature_entry_dict))

                # At the moment we have to compute N^2/2 Levenshtein distances. If such computations will be
                # found too time consuming, we can try optimized Levenshtein distance computation with
                # prefix sharing and lazy evaluations.

                levenshtein_dict = collections.defaultdict(list)
                feature_list = sorted(feature_entry_dict.keys())

                for index, feature_a in enumerate(feature_list):
                    for feature_b in feature_list[index + 1:]:

                        if levenshtein(feature_a, feature_b) <= limit:
                            levenshtein_dict[feature_a].append(feature_b)

                log.debug('feature_list:\n' + pprint.pformat(feature_list))
                log.debug('levenshtein_dict:\n' + pprint.pformat(levenshtein_dict))

                # Any match between features is a match between their corresponding entries. At first we
                # process matches on equal features.

                for feature in feature_list:
                    entry_id_list = sorted(feature_entry_dict[feature])

                    for index, entry_id in enumerate(entry_id_list):
                        for other_id in entry_id_list[index + 1:]:

                            match_dict[(entry_id, other_id)] += 1

                # Then we process matches on different, but sifficiently Levenshtein-similar, features.

                for feature, match_list in levenshtein_dict.items():

                    entry_id_set = feature_entry_dict[feature]

                    other_id_list = list(itertools.chain(
                        *[feature_entry_dict[match] for match in match_list]))

                    for entry_id in entry_id_set:
                        for other_id in other_id_list:

                            if entry_id == other_id:
                                continue

                            key = ((entry_id, other_id)
                                if entry_id <= other_id else (other_id, entry_id))

                            match_dict[key] += 1

    # Compiling and returning matching result.

    log.debug('count_dict:\n' + pprint.pformat(count_dict))
    log.debug('match_dict:\n' + pprint.pformat(match_dict))

    result_list = []

    for (id_a, id_b), count in match_dict.items():
        score = float(count) / (count_dict[id_a] + count_dict[id_b])

        if score >= threshold:
            result_list.append((id_a, id_b, score))

    result_list.sort()
    log.debug('result_list:\n' + pprint.pformat(result_list))

    return result_list


def build_merge_tree(entry):
    """
    Recursively builds merge tree of a 1st or 2nd version merged lexical entry, compiles merge authorship
    info.
    """

    source_list = DBSession.query(LexicalEntry).filter(
        LexicalEntry.additional_metadata['merged_to'] == [entry.client_id, entry.object_id]).all()

    source_list.sort(key = lambda source: (source.client_id, source.object_id))

    log.debug('build_merge_tree {0}/{1}: {2} source entr{3}'.format(
        entry.client_id, entry.object_id, len(source_list), 'y' if len(source_list) == 1 else 'ies'))

    entry_min_created_at = None
    entry_original_client_id = None
    entry_merge_tree = []

    # Looking through all lexical entries merged into the given one.

    for index, source in enumerate(source_list):

        if 'merge_tag' in source.additional_metadata:

            source_type = '\'merge_tag\' (version 1)'
            min_created_at, original_client_id, merge_tree = build_merge_tree(source)

        elif ('merge' in source.additional_metadata and
            'original_author' in source.additional_metadata['merge']):

            source_type = '\'merge\' (version 2)'
            min_created_at, original_client_id, merge_tree = build_merge_tree(source)

        elif 'merge' in source.additional_metadata:

            source_type = '\'merge\' (version 3)'

            # NOTE: For possible use by merge metadata updaters.

            min_created_at = source.additional_metadata['merge']['min_created_at']
            original_client_id = source.additional_metadata['merge']['original_client_id']
            merge_tree = copy.deepcopy(source.additional_metadata['merge']['merge_tree'])

        else:
            source_type = None

            min_created_at = source.created_at
            original_client_id = source.client_id
            merge_tree = [source.client_id, source.object_id]

        # Updating merge tree and merge authorship info.

        if (entry_min_created_at is None or
            min_created_at < entry_min_created_at):

            entry_min_created_at = min_created_at
            entry_original_client_id = original_client_id

        entry_merge_tree.append(merge_tree)

        log.debug('build_merge_tree {0}/{1}: source {2}/{3} [{4}]: {5}'.format(
            entry.client_id, entry.object_id, source.client_id, source.object_id, index, source_type))

    # Returning merge tree data.

    log.debug('build_merge_tree {0}/{1}: result\n{2}'.format(
        entry.client_id, entry.object_id,

        pprint.pformat({
            'min_created_at': entry_min_created_at,
            'original_client_id': entry_original_client_id,
            'merge_tree': entry_merge_tree})))

    return entry_min_created_at, entry_original_client_id, entry_merge_tree


class Merge_Context(object):
    """
    Data and procedures of the bulk merges.
    """

    def __init__(self, method_string, request, client_id, user, publish_any, group_list):
        """
        Initialization of the merge data.
        """

        self.method_string = method_string
        self.request = request
        self.client_id = client_id
        self.user = user

        self.publish_any = publish_any
        self.group_list = group_list

        self.entry_count = sum(len(entry_id_list) for entry_id_list in group_list)

        log.debug('{0}: {1} lexical entry group{2}, {3} entries:\n{4}'.format(
            method_string,
            len(group_list),
            '' if len(group_list) == 1 else 's',
            self.entry_count,
            pprint.pformat(group_list)))

        self.user_permission_dict = {}
        self.result_list = []

    def check_permissions(self, perspective_client_id, perspective_object_id):
        """
        Checks if the user has permissions to create/delete lexical entries and entities of a specified
        perspective, preferably using memoized permission values.
        """

        if (perspective_client_id, perspective_object_id) in self.user_permission_dict:
            return self.user_permission_dict[(perspective_client_id, perspective_object_id)]

        perspective = DBSession.query(DictionaryPerspective).filter_by(
            client_id = perspective_client_id, object_id = perspective_object_id).first()

        user_has_permissions = check_user_merge_permissions(
            self.request, self.user,
            perspective.parent_client_id, perspective.parent_object_id,
            perspective_client_id, perspective_object_id)

        self.user_permission_dict[(perspective_client_id, perspective_object_id)] = user_has_permissions

        return user_has_permissions

    def new_entity_dict(self, merge_entity_set, entity_data):
        """
        Creates new entity merge data.
        """

        additional_metadata = entity_data.get('additional_metadata', {})

        # As of now (Sun Jan 22 15:20:57 UTC 2017), we only support dicts as additional metadata.

        if not isinstance(additional_metadata, dict):
            raise Exception('Unsupported additional metadata '
                'type \'{0}\'.'.format(type(additional_metadata)))

        min_created_at = entity_data['created_at']
        original_client_id = entity_data['client_id']

        if 'merge' in additional_metadata:

            merge_metadata = additional_metadata['merge']
            del additional_metadata['merge']

            min_created_at = merge_metadata['min_created_at']
            original_client_id = merge_metadata['original_client_id']

        if 'merged_to' in additional_metadata:
            del additional_metadata['merged_to']

        if 'merged_by' in additional_metadata:
            del additional_metadata['merged_by']

        # Initializing merged entity data.

        entity_dict = {

            'additional_metadata': {
                'merge': {
                    'min_created_at': min_created_at,
                    'original_client_id': original_client_id}},

            'contains': {},
            'merge_set': set([(entity_data['client_id'], entity_data['object_id'])])}

        merge_entity_set.add((entity_data['client_id'], entity_data['object_id']))

        for name in ['accepted', 'data_type', 'entity_type',
            'field_client_id', 'field_object_id', 'level', 'locale_id', 'published']:

            entity_dict[name] = entity_data[name]

        # Merging metadata, entity contents and containing entities.

        self.metadata_merge(entity_dict['additional_metadata'], additional_metadata)

        if 'content' in entity_data:
            entity_dict['content'] = entity_data['content']

        if 'link_client_id' in entity_data:
            entity_dict['link_client_id'] = entity_data['link_client_id']
            entity_dict['link_object_id'] = entity_data['link_object_id']

        self.merge_contains(
            entity_dict['contains'], merge_entity_set,
            entity_data['contains'], (entity_data['client_id'], entity_data['object_id']))

        return entity_dict

    def merge_entity_dict(self, entity_dict, merge_entity_set, entity_data):
        """
        Updates entity merge data.
        """

        entity_id = (entity_data['client_id'], entity_data['object_id'])

        entity_dict['merge_set'].add(entity_id)
        merge_entity_set.add(entity_id)

        # Acceptedness of entities is processed via logical OR, publishing status either via OR or AND
        # depending on settings.

        entity_dict['accepted'] = entity_dict['accepted'] or entity_data['accepted']

        entity_dict['published'] = (
            entity_dict['published'] or entity_data['published'] if self.publish_any else
            entity_dict['published'] and entity_data['published'])

        additional_metadata = entity_data.get('additional_metadata', {})

        if not isinstance(additional_metadata, dict):
            raise Exception('Unsupported additional metadata '
                'type \'{0}\'.'.format(type(additional_metadata)))

        # Updating merge metadata.

        min_created_at = entity_data['created_at']
        original_client_id = entity_data['client_id']

        if 'merge' in additional_metadata:

            merge_metadata = additional_metadata['merge']
            del additional_metadata['merge']

            min_created_at = merge_metadata['min_created_at']
            original_client_id = merge_metadata['original_client_id']

        if 'merged_to' in additional_metadata:
            del additional_metadata['merged_to']

        if 'merged_by' in additional_metadata:
            del additional_metadata['merged_by']

        merge_dict = entity_dict['additional_metadata']['merge']

        if min_created_at < merge_dict['min_created_at']:
            merge_dict['min_created_at'] = min_created_at
            merge_dict['original_client_id'] = original_client_id

        # Merging metadata and subordinate entities.

        self.metadata_merge(entity_dict['additional_metadata'], additional_metadata)

        self.merge_contains(
            entity_dict['contains'], merge_entity_set,
            entity_data['contains'], (entity_data['client_id'], entity_data['object_id']))

    def merge_contains(self, contains_dict, merge_entity_set, contains_list, container_id):

        """
        Merges entities contained in a lexical entry or another entity to already merged entities.
        """

        for entity_data in contains_list:

            # Self-linked entities which are not part of the container are skipped.

            if ('self_client_id' in entity_data and
                (entity_data['self_client_id'], entity_data['self_object_id']) != container_id):
                continue

            if entity_data['data_type'] == 'Grouping Tag' or entity_data['data_type'] == 'Text':
                entity_key = (entity_data['entity_type'], entity_data.get('content', ''))

            elif entity_data['data_type'] == 'Link':
                entity_key = (entity_data['entity_type'],
                    (entity_data['link_client_id'], entity_data['link_object_id']))

            # Images, text markup and sound recordings are compared by hash.

            elif (entity_data['data_type'] == 'Image' or
                    entity_data['data_type'] == 'Markup' or
                    entity_data['data_type'] == 'Sound'):

                entity_key = (entity_data['entity_type'], entity_data['additional_metadata']['hash'])

            else:
                raise Exception('Can\'t merge entities of '
                    'type \'{0}\', please contact developers.'.format(entity_data['data_type']))

            # If we already have entity of the same type with the same data, we merge current entity
            # into it.

            if entity_key in contains_dict:

                self.merge_entity_dict(
                    contains_dict[entity_key], merge_entity_set, entity_data)

            else:
                contains_dict[entity_key] = self.new_entity_dict(merge_entity_set, entity_data)

    def metadata_merge(self, metadata_dict, another_dict):
        """
        Structurally merges metadata, assuming that metadata is either a list or a dict.
        """

        for key, value in another_dict.items():

            if key not in metadata_dict:
                metadata_dict[key] = copy.deepcopy(another_dict[key])

            elif (isinstance(metadata_dict[key], dict) and
                isinstance(another_dict[key], dict)):

                self.metadata_merge(metadata_dict[key], another_dict[key])

            elif (isinstance(metadata_dict[key], list) and
                isinstance(another_dict[key], list)):

                metadata_dict[key].extend(another_dict[key])

            elif isinstance(metadata_dict[key], set):
                metadata_dict[key].add(self.metadata_freeze(another_dict[key]))

            elif metadata_dict[key] != another_dict[key]:

                metadata_dict[key] = set(map(
                    self.metadata_freeze, [metadata_dict[key], another_dict[key]]))

    def metadata_freeze(self, object):
        """
        Transforms objects stored in a merged metadata dictionary into hashable representations.
        """

        if isinstance(object, set):
            return ('set', frozenset(map(self.metadata_freeze, object)))

        elif isinstance(object, dict):

            return ('dict', frozenset([
                (self.metadata_freeze(key), self.metadata_freeze(value))
                for key, value in dict.items()]))

        elif isinstance(object, list):
            return ('list', tuple(map(self.metadata_freeze, object)))

        else:
            return object

    def metadata_restore(self, object):
        """
        Restores metadata objects from hashable representations.
        """

        if not isinstance(object, tuple):
            return object

        elif object[0] == 'set':
            return sorted(map(self.metadata_restore, object[1]))

        elif object[0] == 'dict':

            return dict([(self.metadata_restore(key), self.metadata_restore(value))
                for key, value in object[1]])

        elif object[0] == 'list':
            return [self.metadata_restore(item) for item in object[1]]

        else:
            raise Exception('Unknown metadata object type \'{0}\'.'.format(type(object)))

    @staticmethod
    def mark_delete_merge(object, merge_tag, merge_id):
        """
        Marks lexical entry or entity as deleted and merged/replaced.
        """

        object.marked_for_deletion = True

        if not object.additional_metadata:
            object.additional_metadata = {merge_tag: merge_id}

        elif not isinstance(object.additional_metadata, dict):
            raise Exception('Unsupported additional metadata type \'{0}\'.'.format(
                type(object.additional_metadata)))

        # Checking for a situation of a repeated merge, which should be impossible.

        elif merge_tag in object.additional_metadata:

            already_client_id, already_object_id = object.additional_metadata[merge_tag]

            raise Exception(
                'Trying to merge lexical object {0}/{1}, which '
                'is already merged into lexical object {2}/{3}, into lexical object {3}/{4}.'.format(
                    object.client_id, object.object_id,
                    already_client_id, already_object_id, *merge_id))

        else:
            object.additional_metadata[merge_tag] = merge_id

        flag_modified(object, 'additional_metadata')

        # Updating object ToC.

        objecttoc = DBSession.query(ObjectTOC).filter_by(
            client_id = object.client_id, object_id = object.object_id).one()

        objecttoc.marked_for_deletion = True

    def check_group(self, index, entry_id_list):
        """
        Checks that all lexical entries belong to the same perspective, and that the user has necessary
        permissions to perform the merge.
        """

        entry_list = DBSession.query(LexicalEntry).filter(
            tuple_(LexicalEntry.client_id, LexicalEntry.object_id).in_(
                (entry['client_id'], entry['object_id']) for entry in entry_id_list)).all()

        perspective_id = None
        for entry in entry_list:

            if perspective_id is None:
                perspective_id = (entry.parent_client_id, entry.parent_object_id)

            elif perspective_id != (entry.parent_client_id, entry.parent_object_id):

                DBSession.rollback()
                raise Exception('Entries {0} (group {1}) are from different perspectives.'.format(
                    entry_id_list, index))

            if not self.check_permissions(*perspective_id):

                DBSession.rollback()
                raise Exception('No create/delete permissions for perspective {0}/{1}.'.format(
                    *perspective_id))

        return entry_list, perspective_id

    def merge_group(self, index, entry_id_list):
        """
        Merges a group of lexical entries.
        """

        entry_list, perspective_id = self.check_group(index, entry_id_list)

        log.debug('{0}: group {1}/{2}, {3} lexical entries, perspective {4}/{5}'.format(
            self.method_string,
            index + 1,
            len(self.group_list),
            len(entry_id_list),
            *perspective_id))

        # Getting lexical entry data.

        entry_data_list = [e.track(False, 2) for e in entry_list]
        remove_deleted(entry_data_list)

        log.debug('{0}: group {1}/{2}, lexical entries\' ids:\n{3}'.format(
            self.method_string,
            index + 1,
            len(self.group_list),
            pprint.pformat(entry_id_list)))

        log.debug('{0}: group {1}/{2}, lexical entries\' data:\n{3}'.format(
            self.method_string,
            index + 1,
            len(self.group_list),
            pprint.pformat(entry_data_list)))

        # Merging lexical entry data.

        entry_dict = {
            'additional_metadata': {},
            'contains': {},
            'merge_entry_dict': {},
            'merge_entity_set': set(),
            'published': False if self.publish_any else True}

        entry_min_created_at = None
        entry_original_client_id = None
        entry_merge_tree = []

        for entry, entry_data in zip(entry_list, entry_data_list):
            entry_dict['merge_entry_dict'][(entry.client_id, entry.object_id)] = entry

            # Processing each lexical entry to be merged.

            if len(set(entry_data.keys()).difference(set([
                'additional_metadata', 'client_id', 'contains', 'created_at', 'level',
                'marked_for_deletion', 'object_id', 'parent_client_id', 'parent_object_id',
                'published']))) > 0:

                DBSession.rollback()
                raise Exception('Unexpected lexical entry data keys.')

            entry_dict['published'] = (
                entry_dict['published'] or entry_data['published'] if self.publish_any else
                entry_dict['published'] and entry_data['published'])

            additional_metadata = entry_data.get('additional_metadata', {})

            if not isinstance(additional_metadata, dict):

                DBSession.rollback()
                raise Exception('Unsupported additional metadata type \'{0}\'.'.format(
                    type(additional_metadata)))

            # Getting merge metadata of the lexical entry.

            if 'merge_tag' in additional_metadata:

                min_created_at, original_client_id, merge_tree = build_merge_tree(entry)
                del additional_metadata['merge_tag']

            elif 'merge' in additional_metadata and 'original_author' in additional_metadata['merge']:

                min_created_at, original_client_id, merge_tree = build_merge_tree(entry)
                del additional_metadata['merge']

            elif 'merge' in additional_metadata:

                # Current (the 3rd) version of merge metadata.

                min_created_at = additional_metadata['merge']['min_created_at']
                original_client_id = additional_metadata['merge']['original_client_id']
                merge_tree = copy.deepcopy(additional_metadata['merge']['merge_tree'])

                del additional_metadata['merge']

            else:
                min_created_at = entry_data['created_at']
                original_client_id = entry_data['client_id']
                merge_tree = [entry_data['client_id'], entry_data['object_id']]

            if 'merged_to' in additional_metadata:
                del additional_metadata['merged_to']

            # Updating merge metadata, merging metadata and entities of the lexical entry.

            if (entry_min_created_at is None or
                min_created_at < entry_min_created_at):

                entry_min_created_at = min_created_at
                entry_original_client_id = original_client_id

            entry_merge_tree.append(merge_tree)

            log.debug('entry {0}/{1} merge_tree: {2}'.format(
                entry.client_id, entry.object_id, pprint.pformat(merge_tree)))

            log.debug('entry_merge_tree: {0}'.format(pprint.pformat(entry_merge_tree)))

            self.metadata_merge(entry_dict['additional_metadata'], additional_metadata)

            self.merge_contains(
                entry_dict['contains'], entry_dict['merge_entity_set'],
                entry_data['contains'], (entry_data['client_id'], entry_data['object_id']))

        # Finalizing merge metadata.

        if 'merge_tag' in entry_dict['additional_metadata']:
            del entry_dict['additional_metadata']['merge_tag']

        entry_dict['additional_metadata']['merge'] = {
            'min_created_at': entry_min_created_at,
            'original_client_id': entry_original_client_id,
            'merge_tree': entry_merge_tree}

        # Creating new lexical entry.

        log.debug('{0}: group {1}/{2}, merged lexical entries\' data:\n{3}'.format(
            self.method_string,
            index + 1,
            len(self.group_list),
            pprint.pformat(entry_dict)))

        entry_kwargs = {
            'client_id': self.client_id,
            'parent_client_id': perspective_id[0],
            'parent_object_id': perspective_id[1]}

        if len(entry_dict['additional_metadata']) > 0:

            metadata = self.metadata_restore(entry_dict['additional_metadata'])

            entry_dict['additional_metadata'] = metadata
            entry_kwargs['additional_metadata'] = metadata

        # NOTE: we do not process 'published' key in lexical entry metadata.

        merge_entry = LexicalEntry(**entry_kwargs)
        DBSession.add(merge_entry)

        self.result_list.append({
            'client_id': merge_entry.client_id,
            'object_id': merge_entry.object_id})

        log.debug(
            '{0}: group {1}/{2}, {3} lexical entr{4} '
            'merged into lexical entry {5}/{6}:\n{7}'.format(
            self.method_string,
            index + 1,
            len(self.group_list),
            len(entry_id_list),
            'y' if len(entry_id_list) == 1 else 'ies',
            merge_entry.client_id,
            merge_entry.object_id,
            pprint.pformat(dict(object_id = merge_entry.object_id, **entry_kwargs))))

        def merge_entities(entity_key, entity_data, entity_parent = None):
            """
            Recursively creates new entities from merged entities.
            """

            entity_kwargs = {
                'client_id': self.client_id,
                'field_client_id': entity_data['field_client_id'],
                'field_object_id': entity_data['field_object_id'],
                'locale_id': entity_data['locale_id'],
                'parent_client_id': merge_entry.client_id,
                'parent_object_id': merge_entry.object_id}

            # Optional attributes.

            if len(entity_data['additional_metadata']) > 0:

                metadata = self.metadata_restore(entity_data['additional_metadata'])

                entity_data['additional_metadata'] = metadata
                entity_kwargs['additional_metadata'] = metadata

            for name in ['content', 'link_client_id', 'link_object_id']:

                if name in entity_data:
                    entity_kwargs[name] = entity_data[name]

            if entity_parent is not None:
                entity_kwargs['self_client_id'] = entity_parent.client_id
                entity_kwargs['self_object_id'] = entity_parent.object_id

            # Creating new entity to replace merged entities.

            merge_entity = Entity(**entity_kwargs)

            if entity_data.get('accepted', False):
                merge_entity.publishingentity.accepted = True

            if entity_data.get('published', False):
                merge_entity.publishingentity.published = True

            DBSession.add(merge_entity)

            log.debug(
                '{0}: group {1}/{2}, {3} entit{4} of type \'{5}\' '
                'with content {6} merged into entity {7}/{8}:\n{9}'.format(
                self.method_string,
                index + 1,
                len(self.group_list),
                len(entity_data['merge_set']),
                'y' if len(entity_data['merge_set']) == 1 else 'ies',
                entity_key[0],
                repr(entity_key[1]),
                merge_entity.client_id,
                merge_entity.object_id,
                pprint.pformat(dict(object_id = merge_entity.object_id, **entity_kwargs))))

            # Updating merged entities.

            for c_id, o_id in sorted(entity_data['merge_set']):

                entity = DBSession.query(Entity).filter_by(
                    client_id = c_id, object_id = o_id).one()

                self.mark_delete_merge(entity, 'merged_to',
                    [merge_entity.client_id, merge_entity.object_id])

            # Creating subentities, if required.

            for key, data in sorted(entity_data['contains'].items()):
                merge_entities(key, data, merge_entity)

        # Recursively creating new entities from merged entities.

        for entity_key_data in sorted(entry_dict['contains'].items()):
            merge_entities(*entity_key_data)

        # A dictionary of all entities which were replaced due to directly or indirectly referencing one
        # of the merged lexical entries.

        replace_entity_dict = {}

        def self_reference_replace(entity, replace_entity):
            """
            Recursively looks up entities referencing already replaced entities and replaces them too.
            """

            self_entity_list = DBSession.query(Entity).filter_by(
                self_client_id = entity.client_id, self_object_id = entity.object_id,
                marked_for_deletion = False).all()

            log.debug(
                '{0}: group {1}/{2}, replaced entity {3}/{4}: '
                '{5} non-deleted self-link entit{6}:{7}{8}'.format(
                self.method_string,
                index + 1,
                len(self.group_list),
                entity.client_id,
                entity.object_id,
                len(self_entity_list),
                'y' if len(self_entity_list) == 1 else 'ies',
                '\n' if len(self_entity_list) > 1 else ' ',
                pprint.pformat([(e.client_id, e.object_id) for e in self_entity_list])))

            # Replacing found reference entities, and then recursively replacing any entities
            # referencing them.

            for self_entity in self_entity_list:

                entity_kwargs = {
                    'additional_metadata': {},
                    'client_id': self.client_id,
                    'field_client_id': self_entity.field_client_id,
                    'field_object_id': self_entity.field_object_id,
                    'locale_id': self_entity.locale_id,
                    'parent_client_id': self_entity.parent_client_id,
                    'parent_object_id': self_entity.parent_object_id,
                    'self_client_id': replace_entity.client_id,
                    'self_object_id': replace_entity.object_id}

                for name in ['additional_metadata', 'content',
                    'link_client_id', 'link_object_id', 'parent_client_id', 'parent_object_id']:

                    if getattr(self_entity, name) is not None:
                        entity_kwargs[name] = copy.deepcopy(getattr(self_entity, name))

                # Checking that reference entity does not additionally reference one of the merged
                # entries through link_client/object_id or parent_client/object_id (in that case link
                # replacement breaks, but it should be impossible).

                link_id = (self_entity.link_client_id, self_entity.link_object_id)
                parent_id = (self_entity.parent_client_id, self_entity.parent_object_id)

                if (link_id in entry_dict['merge_entry_dict'] or
                    parent_id in entry_dict['merge_entry_dict']):

                    raise Exception(
                        'Unexpected additional reference from entity {0}/{1} '
                        '(lexical entry group {2}), please contact developers.'.format(
                            self_entity.client_id, self_entity.object_id, entry_id_list))

                # Creating new entity to replace reference entity.

                additional_metadata = entity_kwargs['additional_metadata']

                additional_metadata['merge'] = {
                    'min_created_at': self_entity.created_at,
                    'original_client_id': self_entity.client_id}

                if 'merged_to' in additional_metadata:
                    del additional_metadata['merged_to']

                if 'merged_by' in additional_metadata:
                    del additional_metadata['merged_by']

                merge_entity = Entity(**entity_kwargs)
                DBSession.add(merge_entity)

                log.debug(
                    '{0}: group {1}/{2}, replaced entity {3}/{4}, self-link '
                    'entity {5}/{6} replaced by entity {7}/{8}:\n{9}'.format(
                    self.method_string,
                    index + 1,
                    len(self.group_list),
                    entity.client_id,
                    entity.object_id,
                    self_entity.client_id,
                    self_entity.object_id,
                    merge_entity.client_id,
                    merge_entity.object_id,
                    pprint.pformat(dict(object_id = merge_entity.object_id, **entity_kwargs))))

                # Marking replaced entity as deleted and replaced due to merge.

                replace_entity_dict[(self_entity.client_id, self_entity.object_id)] = \
                    (merge_entity.client_id, merge_entity.object_id)

                self.mark_delete_merge(self_entity, 'merged_by',
                    [merge_entity.client_id, merge_entity.object_id])

                # Recursively looking up entities which reference replaced entity and replacing them
                # too, if required.

                self_reference_replace(self_entity)

        # Marking merged lexical entries as deleted and merged.

        for (c_id, o_id), entry in sorted(entry_dict['merge_entry_dict'].items()):

            self.mark_delete_merge(entry, 'merged_to',
                [merge_entry.client_id, merge_entry.object_id])

            # Looking up any non-deleted entities representing links to the merged lexical entry, just
            # in case filtering out any entities that will be merged.

            link_entity_list = DBSession.query(Entity).filter_by(
                link_client_id = entry.client_id, link_object_id = entry.object_id,
                marked_for_deletion = False).all()

            log.debug(
                '{0}: group {1}/{2}, merged lexical entry {3}/{4}: '
                '{5} non-deleted incoming link entit{6}:{7}{8}'.format(
                self.method_string,
                index + 1,
                len(self.group_list),
                entry.client_id,
                entry.object_id,
                len(link_entity_list),
                'y' if len(link_entity_list) == 1 else 'ies',
                '\n' if len(link_entity_list) > 1 else ' ',
                pprint.pformat([(e.client_id, e.object_id) for e in link_entity_list])))

            # Replacing such links, and then recursively replacing any entities referencing them.

            for link_entity in link_entity_list:

                entity_kwargs = {
                    'additional_metadata': {},
                    'client_id': self.client_id,
                    'field_client_id': link_entity.field_client_id,
                    'field_object_id': link_entity.field_object_id,
                    'link_client_id': merge_entry.client_id,
                    'link_object_id': merge_entry.object_id,
                    'locale_id': link_entity.locale_id,
                    'parent_client_id': link_entity.parent_client_id,
                    'parent_object_id': link_entity.parent_object_id}

                for name in ['additional_metadata', 'content',
                    'parent_client_id', 'parent_object_id', 'self_client_id', 'self_object_id']:

                    if getattr(link_entity, name) is not None:
                        entity_kwargs[name] = copy.deepcopy(getattr(link_entity, name))

                # Checking that link entity does not additionally reference one of the merge entities
                # through self_client/object_id or one of the merge entries through parent_client/
                # object_id (in that case link replacement breaks, but it should be impossible).

                self_id = (link_entity.self_client_id, link_entity.self_object_id)
                parent_id = (link_entity.parent_client_id, link_entity.parent_object_id)

                if (self_id in entry_dict['merge_entity_set'] or
                    parent_id in entry_dict['merge_entry_dict']):

                    DBSession.rollback()
                    raise Exception(
                        'Unexpected additional reference from entity {0}/{1} (lexical '
                        'entry group {2}), please contact developers.'.format(
                            link_entity.client_id, link_entity.object_id, entry_id_list))

                # Creating new entity to replace link entity.

                additional_metadata = entity_kwargs['additional_metadata']

                additional_metadata['merge'] = {
                    'min_created_at': link_entity.created_at,
                    'original_client_id': link_entity.client_id}

                if 'merged_to' in additional_metadata:
                    del additional_metadata['merged_to']

                if 'merged_by' in additional_metadata:
                    del additional_metadata['merged_by']

                merge_entity = Entity(**entity_kwargs)
                DBSession.add(merge_entity)

                log.debug(
                    '{0}: group {1}/{2}, merged lexical entry {3}/{4}, incoming '
                    'link entity {5}/{6} replaced by entity {7}/{8}:\n{9}'.format(
                    self.method_string,
                    index + 1,
                    len(self.group_list),
                    entry.client_id,
                    entry.object_id,
                    link_entity.client_id,
                    link_entity.object_id,
                    merge_entity.client_id,
                    merge_entity.object_id,
                    pprint.pformat(dict(object_id = merge_entity.object_id, **entity_kwargs))))

                # Marking replaced entity as deleted and replaced due to merge.

                replace_entity_dict[(link_entity.client_id, link_entity.object_id)] = \
                    (merge_entity.client_id, merge_entity.object_id)

                self.mark_delete_merge(link_entity, 'merged_by',
                    [merge_entity.client_id, merge_entity.object_id])

                # Recursively looking up entities which reference replaced entity and replacing them
                # too, if required.

                self_reference_replace(link_entity, merge_entity)


def merge_bulk(request, publish_any, group_list):
    """
    Merges multiple groups of lexical entries, provided that each group is a subset of a single perspective,
    returns client/object ids of new lexical entries, a new entry for each merged group.
    """

    log.debug('merge_bulk')

    # Getting client and user data.

    client_id = request.authenticated_userid

    if not client_id:
        raise ResponseError(message='Unrecognized client.')

    user = Client.get_user_by_client_id(client_id)

    if not user:
        raise ResponseError(message='User authentification failure.')

    # Processing lexical entries group by group.

    try:
        merge_context = Merge_Context(
            'merge_bulk', request, client_id, user,
            publish_any,
            group_list)

        for index, entry_id_list in enumerate(merge_context.group_list):
            merge_context.merge_group(index, entry_id_list)

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]
        DBSession.rollback()
        raise ResponseError(message='\n' + traceback_string)

    # Returning identifiers of new lexical entries.

    return merge_context.result_list


@celery.task
def merge_bulk_task(task_key, cache_kwargs, sqlalchemy_url, merge_context):
    """
    Performs asynchronous merge.
    """

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind = engine)

    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)

    with manager:
        try:

            task_status.set(1, 0,
                'Merging lexical entries and entities')

            # Merging entry groups one by one.

            for index, entry_id_list in enumerate(merge_context.group_list):
                merge_context.merge_group(index, entry_id_list)

                task_status.set(1,
                    int(math.floor((index + 1) * 100 / len(merge_context.group_list))),
                    'Merging lexical entries and entities')

            task_status.set(1, 100, 'Finished merge')

        # If something is not right, we report it.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('merge_bulk_async: exception')
            log.debug('\n' + traceback_string)

            print(traceback_string)

            if task_status is not None:
                task_status.set(1, 100, 'Finished (ERROR), external error')

            raise ResponseError(message='\n' + traceback_string)


def merge_bulk_async(request, publish_any, group_list):
    """
    Launches asynchronous background merge task, see 'merge_bulk' procedure.
    """

    log.debug('merge_bulk_async')

    # Getting client and user data.

    client_id = request.authenticated_userid

    if not client_id:
        return {'error': message('Unrecognized client.')}

    user = Client.get_user_by_client_id(client_id)

    if not user:
        return {'error': message('User authentification failure.')}

    # Getting lexical entry group data.

    task_status = None

    try:
        merge_context = Merge_Context(
            'merge_bulk_async', request, client_id, user,
            publish_any,
            group_list)

        # Pre-checking that each entry group belongs to the same perspective, and that the user has
        # necessary permissions to perform the merge, and dropping request info.

        for index, entry_id_list in enumerate(merge_context.group_list):
            merge_context.check_group(index, entry_id_list)

        merge_context.request = None

        # Launching asynchronous merge task.

        task_status = TaskStatus(user.id, 'Merge',
            '{0} groups, {1} entries'.format(len(merge_context.group_list), merge_context.entry_count), 1)

        task_status.set(1, 0, 'Starting merge')

        task_key = task_status.key
        cache_kwargs = request.registry.settings["cache_kwargs"]
        sqlalchemy_url = request.registry.settings["sqlalchemy.url"]

        merge_bulk_task.delay(task_key, cache_kwargs, sqlalchemy_url, merge_context)

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('merge_bulk_async: exception')
        log.debug('\n' + traceback_string)

        if task_status is not None:
            task_status.set(1, 100, 'Finished (ERROR), external error')
        raise ResponseError(message='\n' + traceback_string)

    return task_status.key if task_status is not None else ''


