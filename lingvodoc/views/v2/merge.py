
__author__ = 'alexander'

# Standard library imports.

import collections
import copy
import hashlib
import itertools
import json
import logging
import math
import pprint
import traceback

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPOk
)

# External imports.

import pylev

from pyramid.request import Request
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy import and_, create_engine, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

import transaction
from transaction import manager

# Lingvodoc imports.

from lingvodoc.cache.caching import initialize_cache, TaskStatus
from lingvodoc.exceptions import CommonException

import lingvodoc.merge_perspectives as merge_perspectives
from lingvodoc.merge_perspectives import mergeDicts

from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    Entity,
    Group,
    LexicalEntry,
    ObjectTOC,
    organization_to_group_association,
    User,
    user_to_group_association,
    user_to_organization_association
)

from lingvodoc.queue.celery import celery
from lingvodoc.schema.gql_holders import del_object
from lingvodoc.utils.static_fields import fields_static

from lingvodoc.views.v2.utils import (
    as_storage_file,
    message,
    remove_deleted,
    storage_file,
    unimplemented
)

from lingvodoc.cache.caching import CACHE

log = logging.getLogger(__name__)


@view_config(route_name='merge_dictionaries', renderer='json', request_method='POST')
def merge_dictionaries(request):  # TODO: test
    try:
        req = request.json_body
        variables = {'auth': request.authenticated_userid}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        client_id = req.get('client_id')
        object_id = req.get('object_id')
        parent_object_id = req['language_object_id']
        parent_client_id = req['language_client_id']
        translation_string = req['translation_string']
        translation = translation_string
        if 'translation' in req:
            translation = req['translation']

        dictionaries = req['dictionaries']
        if len(dictionaries) != 2:
            raise KeyError("Wrong number of dictionaries to merge.",
                           len(dictionaries))
        new_dicts = []
        for dicti in dictionaries:
            diction = DBSession.query(Dictionary).filter_by(client_id=dicti['client_id'], object_id=dicti['object_id']).first()
            if not diction:
                raise KeyError("Dictionary do not exist in the system")
            if parent_client_id != diction.parent_client_id or parent_object_id != diction.parent_object_id:
                raise KeyError("Both dictionaries should have same language.")
            new_dicts += [diction]
        dictionaries = new_dicts
        base = DBSession.query(BaseGroup).filter_by(subject='merge', action='create').first()
        override = DBSession.query(Group).filter_by(base_group_id=base.id, subject_override = True).first()
        if not user.is_active:
            raise KeyError("Not enough permission to do that")
        if user not in override.users:
            grps = []
            for dict in dictionaries:
                gr = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                      subject_client_id=dict.client_id,
                                                      subject_object_id=dict.object_id).first()
                grps += [gr]
            if client_id and object_id:
                gr = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                      subject_client_id=client_id,
                                                      subject_object_id=object_id).first()
                grps += [gr]
            for gr in grps:
                if user not in gr.users:
                    raise KeyError("Not enough permission to do that")
        if not client_id or not object_id:
            subreq = Request.blank('/dictionary')
            subreq.method = 'POST'
            subreq.json = {'parent_object_id': parent_object_id, 'parent_client_id': parent_client_id,
                                'translation_string': translation_string, 'translation': translation}
            headers = {'Cookie':request.headers['Cookie']}
            subreq.headers = headers
            response = request.invoke_subrequest(subreq)
            client_id = response.json['client_id']
            object_id = response.json['object_id']
        new_dict = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
        perspectives = []
        for dicti in dictionaries:
            for entry in dicti.dictionaryperspective:
                perspectives += [entry]
            for entry in perspectives:
                if entry in dicti.dictionaryperspective:
                    dicti.dictionaryperspective.remove(entry)
                new_dict.dictionaryperspective.append(entry)
            cli_id = dicti.client_id
            obj_id = dicti.object_id
            if (cli_id == client_id) and (obj_id == object_id):
                continue
            bases = DBSession.query(BaseGroup).filter_by(dictionary_default=True)
            groups = []
            for base in bases:

                group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                         subject_object_id=obj_id,
                                                         subject_client_id=cli_id).first()
                groups += [group]

            for group in groups:
                base = group.parent
                existing = DBSession.query(Group).filter_by(parent = base,
                                                         subject_object_id=object_id,
                                                         subject_client_id=client_id).first()
                if existing:
                    users = []
                    for user in group.users:
                        users += [user]
                    for user in users:
                        if user in group.users:
                            group.users.remove(user)
                        if not user in existing.users:
                            existing.users.append(user)
                else:
                    new_group = Group(base_group_id=group.base_group_id,
                                      subject_object_id=client_id,
                                      subject_client_id=object_id)
                    DBSession.add(new_group)
                    users = []
                    for user in group.users:
                        users += [user]
                    for user in users:
                        if user in group.users:
                            group.users.remove(user)
                        if not user in new_group.users:
                            new_group.users.append(user)
                group.marked_for_deletion = True
            dicti.marked_for_deletion = True
        request.response.status = HTTPOk.code
        return {'object_id': object_id,
                'client_id': client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='merge_perspectives', renderer='json', request_method='POST')
def merge_perspectives_api(request):  # TODO: test
    try:
        req = request.json_body
        variables = {'auth': request.authenticated_userid}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        client_id = req.get('client_id')
        object_id = req.get('object_id')
        dictionary_client_id = req['dictionary_client_id']
        dictionary_object_id = req['dictionary_object_id']
        translation_string = req['translation_string']
        translation = translation_string
        if 'translation' in req:
            translation = req['translation']

        persps = req['perspectives']
        if len(persps) != 2:
            raise KeyError("Wrong number of perspectives to merge.",
                           len(persps))
        for persp in persps:
            perspe = DBSession.query(DictionaryPerspective).filter_by(client_id=persp['client_id'],
                                                                       object_id=persp['object_id']).first()
            if not perspe:
                raise KeyError("Perspective do not exist in the system")
            if dictionary_client_id != perspe.parent_client_id or dictionary_object_id != perspe.parent_object_id:
                raise KeyError("Both perspective should from same dictionary.")
        base = DBSession.query(BaseGroup).filter_by(subject='merge', action='create').first()
        override = DBSession.query(Group).filter_by(base_group_id=base.id, subject_override = True).first()
        if not user.is_active:
            raise KeyError("Not enough permission to do that")
        if user not in override.users:
            group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                  subject_client_id=dictionary_client_id,
                                                  subject_object_id=dictionary_object_id).first()
            if user not in group.users:
                raise KeyError("Not enough permission to do that")
            if client_id and object_id:
                gr = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                      subject_client_id=client_id,
                                                      subject_object_id=object_id).first()
                if user not in gr.users:
                    raise KeyError("Not enough permission to do that")

        if not client_id and not object_id:
            subreq = Request.blank('/dictionary/%s/%s/perspective' % (dictionary_client_id, dictionary_object_id))
            subreq.method = 'POST'
            subreq.json = {'translation_string': translation_string, 'translation': translation}
            headers = {'Cookie':request.headers['Cookie']}
            subreq.headers = headers
            response = request.invoke_subrequest(subreq)
            client_id = response.json['client_id']
            object_id = response.json['object_id']
        new_persp = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        fields = []
        for persp in persps:
            for entry in persp['fields']:
                field = dict(entry)
                new_type = field.pop('new_type_name', None)
                if new_type:
                    field['entity_type'] = new_type
                    field['entity_type_translation'] = new_type
                if not field in fields:
                    entity_type_translation = field['entity_type_translation']
                    add_need = True
                    for fi in fields:
                        if fi['entity_type_translation'] == entity_type_translation:
                            add_need = False
                            break
                    if add_need:
                        fields.append(field)
        subreq = Request.blank('/dictionary/%s/%s/perspective/%s/%s/fields' %
                               (dictionary_client_id,
                                dictionary_object_id,
                                client_id,
                                object_id))
        subreq.method = 'POST'
        subreq.json = {'fields': fields}
        headers = {'Cookie':request.headers['Cookie']}
        subreq.headers = headers
        response = request.invoke_subrequest(subreq)
        for persp in persps:

            obj_id = persp['object_id']
            cli_id = persp['client_id']
            if (cli_id == client_id) and (obj_id == object_id):
                continue
            parent = DBSession.query(DictionaryPerspective).filter_by(client_id=cli_id, object_id=obj_id).first()
            lexes = DBSession.query(LexicalEntry).filter_by(parent_client_id=cli_id, parent_object_id=obj_id).all()

            for lex in lexes:
                metadata = dict()
                if lex.additional_metadata:
                    metadata = lex.additional_metadata
                metadata['came_from'] = {'client_id': lex.parent_client_id, 'object_id': lex.parent_object_id}
                lex.additional_metadata = metadata
                lex.parent = new_persp
                DBSession.flush()
                for ent in lex.leveloneentity:
                    for field in persp['fields']:
                        if ent.entity_type == field['entity_type']:
                            if 'new_type_name' in field:
                                ent.entity_type = field['new_type_name']
            bases = DBSession.query(BaseGroup).filter_by(perspective_default=True)
            groups = []
            for base in bases:

                group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                         subject_object_id=obj_id,
                                                         subject_client_id=cli_id).first()
                if group:
                    groups += [group]

            for group in groups:
                base = group.parent
                existing = DBSession.query(Group).filter_by(parent = base,
                                                         subject_object_id=object_id,
                                                         subject_client_id=client_id).first()
                if existing:
                    users = []
                    for user in group.users:
                        users += [user]
                    for user in users:
                        if user in group.users:
                            group.users.remove(user)
                        if not user in existing.users:
                            existing.users.append(user)
                else:
                    new_group = Group(base_group_id=group.base_group_id,
                                      subject_object_id=client_id,
                                      subject_client_id=object_id)
                    DBSession.add(new_group)
                    users = []
                    for user in group.users:
                        users += [user]
                    for user in users:
                        if user in group.users:
                            group.users.remove(user)
                        if not user in new_group.users:
                            new_group.users.append(user)
                group.marked_for_deletion = True
            parent.marked_for_deletion = True
        new_persp.marked_for_deletion = False  # TODO: check where it is deleted
        request.response.status = HTTPOk.code
        return {'object_id': object_id,
                'client_id': client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='merge_suggestions_old', renderer='json', request_method='POST')
def merge_suggestions_old(request):
    subreq = Request.blank('/dictionary/' + request.matchdict.get('dictionary_client_id_1') + '/' +
    request.matchdict.get('dictionary_object_id_1') + '/perspective/' +
    request.matchdict.get('perspective_client_id_1') + '/' +
    request.matchdict.get('perspective_object_id_1') + '/all')
    subreq.method = 'GET'
    response_1 = request.invoke_subrequest(subreq).json
    subreq = Request.blank('/dictionary/' + request.matchdict.get('dictionary_client_id_2') + '/' +
    request.matchdict.get('dictionary_object_id_2') + '/perspective/' +
    request.matchdict.get('perspective_client_id_2') + '/' +
    request.matchdict.get('perspective_object_id_2') + '/all')
    subreq.method = 'GET'
    response_2 = request.invoke_subrequest(subreq).json
    #entity_type_primary = 'Word'
    #entity_type_secondary = 'Transcription'
    #threshold = 0.2
    #levenstein = 2
    entity_type_primary = request.matchdict.get('entity_type_primary')
    entity_type_secondary = request.matchdict.get('entity_type_secondary')
    threshold = request.matchdict.get('threshold')
    levenstein = request.matchdict.get('levenstein')
    def parse_response(elem):
        words = filter(lambda x: x['entity_type'] == entity_type_primary and not x['marked_for_deletion'], elem['contains'])
        words = map(lambda x: x['content'], words)
        trans = filter(lambda x: x['entity_type'] == entity_type_secondary and not x['marked_for_deletion'], elem['contains'])
        trans = map(lambda x: x['content'], trans)
        tuples_res = [(i_word, i_trans, (elem['client_id'], elem['object_id'])) for i_word in words for i_trans in trans]
        return tuples_res
    tuples_1 = [parse_response(i) for i in response_1['lexical_entries']]
    tuples_1 = [item for sublist in tuples_1 for item in sublist]
    tuples_2 = [parse_response(i) for i in response_2['lexical_entries']]
    tuples_2 = [item for sublist in tuples_2 for item in sublist]
    def get_dict(elem):
        return {'suggestion': [
            {'lexical_entry_client_id': elem[0][0], 'lexical_entry_object_id': elem[0][1]},
            {'lexical_entry_client_id': elem[1][0], 'lexical_entry_object_id': elem[1][1]}
        ], 'confidence': elem[2]}
    results = [get_dict(i) for i in mergeDicts(tuples_1, tuples_2, float(threshold), int(levenstein))]
    return json.dumps(results)


def check_user_merge_permissions_direct(user_id, perspective_client_id, perspective_object_id):
    """
    Checks if the user has permissions required to merge lexical entries and entities, i.e. permissions to
    create and delete them, by direct DB query.

    NOTE: replaced by check_user_merge_permissions.
    """

    user = DBSession.query(User).filter_by(id = user_id).first()

    if not user.is_active:
        return False

    create_base_group = DBSession.query(BaseGroup).filter_by(
        subject = 'lexical_entries_and_entities', action = 'create').first()

    delete_base_group = DBSession.query(BaseGroup).filter_by(
        subject = 'lexical_entries_and_entities', action = 'delete').first()

    # Checking if user can create lexical entries and entities.

    user_create = DBSession.query(user_to_group_association, Group).filter(and_(
        user_to_group_association.c.user_id == user_id,
        user_to_group_association.c.group_id == Group.id,
        Group.base_group_id == create_base_group.id,
        Group.subject_client_id == perspective_client_id,
        Group.subject_object_id == perspective_object_id)).limit(1).count() > 0

    organization_create = DBSession.query(
        user_to_organization_association, organization_to_group_association, Group).filter(and_(
            user_to_organization_association.c.user_id == user_id,
            organization_to_group_association.c.organization_id ==
                user_to_organization_association.c.organization_id,
            organization_to_group_association.c.group_id == Group.id,
            Group.base_group_id == create_base_group.id,
            Group.subject_client_id == perspective_client_id,
            Group.subject_object_id == perspective_object_id)).limit(1).count() > 0

    # Checking if user can delete lexical entries and entities.

    user_delete = DBSession.query(user_to_group_association, Group).filter(and_(
        user_to_group_association.c.user_id == user_id,
        user_to_group_association.c.group_id == Group.id,
        Group.base_group_id == delete_base_group.id,
        Group.subject_client_id == perspective_client_id,
        Group.subject_object_id == perspective_object_id)).limit(1).count() > 0

    organization_delete = DBSession.query(
        user_to_organization_association, organization_to_group_association, Group).filter(and_(
            user_to_organization_association.c.user_id == user_id,
            organization_to_group_association.c.organization_id ==
                user_to_organization_association.c.organization_id,
            organization_to_group_association.c.group_id == Group.id,
            Group.base_group_id == delete_base_group.id,
            Group.subject_client_id == perspective_client_id,
            Group.subject_object_id == perspective_object_id)).limit(1).count() > 0

    # Returning final result.

    return (user_create or organization_create and user_delete or organization_delete)


def check_user_merge_permissions(
    request, user,
    dictionary_client_id, dictionary_object_id,
    perspective_client_id, perspective_object_id):
    """
    Checks if the user has permissions required to merge lexical entries and entities, i.e. permissions to
    create and delete them, via perspective user role subrequest.
    """

    if user.id == 1:
        return True

    if not user.is_active:
        return False

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


@view_config(
    route_name = 'merge_permissions',
    renderer = 'json',
    request_method = 'POST',
    permission = 'view')
def merge_permissions(request):
    """
    Checks if the user has create/delete permissions required to merge lexical entries and entities.
    """

    perspective_client_id = request.matchdict.get('perspective_client_id')
    perspective_object_id = request.matchdict.get('perspective_object_id')

    # Trying to check user's merge permissions.

    try:
        user = Client.get_user_by_client_id(request.authenticated_userid)

        perspective = DBSession.query(DictionaryPerspective).filter_by(
            client_id = perspective_client_id, object_id = perspective_object_id).first()

        user_has_permissions = check_user_merge_permissions(
            request, user,
            perspective.parent_client_id, perspective.parent_object_id,
            perspective_client_id, perspective_object_id)

        log.debug('merge_permissions {0}/{1}: {2}'.format(
            perspective_client_id, perspective_object_id, user_has_permissions))

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('merge_permissions: exception')
        log.debug('\n' + traceback_string)

        return {'error': message('\n' + traceback_string)}

    return {'user_has_permissions': user_has_permissions}


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

    # Checking if we need to adjust entity filtering.

    if entity_type_primary in fields_static:

        primary_client_id, primary_object_id = fields_static[entity_type_primary]

        primary_filter = (lambda entity_data:
            entity_data['field_client_id'] == primary_client_id and
            entity_data['field_object_id'] == primary_object_id and
            not entity_data['marked_for_deletion'])

    else:

        primary_filter = (lambda entity_data:
            entity_data['entity_type'] == entity_type_primary and
            not entity_data['marked_for_deletion'])

    if entity_type_secondary in fields_static:

        secondary_client_id, secondary_object_id = fields_static[entity_type_secondary]

        secondary_filter = (lambda entity_data:
            entity_data['field_client_id'] == secondary_client_id and
            entity_data['field_object_id'] == secondary_object_id and
            not entity_data['marked_for_deletion'])

    else:

        secondary_filter = (lambda entity_data:
            entity_data['entity_type'] == entity_type_secondary and
            not entity_data['marked_for_deletion'])

    def parse_response(entry_data):
        """
        Contructs description of a lexical entry to be used for matching.
        """

        word_list = map(
            lambda x: x.get('content', ''),
            filter(primary_filter, entry_data['contains']))

        translation_list = map(
            lambda x: x.get('content', ''),
            filter(secondary_filter, entry_data['contains']))

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

    Each lexical entry L is transformed into a feature vector V(L) given fields F1, ..., Fn:

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


def match_graph(match_result_list):
    """
    Compiles lexical entry match graph based on results of lexical entry matching.
    """

    confidence_dict = collections.defaultdict(lambda: 0.0)
    weight_dict = collections.defaultdict(lambda: 0.0)
    adjacency_dict = collections.defaultdict(set)

    def canonical_id_id_key(id_a, id_b):
        return (id_a, id_b) if id_a <= id_b else (id_b, id_a)

    for id_a, id_b, confidence in match_result_list:

        # Building adjacency lists, total lexical entry confidence map and link confidence map.

        adjacency_dict[id_a].add(id_b)
        adjacency_dict[id_b].add(id_a)

        weight_dict[id_a] += confidence / 2
        weight_dict[id_b] += confidence / 2

        confidence_dict[canonical_id_id_key(id_a, id_b)] += confidence

    entry_id_list = sorted(adjacency_dict.keys())

    log.debug(
        'merge_suggestions {0}/{1}: {2} matching entries\n'.format(
            perspective_client_id, perspective_object_id, len(entry_id_list)) +
        pprint.pformat(entry_id_list))

    # Grouping matching lexical entries via depth-first search.

    group_list = []
    group_dict = {}

    def df_search(lexical_entry_id, group_index):

        if lexical_entry_id in group_dict:
            return

        group_list[-1].add(lexical_entry_id)
        group_dict[lexical_entry_id] = group_index

        for id in adjacency_dict[lexical_entry_id]:
            df_search(id, group_index)

    for lexical_entry_id in entry_id_list:
        if lexical_entry_id not in group_dict:

            group_list.append(set())
            df_search(lexical_entry_id, len(group_list) - 1)

    # Reporting lexical entry groups.

    log.debug('merge_suggestions {0}/{1}: {2} match groups'.format(
        perspective_client_id, perspective_object_id, len(group_list)))

    for group_index, group_set in enumerate(group_list):

        group_entry_list = list(sorted(
            (entry_id, len(adjacency_dict[entry_id]), weight_dict[entry_id])
                for entry_id in sorted(group_set)))

        log.debug(
            'group {0}, {1} lexical entries:\n'.format(group_index, len(group_set)) +
            pprint.pformat(group_entry_list))


def merge_suggestions_compute(
    request,
    perspective_client_id, perspective_object_id,
    algorithm,
    entity_type_primary, entity_type_secondary,
    threshold, levenshtein,
    field_selection_list, locale_id):
    """
    Computes merge suggestions.
    """

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

        return [], [], user_has_permissions

    # Aggregated entity tracking without checking lexical entries' perspective.

    composite_list = [

        (entry.created_at,
            entry.client_id,
            entry.object_id,
            entry.parent_client_id,
            entry.parent_object_id,
            entry.marked_for_deletion,
            entry.additional_metadata,
            entry.additional_metadata.get('came_from') if entry.additional_metadata else None)

        for entry in lexical_entry_list]

    entry_data_list = (

        LexicalEntry.track_multiple(
            composite_list,
            locale_id,
            False,
            check_perspective = False))

    remove_deleted(entry_data_list)

    log.debug('merge_suggestions {0}/{1}: {2} lexical entries'.format(
        perspective_client_id, perspective_object_id, len(entry_data_list)))

    # Matching lexical entries.

    if algorithm == 'simple':

        match_result_list = match_simple(entry_data_list,
            entity_type_primary, entity_type_secondary, threshold, levenshtein)

    else:

        match_result_list = match_fields(entry_data_list,
            field_selection_list, threshold)

    log.debug('merge_suggestions {0}/{1}: {2} matches'.format(
        perspective_client_id, perspective_object_id, len(match_result_list)))

    return entry_data_list, match_result_list, user_has_permissions


@view_config(
    route_name = 'merge_suggestions',
    renderer = 'json',
    request_method = 'POST',
    permission = 'view')
def merge_suggestions(request):
    """
    Finds groups of mergeable lexical entries according to specified criteria.
    """

    perspective_client_id = request.matchdict.get('perspective_client_id')
    perspective_object_id = request.matchdict.get('perspective_object_id')

    request_json = request.json

    algorithm = request_json.get('algorithm')
    threshold = request_json.get('threshold') or 0.1

    if algorithm not in set(['simple', 'fields']):
        return {'error': message('Unknown entity matching algorithm \'{0}\'.'.format(algorithm))}

    # Getting merge suggestions options.

    entity_type_primary = 'Transcription'
    entity_type_secondary = 'Translation'

    levenshtein = 1

    field_selection_list = None

    if algorithm == 'simple':

        entity_type_primary = request_json.get('entity_type_primary', entity_type_primary)
        entity_type_secondary = request_json.get('entity_type_secondary', entity_type_secondary)

        levenshtein = request_json.get('levenshtein', levenshtein)

    else:
        field_selection_list = request_json['field_selection_list']

    locale_id = int(request.cookies.get('locale_id') or 2)

    # Computing merge suggestions.

    entry_data_list, match_result_list, user_has_permissions = merge_suggestions_compute(
        request,
        perspective_client_id, perspective_object_id,
        algorithm,
        entity_type_primary, entity_type_secondary,
        threshold, levenshtein,
        field_selection_list, locale_id)

    if not match_result_list:

        return {
            'entry_data': [],
            'match_result': [],
            'user_has_permissions': user_has_permissions}

    # Returning match data together with data of matching lexical entries.

    match_id_set = set(id
        for id_a, id_b, confidence in match_result_list
            for id in (id_a, id_b))

    return {

        'entry_data': [
            entry_data for entry_data in entry_data_list
                if (entry_data['client_id'], entry_data['object_id']) in match_id_set],

        'match_result': [
            ({'client_id': id_a[0], 'object_id': id_a[1]},
                {'client_id': id_b[0], 'object_id': id_b[1]},
                confidence)
                for id_a, id_b, confidence in match_result_list],

        'user_has_permissions': user_has_permissions}


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

    def __init__(self,
        method_string,
        request,
        client_id,
        user,
        publish_any = None,
        group_list = None):
        """
        Initialization of the merge data.
        """

        self.method_string = method_string
        self.request = request

        self.client_id = client_id
        self.user = user

        if group_list is not None:

            self.group_list = group_list
            self.entry_count = sum(len(entry_id_list) for entry_id_list in group_list)

            log.debug('{0}: {1} lexical entry group{2}, {3} entries:\n{4}'.format(
                method_string,
                len(group_list),
                '' if len(group_list) == 1 else 's',
                self.entry_count,
                pprint.pformat(group_list)))

        self.publish_any = publish_any

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

    def mark_delete_merge(
        self,
        object,
        merge_tag,
        merge_id):
        """
        Marks lexical entry or entity as deleted and merged/replaced.
        """

        if not object.additional_metadata:

            object.additional_metadata = {merge_tag: merge_id}

        elif not isinstance(object.additional_metadata, dict):

            raise Exception(
                'Unsupported additional metadata type \'{}\'.'.format(
                    type(object.additional_metadata)))

        # Checking for a situation of a repeated merge, which should be impossible.

        elif merge_tag in object.additional_metadata:

            already_client_id, already_object_id = object.additional_metadata[merge_tag]

            raise Exception(
                'Trying to merge lexical object {}/{}, which '
                'is already merged into lexical object {}/{}, into lexical object {}/{}.'.format(
                    object.client_id, object.object_id,
                    already_client_id, already_object_id,
                    *merge_id))

        else:

            object.additional_metadata[merge_tag] = merge_id

        flag_modified(object, 'additional_metadata')

        # Object deletion.

        del_object(
            object, 'merge', self.client_id)

    def check_group(self, index, entry_id_list):
        """
        Checks that all lexical entries exist, belong to the same perspective, are not deleted and are not
        already merged, and that the user has necessary permissions to perform the merge.
        """

        entry_id_set = set(
            (entry_id['client_id'], entry_id['object_id'])
            for entry_id in entry_id_list)

        entry_list = (DBSession

            .query(LexicalEntry)

            .filter(
                tuple_(LexicalEntry.client_id, LexicalEntry.object_id)
                    .in_(entry_id_set))

            .all())

        # Checking that all specified lexical entries exist.

        if len(entry_list) < len(entry_id_set):

            nonexistent_id_set = set(entry_id_set)

            for entry in entry_list:

                nonexistent_id_set.remove(
                    (entry.client_id, entry.object_id))

            raise Exception(
                'Group {} {} has following nonexistent entries: {}'.format(
                    index, entry_id_set, nonexistent_id_set))

        # Checking that they are from the same perspective, are not deleted and are not already merged.

        perspective_id = None

        for entry in entry_list:

            entry_parent_id = (
                entry.parent_client_id, entry.parent_object_id)

            # Perspective check.

            if perspective_id is None:

                perspective_id = entry_parent_id

            elif perspective_id != entry_parent_id:

                raise Exception(
                    'Entries {} (group {}) are from different perspectives: {}, {}'.format(
                        entry_id_set,
                        index,
                        perspective_id,
                        entry_parent_id))

            # Deleted/merged check.

            if entry.marked_for_deletion:

                raise Exception(
                    'Entry {}/{} (group {}) is deleted.'.format(
                        entry.client_id,
                        entry.object_id,
                        index))

            if (entry.additional_metadata and
                'merged_to' in entry.additional_metadata):

                raise Exception(
                    'Entry {}/{} (group {}) is already merged.'.format(
                        entry.client_id,
                        entry.object_id,
                        index))

        # Checking that the user has the necessary permissions.

        if not self.check_permissions(*perspective_id):

            raise Exception(
                'No create/delete permissions for perspective {}/{}.'.format(
                    *perspective_id))

        return entry_list, perspective_id

    def merge_entry_data(self, entry_list, entry_data_list):
        """
        Merges lexical entry data.
        """

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

                raise Exception('Unexpected lexical entry data keys.')

            entry_dict['published'] = (
                entry_dict['published'] or entry_data['published'] if self.publish_any else
                entry_dict['published'] and entry_data['published'])

            additional_metadata = entry_data.get('additional_metadata', {})

            if not isinstance(additional_metadata, dict):

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

        return entry_dict

    def create_entity(self,
        merge_entry,
        entity_key,
        entity_data,
        entity_parent,
        client_id = None):
        """
        Creates new entity given merged entity data.
        """

        entity_kwargs = {
            'client_id': client_id or self.client_id,
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

        CACHE.set(objects = [merge_entity, ], DBSession=DBSession)
        # DBSession.add(merge_entity)

        log.debug(
            '{0}: {1} entit{2} of type \'{3}\' with content '
            '{4} merged into entity {5}/{6}:\n{7}'.format(
            self.method_string,
            len(entity_data['merge_set']),
            'y' if len(entity_data['merge_set']) == 1 else 'ies',
            entity_key[0],
            repr(entity_key[1]),
            merge_entity.client_id,
            merge_entity.object_id,
            pprint.pformat(dict(object_id = merge_entity.object_id, **entity_kwargs))))

        return merge_entity

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

        entry_data_list = [
            entry.track(False, 2, check_perspective = False)
            for entry in entry_list]

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

        entry_dict = self.merge_entry_data(entry_list, entry_data_list)

        log.debug('{0}: group {1}/{2}, merged lexical entries\' data:\n{3}'.format(
            self.method_string,
            index + 1,
            len(self.group_list),
            pprint.pformat(entry_dict)))

        # Creating new lexical entry.

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

            merge_entity = self.create_entity(
                merge_entry, entity_key, entity_data, entity_parent)

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
                CACHE.set(objects = [merge_entity, ], DBSession=DBSession)
                # DBSession.add(merge_entity)

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
                CACHE.set(objects = [merge_entity, ], DBSession=DBSession)
                # DBSession.add(merge_entity)

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

    def hash_fix(self, index_str, merge_entry, hash_content_dict):
        """
        Tries to update results of the merge after source lexical entries and entities were changed.
        """

        merge_tree = merge_entry.additional_metadata['merge']['merge_tree']
        linear_flag = True

        for entry_id in merge_tree:

            if (len(entry_id) != 2 or
                not isinstance(entry_id[0], int) or not isinstance(entry_id[1], int)):

                linear_flag = False
                break

        # If we have a simple linear merge tree (so, just a merge list), we get merged lexical entries by
        # their ids.

        if linear_flag:

            source_entry_id_list = merge_tree

            source_entry_list = DBSession.query(LexicalEntry).filter(
                tuple_(LexicalEntry.client_id, LexicalEntry.object_id).in_(
                    tuple(source_entry_id) for source_entry_id in source_entry_id_list)).all()

        # Otherwise we have to search for source lexical entries based on their merge metadata tags.

        else:

            source_entry_list = DBSession.query(LexicalEntry).filter(
                LexicalEntry.additional_metadata.contains({'merged_to':
                    [merge_entry.client_id, merge_entry.object_id]})).all()

            source_entry_id_list = [
                (source_entry.client_id, source_entry.object_id)
                for source_entry in source_entry_list]

        # Showing info of source lexical entries.

        log.debug('{0}: merge entry {1}/{2} ({3}), {4} source lexical entries ({5})'.format(
            self.method_string,
            merge_entry.client_id,
            merge_entry.object_id,
            index_str,
            len(source_entry_id_list),
            ', '.join('{0}/{1}'.format(*source_entry_id)
                for source_entry_id in source_entry_id_list)))

        # Getting and showing info of entites created in the merge being updated.

        merge_entity_list = DBSession.query(Entity).filter_by(
            parent_client_id = merge_entry.client_id,
            parent_object_id = merge_entry.object_id).all()

        merge_data = merge_entry.track(False, 2, None, None)

        log.debug('{0}: {1} merge entities ({2})\n{3}'.format(
            self.method_string,
            len(merge_entity_list),
            ', '.join('{0}/{1}'.format(entity.client_id, entity.object_id)
                for entity in merge_entity_list),
            pprint.pformat(merge_data)))

        merge_entity_dict = {
            (entity.client_id, entity.object_id): entity
            for entity in merge_entity_list}

        merge_dict = collections.defaultdict(set)

        def f(entity_data_list):
            """
            Filters entity track data by leaving only entities used in a merge, gathers info on what
            source entities were merged into which merge entities.
            """

            result_list = []

            for entity_data in entity_data_list:

                if ('additional_metadata' in entity_data and
                    'merged_to' in entity_data['additional_metadata']):

                    merged_to = tuple(
                        entity_data['additional_metadata']['merged_to'])

                    merge_dict[merged_to].add(
                        (entity_data['client_id'], entity_data['object_id']))

                    if 'contains' in entity_data:
                        entity_data['contains'] = f(entity_data['contains'])

                    result_list.append(entity_data)

            return result_list

        # Getting info of entities used for the merge.

        entry_data_list = []

        for source_entry in source_entry_list:
            entry_data = source_entry.track(False, 2, None, None)

            if 'contains' in entry_data:
                entry_data['contains'] = f(entry_data['contains'])

            entry_data_list.append(entry_data)

        log.debug('{0}: source lexical entries\' data:\n{1}'.format(
            self.method_string,
            pprint.pformat(entry_data_list, width = 144)))

        source_dict = {
            tuple(sorted(entity_id_set)): entity_id
            for entity_id, entity_id_set in merge_dict.items()}

        log.debug('{0}: source/merge entity correspondece:\n{1}'.format(
            self.method_string,
            pprint.pformat(source_dict)))

        # Merging lexical entry data.

        entry_dict = self.merge_entry_data(source_entry_list, entry_data_list)

        if len(entry_dict['additional_metadata']) > 0:
            entry_dict['additional_metadata'] = self.metadata_restore(entry_dict['additional_metadata'])

        log.debug('{0}: merged lexical entries\' data:\n{1}'.format(
            self.method_string,
            pprint.pformat(entry_dict, width = 144)))

        modify_set = set()

        def g(type, key, entity_data, entity_parent = None):
            """
            Looks through the merged data, processing hash-datatype ('Image', 'Markup', 'Sound') nodes.
            """

            log.debug('{0}: entity data {1}, {2}\n{3}'.format(
                self.method_string,
                repr(type),
                repr(key),
                pprint.pformat(entity_data)))

            merge_entity = None

            entity_set_key = tuple(
                sorted(entity_data['merge_set']))

            # Checking if we can reuse already existing entity.

            if entity_set_key in source_dict:

                merge_entity_id = source_dict[entity_set_key]
                merge_entity = merge_entity_dict[merge_entity_id]

                hash_flag = type in ['Image', 'Markup', 'Sound']

                log.debug('{0}: {1} entity {2}/{3}\n{4}'.format(
                    self.method_string,
                    'modifying' if hash_flag else 'reusing',
                    merge_entity.client_id,
                    merge_entity.object_id,
                    pprint.pformat({
                        key: getattr(merge_entity, key)
                        for key in dir(merge_entity)
                        if not key.startswith('_')})))

                # Ensuring proper child-parent entity linking, modifying hash, if required.

                if entity_parent is not None:

                    merge_entity.self_client_id = entity_parent.client_id
                    merge_entity.self_object_id = entity_parent.object_id

                else:

                    merge_entity.self_client_id = None
                    merge_entity.self_object_id = None

                if hash_flag:

                    merge_entity.additional_metadata['hash'] = \
                        entity_data['additional_metadata']['hash']

                    flag_modified(merge_entity, 'additional_metadata')

                modify_set.add(merge_entity_id)

            # We do not have an already existing merge entity, so we have to create a new one.

            else:

                # If 'publish_any' switch is not set, false 'publish' entity data key means that setting
                # 'publish_any' switch could have changed entity merge results, and we should take care.

                if not entity_data['published']:
                    raise NotImplementedError

                merge_entity = self.create_entity(
                    merge_entry, (type, key), entity_data, entity_parent,
                    client_id = merge_entry.client_id)

                # Updating merged entities.

                for c_id, o_id in sorted(entity_data['merge_set']):

                    entity = DBSession.query(Entity).filter_by(
                        client_id = c_id, object_id = o_id).one()

                    if entity.marked_for_deletion is not True:
                        raise NotImplementedError

                    entity.additional_metadata['merged_to'] = [
                        merge_entity.client_id, merge_entity.object_id]

                    flag_modified(entity, 'additional_metadata')

            # Processing underlying nodes.

            for (c_type, c_key), c_entity_data in entity_data['contains'].items():
                g(c_type, c_key, c_entity_data, merge_entity)

        # Trying to fix hash merges.

        for (type, key), entity_data_dict in entry_dict['contains'].items():
            g(type, key, entity_data_dict)

        # Checking if we have any unmodified merge entities we have to delete.

        for merge_entity in merge_entity_list:

            if (merge_entity.field.data_type not in ['Image', 'Markup', 'Sound'] or
                (merge_entity.client_id, merge_entity.object_id) in modify_set or
                'merge' not in merge_entity.additional_metadata):
                continue

            self_entity_count = DBSession.query(Entity).filter_by(
                self_client_id = merge_entity.client_id,
                self_object_id = merge_entity.object_id).count()

            if self_entity_count > 0:
                raise NotImplementedError

            # Showing info of the entity we are to delete, fixing its hash data, changing its merge data and
            # deleting it.

            log.debug('{0}: deleting entity {1}/{2}\n{3}'.format(
                self.method_string,
                merge_entity.client_id,
                merge_entity.object_id,
                pprint.pformat({
                    key: getattr(merge_entity, key)
                    for key in dir(merge_entity)
                    if not key.startswith('_')}, width = 144)))

            if (merge_entity.additional_metadata['hash'] ==
                'd14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f'):

                merge_entity.additional_metadata['hash'] = \
                    hash_content_dict[merge_entity.content]

            merge_entity.additional_metadata['merge_cancel'] = merge_entity.additional_metadata['merge']
            del merge_entity.additional_metadata['merge']

            flag_modified(merge_entity, 'additional_metadata')

            merge_entity.marked_for_deletion = True


def merge_bulk_try(
    request, publish_any, group_list, error_f):
    """
    Helper function for bulk merges.
    """

    client_id = request.authenticated_userid

    log.debug(
        '\nmerge_bulk:'
        '\n  client_id: {}'
        '\n  publish_any: {}'
        '\n  group_list:\n{}'
        '\n  error_f: {}'.format(
            client_id,
            publish_any,
            pprint.pformat(group_list, width = 144),
            error_f))

    try:

        # Getting client and user data.

        if not client_id:

            raise Exception(
                'Invalid client id {}, please relogin.'.format(
                    client_id))

        user = Client.get_user_by_client_id(client_id)

        if not user:

            raise Exception(
                'User authentification failure, client id: {}. Please relogin.'.format(
                    client_id))

        # Checking that each group has at least two lexical entries and that no specified lexical entry
        # belongs to a more than one group.

        entry_id_set = set()

        for index, group_entry_id_list in enumerate(group_list):

            group_entry_id_set = set(
                (entry_id['client_id'], entry_id['object_id'])
                for entry_id in group_entry_id_list)

            if len(group_entry_id_set) <= 1:

                raise Exception(
                    'Group {} {} does not have at least two unique lexical entry ids.'.format(
                        index, group_entry_id_set))

            if not group_entry_id_set.isdisjoint(entry_id_set):

                already_set = (
                    group_entry_id_set & entry_id_set)

                raise Exception(
                    'Group {} {} has previously encountered lexical entry id{} {}.'.format(
                        index,
                        group_entry_id_set,
                        '' if len(already_set) == 1 else 's',
                        already_set))

            entry_id_set.update(group_entry_id_set)

        # Processing lexical entries group by group.

        merge_context = (

            Merge_Context(
                'merge_bulk',
                request,
                client_id,
                user,
                publish_any,
                group_list))

        for index, entry_id_list in enumerate(merge_context.group_list):

            merge_context.merge_group(
                index, entry_id_list)

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = (

            ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1])

        log.debug('merge_bulk: exception')
        log.debug('\n' + traceback_string)

        return (
            False,
            error_f(message('\n' + traceback_string)))

    # Returning resulting merge data.

    log.debug('merge_bulk: result{0}{1}'.format(
        '\n' if len(merge_context.result_list) > 1 else ' ',
        pprint.pformat(merge_context.result_list)))

    return (
        True,
        merge_context)


@view_config(route_name = 'merge_bulk', renderer = 'json', request_method = 'POST')
def merge_bulk(request):
    """
    Merges multiple groups of lexical entries, provided that each group is a subset of a single perspective,
    returns client/object ids of new lexical entries, a new entry for each merged group.
    """

    try_ok, result = merge_bulk_try(request,
        request.json['publish_any'],
        request.json['group_list'],
        lambda error_message: {'error': error_message})

    if not try_ok:

        error_dict = result
        return error_dict

    # Returning identifiers of new lexical entries.

    merge_context = result
    return {'result': merge_context.result_list}


@view_config(route_name = 'merge_update_2', renderer = 'json', request_method = 'GET')
def merge_update_2(request):
    """
    Changes format of metadata of lexical entries created from merges of other lexical entries from the
    first version (with 'merge_tag' key) to the second version (with 'merge' key).
    """

    log.debug('merge_update_2')

    try:
        user = Client.get_user_by_client_id(request.authenticated_userid)

        if user is None or user.id != 1:
            return {'error': 'Not an administrator.'}

        entry_list = DBSession.query(LexicalEntry).filter(
            LexicalEntry.additional_metadata.has_key('merge_tag')).all()

        log.debug('merge_update_2: {0} lexical entries'.format(len(entry_list)))

        # Going through all lexical entries with metadata in version 1 format, assuming that repeated
        # queries of the same row return the same object.

        for entry in entry_list:

            log.debug('merge_update_2 {0}/{1} additional_metadata:\n{2}'.format(
                entry.client_id, entry.object_id, pprint.pformat(entry.additional_metadata)))

            min_created_at, original_author, merge_tree = build_merge_tree(entry)

            entry.additional_metadata['merge'] = {
                'min_created_at': min_created_at,
                'original_author': original_author,
                'merge_tree': merge_tree}

            del entry.additional_metadata['merge_tag']
            flag_modified(entry, 'additional_metadata')

            # Showing updated merge metadata.

            log.debug('merge_update_2 {0}/{1} additional_metadata:\n{2}'.format(
                entry.client_id, entry.object_id, pprint.pformat(entry.additional_metadata)))

        return len(entry_list)

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('merge_update_2: exception')
        log.debug('\n' + traceback_string)

        transaction.abort()

        return {'error': message('\n' + traceback_string)}


@view_config(route_name = 'merge_update_3', renderer = 'json', request_method = 'GET')
def merge_update_3(request):
    """
    Changes format of metadata of merged lexical entries from the 2nd version to the 3rd version by removing
    'original_author' merge metadata key and adding 'original_client_id' merge metadata key, and adding
    merge metadata to merged entities.
    """

    log.debug('merge_update_3')

    try:
        user = Client.get_user_by_client_id(request.authenticated_userid)

        if user is None or user.id != 1:
            return {'error': 'Not an administrator.'}

        entry_list = DBSession.query(LexicalEntry).filter(
            LexicalEntry.additional_metadata.has_key('merge')).all()

        log.debug('merge_update_3: {0} lexical entries'.format(len(entry_list)))

        # Going through all merged lexical entries, updating metadata if required.

        entry_count = 0
        for entry in entry_list:

            log.debug('merge_update_3: entry {0}/{1}: additional_metadata before:\n{2}'.format(
                entry.client_id, entry.object_id, pprint.pformat(entry.additional_metadata)))

            if 'original_author' not in entry.additional_metadata['merge']:
                continue

            min_created_at, original_client_id, merge_tree = build_merge_tree(entry)

            entry.additional_metadata['merge'] = {
                'min_created_at': min_created_at,
                'original_client_id': original_client_id,
                'merge_tree': merge_tree}

            flag_modified(entry, 'additional_metadata')

            # Showing updated merge metadata, counting another updated entity.

            log.debug('merge_update_3: entry {0}/{1}: additional_metadata after:\n{2}'.format(
                entry.client_id, entry.object_id, pprint.pformat(entry.additional_metadata)))

            entry_count += 1

        log.debug('merge_update_3: updated {0} lexical entries'.format(entry_count))

        # And now we should update merged entity metadata.

        entity_list_a = DBSession.query(Entity).filter(
            Entity.additional_metadata.has_key('merged_to')).all()

        entity_list_b = DBSession.query(Entity).filter(
            Entity.additional_metadata.has_key('merged_by')).all()

        entity_list = entity_list_a + entity_list_b

        log.debug('merge_update_3: {0} merged entities ({1} \'merged_to\', {2} \'merged_by\')'.format(
            len(entity_list), len(entity_list_a), len(entity_list_b)))

        # Gathering entities by merge results.

        entity_dict = {}
        merge_dict = collections.defaultdict(set)

        for entity in entity_list_a:
            entity_id = (entity.client_id, entity.object_id)

            entity_dict[entity_id] = entity
            merge_dict[tuple(entity.additional_metadata['merged_to'])].add(entity_id)

        for entity in entity_list_b:
            entity_id = (entity.client_id, entity.object_id)

            entity_dict[entity_id] = entity
            merge_dict[tuple(entity.additional_metadata['merged_by'])].add(entity_id)

        # NOTE: making local variable referencable from a local function by wrapping it in a singleton list.

        entity_count = [0]

        def update(entity_id, source_id_set):
            """
            Recursively updates merged entities.
            """

            if entity_id in entity_dict:
                entity = entity_dict[entity_id]

            else:
                entity_client_id, entity_object_id = entity_id

                entity = DBSession.query(Entity).filter_by(
                    client_id = entity_client_id, object_id = entity_object_id).first()

                entity_dict[entity_id] = entity

            if not entity.additional_metadata:
                entity.additional_metadata = {}

            if 'merge' in entity.additional_metadata:
                return

            # Updating source entities, if required, compiling merge metadata.

            min_created_at = None
            original_client_id = None

            for source_id in sorted(source_id_set):

                if source_id in merge_dict:
                    update(source_id, merge_dict[source_id])

                source = entity_dict[source_id]

                if min_created_at is None or source.created_at < min_created_at:

                    min_created_at = source.created_at
                    original_client_id = source.client_id

            # Updating the merge entity.

            log.debug('merge_update_3: entity {0}/{1}: additional_metadata before:\n{2}'.format(
                entity.client_id, entity.object_id, pprint.pformat(entity.additional_metadata)))

            entity.additional_metadata['merge'] = {
                'min_created_at': min_created_at,
                'original_client_id': original_client_id}

            flag_modified(entity, 'additional_metadata')

            log.debug('merge_update_3: entity {0}/{1}: additional_metadata after:\n{2}'.format(
                entity.client_id, entity.object_id, pprint.pformat(entity.additional_metadata)))

            entity_count[0] += 1

        # Updating all merged entities.

        for merge_id, source_id_set in merge_dict.items():
            update(merge_id, source_id_set)

        log.debug('merge_update_3: updated {0} entities'.format(entity_count[0]))
        return {'entries': entry_count, 'entities': entity_count[0]}

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('merge_update_3: exception')
        log.debug('\n' + traceback_string)

        transaction.abort()

        return {'error': message('\n' + traceback_string)}


def merge_bulk_task_try(task_status, merge_context):
    """
    Helper function for asynchronous background merge task.
    """

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

        return True, None

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('merge_bulk_async: exception')
        log.debug('\n' + traceback_string)

        print(traceback_string)

        if task_status is not None:
            task_status.set(1, 100, 'Finished (ERROR), external error')

        return False, traceback_string


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
        try_ok, traceback_string = merge_bulk_task_try(task_status, merge_context)

    if not try_ok:

        transaction.abort()

        return {'error': message('\n' + traceback_string)}


def merge_bulk_async_try(request, publish_any, group_list):
    """
    Helper function for asynchronous background merge task launch attempt.
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
            publish_any, group_list)

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
        return True, task_status

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('merge_bulk_async: exception')
        log.debug('\n' + traceback_string)

        if task_status is not None:
            task_status.set(1, 100, 'Finished (ERROR), external error')

        return False, traceback_string


@view_config(route_name = 'merge_bulk_async', renderer = 'json', request_method = 'POST')
def merge_bulk_async(request):
    """
    Launches asynchronous background merge task, see 'merge_bulk' procedure.
    """

    try_ok, result = merge_bulk_async_try(request,
        request.json['publish_any'],
        request.json['group_list'])

    # If something was not as expected, we report it.

    if not try_ok:

        traceback_string = result

        request.response.status = HTTPInternalServerError.code

        transaction.abort()

        return {'error': message('\n' + traceback_string)}

    # Launched asynchronous merge task successfully.

    task_status = result

    request.response.status = HTTPOk.code
    return {'result': task_status.key if task_status is not None else ''}


@view_config(route_name = 'hash_fix', renderer = 'json', request_method = 'GET')
def hash_fix(request):
    """
    Fixes, as much as possible, consequences of wrongly computed hashes of a subset of entities.
    """

    debug_flag = True
    log.debug('hash_fix')

    try:
        user = Client.get_user_by_client_id(request.authenticated_userid)

        if user is None or user.id != 1:
            return {'error': 'Not an administrator.'}

        # Getting info of entities with wrong hashes.

        entity_query = DBSession.query(Entity).filter(
            Entity.additional_metadata.contains({'hash':
                'd14a028c2a3a2bc9476102bb288234c415a2b01f828ea62ac5b3e42f'}))

        entity_count = entity_query.count()
        log.debug('hash_fix: {0} entities'.format(entity_count))

        entity_list = entity_query.all()

        merge_dict = collections.defaultdict(list)
        merge_entity_list = []

        for entity in entity_list:
            if 'merged_to' in entity.additional_metadata:

                merge_dict[tuple(entity.additional_metadata['merged_to'])].append(
                    (entity.client_id, entity.object_id))

        log.debug('hash_fix: {0} entities merged from, {1} entities merged to'.format(
            len(merge_dict),
            sum(len(merge_list) for merge_list in merge_dict.values())))

        # Righting hashes of entities not created by merges.

        storage = request.registry.settings['storage']
        hash_content_dict = {}

        for index, entity in enumerate(entity_list):
            entity_id = (entity.client_id, entity.object_id)

            if entity_id in merge_dict:
                merge_entity_list.append(entity)
                continue

            if entity.content in hash_content_dict:
                hash = hash_content_dict[entity.content]

            else:

                with storage_file(storage, entity.content) as entity_file:
                    hash = hashlib.sha224(entity_file.read()).hexdigest()

            entity.additional_metadata['hash'] = hash
            flag_modified(entity, 'additional_metadata')

            log.debug(
                'hash_fix: entity {0}/{1} ({2})\nurl: {3}\nhash: {4}'.format(
                    entity.client_id,
                    entity.object_id,
                    index,
                    entity.content,
                    hash))

            hash_content_dict[entity.content] = hash

        # Checking if we have any merge entities created through merges of other merge entities.

        intermediate_set = set()

        for entity_id, merge_list in merge_dict.items():

            for merge_id in merge_list:
                if merge_id in merge_dict:

                    intermediate_set.add(merge_id)

                    log.debug(
                        'hash_fix: entity {0} merged into entity {1} '
                        'and was merged from entities {2}.'.format(
                        merge_id, entity_id, merge_dict[merge_id]))

        log.debug('hash_fix: {0} intermediate merge entities'.format(
            len(intermediate_set)))

        if len(intermediate_set) > 0:
            raise NotImplementedError

        # Getting identifiers of lexical entries resulting from merges related to our merge entities.

        entry_list = []
        entry_entity_dict = collections.defaultdict(list)

        perspective_dict = {}

        for entity in merge_entity_list:

            entry = entity.parent
            entry_id = (entry.client_id, entry.object_id)

            entry_flag = entry_id not in entry_entity_dict

            if entry_flag:
                entry_list.append(entry)

            entry_entity_dict[entry_id].append(entity)

            # Getting perspective info, if required.

            if debug_flag:

                perspective = entry.parent
                perspective_id = (perspective.client_id, perspective.object_id)

                if perspective_id not in perspective_dict:
                    perspective_dict[perspective_id] = [perspective, 1]

                elif entry_flag:
                    perspective_dict[perspective_id][1] += 1

        log.debug('hash_fix: {0} merge lexical entries\n{1}'.format(
            len(entry_list),
            pprint.pformat(entry_entity_dict)))

        if debug_flag:

            # Showing additional info, if required.

            info_list = []

            for (perspective_cid, perspective_oid), (perspective, merge_entry_count) in sorted(
                perspective_dict.items()):

                dictionary = perspective.parent

                entry_count = DBSession.query(LexicalEntry).filter_by(
                    parent_client_id = perspective_cid,
                    parent_object_id = perspective_oid,
                    marked_for_deletion = False).count()

                info_list.append(
                    '\'{0}\' {1}/{2}:\n  \'{3}\' {4}/{5} '
                    '({6} lexical entries, {7} affected lexical entries)'.format(
                        dictionary.get_translation(locale_id = 2),
                        dictionary.client_id,
                        dictionary.object_id,
                        perspective.get_translation(locale_id = 2),
                        perspective_cid,
                        perspective_oid,
                        entry_count,
                        merge_entry_count))

            log.debug('hash_fix: {0} perspectives with affected merge entries\n{1}'.format(
                len(perspective_dict),
                '\n'.join(info_list)))

        # And now we try to fix merge lexical entries and entities.

        merge_context = Merge_Context(
            'hash_fix', request, request.authenticated_userid, user)

        for index, entry in enumerate(entry_list):

            merge_context.hash_fix(
                '{0}/{1}'.format(index + 1, len(entry_list)),
                entry,
                hash_content_dict)

    # If something is not right, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('hash_fix: exception')
        log.debug('\n' + traceback_string)

        transaction.abort()

        return {'error': message('\n' + traceback_string)}
