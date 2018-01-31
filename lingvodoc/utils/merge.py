
# Standard library imports.

import ast
import collections
import datetime
import io
import logging
import pdb
import pprint
import traceback
import itertools

# External imports.

import pylev
from pyramid.response import Response
from pyramid.request import Request
from pyramid.view import view_config

from sqlalchemy import and_, BigInteger, cast, extract, func, tuple_
from sqlalchemy.orm import aliased

# Lingvodoc imports.

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
    DictionaryPerspective
)

from lingvodoc.views.v2.utils import message, unimplemented
from lingvodoc.utils.creation import add_user_to_group
from lingvodoc.schema.gql_holders import ResponseError

from lingvodoc.views.v2.utils import (
    message,
    remove_deleted,
    unimplemented
)



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
            ({'id': list(id_a)},
             {'id': list(id_b)},
             confidence)
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
        field_id = (field_selection['client_id'], field_selection['object_id'])

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