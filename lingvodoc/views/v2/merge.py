
__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.merge_perspectives import (
    mergeDicts
    )
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
from lingvodoc.views.v2.utils import (
    remove_deleted
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPOk
)
from pyramid.request import Request
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy import and_, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

import collections
import itertools
import json
import logging
import pprint
import traceback

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


def check_user_merge_permissions(user_id, perspective_client_id, perspective_object_id):
    """
    Checks if the user has permissions required to merge lexical entries and entities, i.e. permissions to
    create and delete them.
    """

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


@view_config(
    route_name = 'merge_suggestions',
    renderer = 'json',
    request_method = 'POST',
    permission = 'view')
def merge_suggestions(request):
    """
    Finds groups of mergeable lexical entries according to specified criteria.
    """

    log.debug('merge_suggestions')

    perspective_client_id = request.matchdict.get('perspective_client_id')
    perspective_object_id = request.matchdict.get('perspective_object_id')

    req = request.json

    entity_type_primary = req.get('entity_type_primary') or 'Transcription'
    entity_type_secondary = req.get('entity_type_secondary') or 'Translation'

    threshold = req.get('threshold') or 0.2
    levenstein = req.get('levenstein') or 1

    locale_id = int(request.cookies.get('locale_id') or 2)

    # Checking if the user has sufficient permissions to perform suggested merges.

    user = Client.get_user_by_client_id(request.authenticated_userid)

    user_has_permissions = check_user_merge_permissions(
        user.id, perspective_client_id, perspective_object_id)

    # Getting data of the undeleted lexical entries of the perspective.

    lexical_entry_list = list(DBSession.query(LexicalEntry).filter_by(
        parent_client_id = perspective_client_id,
        parent_object_id = perspective_object_id,
        marked_for_deletion = False).all())

    if not lexical_entry_list:
        return []

    entry_data_list = [l.track(False, locale_id) for l in lexical_entry_list]
    remove_deleted(entry_data_list)

    log.debug('merge_suggestions {0}/{1}: {2} lexical entries'.format(
        perspective_client_id, perspective_object_id, len(entry_data_list)))

    def parse_response(entry_data):
        """
        Contructs description of a lexical entry to be used for matching.
        """

        word_list = map(lambda x: x['content'], filter(
            lambda x: x['entity_type'] == entity_type_primary and not x['marked_for_deletion'],
            entry_data['contains']))

        translation_list = map(lambda x: x['content'], filter(
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

    # Compiling match graph.

    match_result_list = mergeDicts(
        match_data_list, match_data_list, float(threshold), int(levenstein))

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

    # Returning match data together with data of matching lexical entries.

    return {

        'entry_data': [
            entry_data for entry_data in entry_data_list
                if (entry_data['client_id'], entry_data['object_id']) in adjacency_dict],

        'match_result': [
            ({'client_id': id_a[0], 'object_id': id_a[1]},
                {'client_id': id_b[0], 'object_id': id_b[1]},
                confidence)
                for id_a, id_b, confidence in match_result_list],

        'user_has_permissions': user_has_permissions}


@view_config(route_name = 'merge_bulk', renderer = 'json', request_method = 'POST')
def merge_bulk(request):
    """
    Merges multiple groups of lexical entries, provided that each group is a subset of a single perspective,
    returns client/object ids of new lexical entries, a new entry for each merged group.
    """

    log.debug('merge_bulk')

    # Getting client and user data.

    client_id = request.authenticated_userid

    if not client_id:
        return {'error': 'Unrecognized client.'}

    user = Client.get_user_by_client_id(client_id)
    user_permission_dict = {}

    if not user:
        return {'error': 'User authentification failure.'}

    def check_permissions(perspective_client_id, perspective_object_id):
        """
        Checks if the user has permissions to create/delete lexical entries and entities of a specified
        perspective, preferably using memoized permission values.
        """

        if (perspective_client_id, perspective_object_id) in user_permission_dict:
            return user_permission_dict[(perspective_client_id, perspective_object_id)]

        user_has_permissions = check_user_merge_permissions(
            user.id, perspective_client_id, perspective_object_id)

        user_permission_dict[(perspective_client_id, perspective_object_id)] = user_has_permissions
        return user_has_permissions

    def new_entity_dict(merge_entity_set, entity_data):
        """
        Creates new entity merge data.
        """

        entity_dict = {'additional_metadata': {}, 'contains': {}, 'merge_set': set([
            (entity_data['client_id'], entity_data['object_id'])])}

        merge_entity_set.add((entity_data['client_id'], entity_data['object_id']))

        for name in ['accepted', 'data_type', 'entity_type',
            'field_client_id', 'field_object_id', 'level', 'locale_id', 'published']:

            entity_dict[name] = entity_data[name]

        # As of now (Sun Jan 22 15:20:57 UTC 2017), we only support dicts as additional metadata.

        additional_metadata = entity_data.get('additional_metadata', {})

        if not isinstance(additional_metadata, dict):
            raise Exception('Unsupported additional metadata '
                'type \'{0}\'.'.format(type(additional_metadata)))

        metadata_merge(entity_dict['additional_metadata'], additional_metadata)

        if 'content' in entity_data:
            entity_dict['content'] = entity_data['content']

        if 'link_client_id' in entity_data:
            entity_dict['link_client_id'] = entity_data['link_client_id']
            entity_dict['link_object_id'] = entity_data['link_object_id']

        merge_contains(
            entity_dict['contains'], merge_entity_set,
            entity_data['contains'], (entity_data['client_id'], entity_data['object_id']))

        return entity_dict

    def merge_entity_dict(entity_dict, merge_entity_set, entity_data):
        """
        Updates entity merge data.
        """

        entity_dict['merge_set'].add((entity_data['client_id'], entity_data['object_id']))
        merge_entity_set.add((entity_data['client_id'], entity_data['object_id']))

        entity_dict['accepted'] = entity_dict['accepted'] and entity_data['accepted']
        entity_dict['published'] = entity_dict['published'] and entity_data['published']

        additional_metadata = entity_data.get('additional_metadata', {})

        if not isinstance(additional_metadata, dict):
            raise Exception('Unsupported additional metadata '
                'type \'{0}\'.'.format(type(additional_metadata)))

        metadata_merge(entity_dict['additional_metadata'], additional_metadata)

        merge_contains(
            entity_dict['contains'], merge_entity_set,
            entity_data['contains'], (entity_data['client_id'], entity_data['object_id']))

    def merge_contains(
        contains_dict, merge_entity_set, contains_list, container_id):

        """
        Merges entities contained in a lexical entry or another entity to already merged entities.
        """

        for entity_data in contains_list:

            # Self-linked entities which are not part of the container are skipped.

            if ('self_client_id' in entity_data and
                (entity_data['self_client_id'], entity_data['self_object_id']) != container_id):
                continue

            if entity_data['data_type'] == 'Grouping Tag' or entity_data['data_type'] == 'Text':
                entity_key = (entity_data['entity_type'], entity_data['content'])

            elif entity_data['data_type'] == 'Link':
                entity_key = (entity_data['entity_type'],
                    (entity_data['link_client_id'], entity_data['link_object_id']))

            elif entity_data['data_type'] == 'Sound' or entity_data['data_type'] == 'Markup':
                entity_key = (entity_data['entity_type'], entity_data['additional_metadata']['hash'])

            else:
                raise Exception('Can\'t merge entities of '
                    'type \'{0}\', please contact developers.'.format(entity_data['data_type']))

            # If we already have entity of the same type with the same data, we merge current entity
            # into it.

            if entity_key in contains_dict:
                merge_entity_dict(contains_dict[entity_key], merge_entity_set, entity_data)

            else:
                contains_dict[entity_key] = new_entity_dict(merge_entity_set, entity_data)

    def metadata_merge(metadata_dict, another_dict):
        """
        Structurally merges metadata, assuming that metadata is either a list or a dict.
        """

        for key, value in another_dict.items():

            if key not in metadata_dict:
                metadata_dict[key] = another_dict[key]

            elif isinstance(metadata_dict[key], dict) and isinstance(another_dict[key], dict):
                metadata_merge(metadata_dict[key], another_dict[key])

            elif isinstance(metadata_dict[key], list) and isinstance(another_dict[key], list):
                metadata_dict[key].extend(another_dict[key])

            elif isinstance(metadata_dict[key], set):
                metadata_dict[key].add(metadata_freeze(another_dict[key]))

            elif metadata_dict[key] != another_dict[key]:
                metadata_dict[key] = set(map(metadata_freeze, [metadata_dict[key], another_dict[key]]))

    def metadata_freeze(object):
        """
        Transforms objects stored in a merged metadata dictionary into hashable representations.
        """

        if isinstance(object, set):
            return ('set', frozenset(map(metadata_freeze, object)))

        elif isinstance(object, dict):
            return ('dict', frozenset([
                (metadata_freeze(key), metadata_freeze(value))
                for key, value in dict.items()]))

        elif isinstance(object, list):
            return ('list', tuple(map(metadata_freeze, object)))

        else:
            return object

    def metadata_restore(object):
        """
        Restores metadata objects from hashable representations.
        """

        if not isinstance(object, tuple):
            return object

        elif object[0] == 'set':
            return sorted(map(metadata_restore, object[1]))

        elif object[0] == 'dict':
            return dict([(metadata_restore(key), metadata_restore(value)) for key, value in object[1]])

        elif object[0] == 'list':
            return [metadata_restore(item) for item in object[1]]

        else:
            raise Exception('Unknown metadata object type \'{0}\'.'.format(type(object)))

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

            raise Exception(
                'Trying to merge lexical object {0}/{1}, which '
                'is already merged into lexical object {2}/{3}.'.format(
                    object.client_id, object.object_id, *object.additional_metadata[merge_tag]))

        else:
            object.additional_metadata[merge_tag] = merge_id

        flag_modified(object, 'additional_metadata')

        # Updating object ToC.

        objecttoc = DBSession.query(ObjectTOC).filter_by(
            client_id = object.client_id, object_id = object.object_id).one()

        objecttoc.marked_for_deletion = True

    # Processing lexical entries group by group.

    try:
        json_data = request.json
        group_list = request.json['group_list']
        result_list = []

        log.debug('merge_bulk: {0} lexical entry group{1}:\n{2}'.format(
            len(group_list), '' if len(group_list) == 1 else 's', pprint.pformat(group_list)))

        for index, entry_id_list in enumerate(group_list):

            entry_list = DBSession.query(LexicalEntry).filter(
                tuple_(LexicalEntry.client_id, LexicalEntry.object_id).in_(
                    (entry['client_id'], entry['object_id']) for entry in entry_id_list)).all()

            # Checking that all lexical entries belong to the same perspective, and that the user has
            # necessary permissions to perform the merge.

            perspective_id = None
            for entry in entry_list:

                if perspective_id is None:
                    perspective_id = (entry.parent_client_id, entry.parent_object_id)

                elif perspective_id != (entry.parent_client_id, entry.parent_object_id):
                    return {'error': 'Entries {0} are from different perspectives.'.format(
                        entry_id_list)}

            if not check_permissions(*perspective_id):
                return {'error': 'No create/delete permissions for perspective {0}/{1}.'.format(
                    *perspective_id)}

            log.debug('merge_bulk: group {0}/{1}, {2} lexical entries, perspective {3}/{4}'.format(
                index + 1, len(group_list), len(entry_id_list), *perspective_id))

            # Merging lexical entry data.

            entry_data_list = [e.track(False, 2) for e in entry_list]
            remove_deleted(entry_data_list)

            log.debug('merge_bulk: group {0}/{1}, lexical entries\' ids:\n{2}'.format(
                index + 1, len(group_list), pprint.pformat(entry_id_list)))

            log.debug('merge_bulk: group {0}/{1}, lexical entries\' data:\n{2}'.format(
                index + 1, len(group_list), pprint.pformat(entry_data_list)))

            entry_dict = {
                'additional_metadata': {},
                'contains': {},
                'merge_entry_dict': {},
                'merge_entity_set': set(),
                'published': True}

            for entry, entry_data in zip(entry_list, entry_data_list):
                entry_dict['merge_entry_dict'][(entry.client_id, entry.object_id)] = entry

                # Processing each lexical entry to be merged.

                if len(set(entry_data.keys()).difference(set([
                    'additional_metadata', 'client_id', 'contains', 'level', 'marked_for_deletion',
                    'object_id', 'parent_client_id', 'parent_object_id', 'published']))) > 0:
                    return {'error': 'Unexpected lexical entry data keys.'}

                additional_metadata = entry_data.get('additional_metadata', {})

                if not isinstance(additional_metadata, dict):
                    return {'error': 'Unsupported additional metadata type \'{0}\'.'.format(
                        type(additional_metadata))}

                entry_dict['published'] = entry_dict['published'] and entry_data['published']

                metadata_merge(entry_dict['additional_metadata'], additional_metadata)

                merge_contains(
                    entry_dict['contains'], entry_dict['merge_entity_set'],
                    entry_data['contains'], (entry_data['client_id'], entry_data['object_id']))

            # If merged entries were themselves merge results, we don't care.

            entry_dict['additional_metadata']['merge_tag'] = len(entry_list)

            # Creating new lexical entry.

            log.debug('merge_bulk: group {0}/{1}, merged lexical entries\' data:\n{2}'.format(
                index + 1, len(group_list), pprint.pformat(entry_dict)))

            entry_kwargs = {
                'client_id': client_id,
                'parent_client_id': perspective_id[0],
                'parent_object_id': perspective_id[1]}

            if len(entry_dict['additional_metadata']) > 0:
                metadata = metadata_restore(entry_dict['additional_metadata'])
                entry_dict['additional_metadata'] = metadata
                entry_kwargs['additional_metadata'] = metadata

            # NOTE: we do not process 'published' key in lexical entry metadata.

            merge_entry = LexicalEntry(**entry_kwargs)
            DBSession.add(merge_entry)

            result_list.append({
                'client_id': merge_entry.client_id,
                'object_id': merge_entry.object_id})

            log.debug(
                'merge_bulk: group {0}/{1}, {2} lexical entr{3} '
                'merged into lexical entry {4}/{5}:\n{6}'.format(
                index + 1, len(group_list), len(entry_id_list), 'y' if len(entry_id_list) == 1 else 'ies',
                merge_entry.client_id, merge_entry.object_id,
                pprint.pformat(dict(object_id = merge_entry.object_id, **entry_kwargs))))

            def merge_entities(entity_key, entity_data, entity_parent = None):
                """
                Recursively creates new entities from merged entities.
                """

                entity_kwargs = {
                    'client_id': client_id,
                    'field_client_id': entity_data['field_client_id'],
                    'field_object_id': entity_data['field_object_id'],
                    'locale_id': entity_data['locale_id'],
                    'parent_client_id': merge_entry.client_id,
                    'parent_object_id': merge_entry.object_id}

                # Optional attributes.

                if len(entity_data['additional_metadata']) > 0:
                    metadata = metadata_restore(entity_data['additional_metadata'])
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
                    'merge_bulk: group {0}/{1}, {2} entit{3} of type \'{4}\' '
                    'with content {5} merged into entity {6}/{7}:\n{8}'.format(
                    index + 1, len(group_list), len(entity_data['merge_set']),
                    'y' if len(entity_data['merge_set']) == 1 else 'ies',
                    entity_key[0], repr(entity_key[1]),
                    merge_entity.client_id, merge_entity.object_id,
                    pprint.pformat(dict(object_id = merge_entity.object_id, **entity_kwargs))))

                # Updating merged entities.

                for c_id, o_id in sorted(entity_data['merge_set']):

                    entity = DBSession.query(Entity).filter_by(
                        client_id = c_id, object_id = o_id).one()

                    mark_delete_merge(entity, 'merged_to',
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
                    'merge_bulk: group {0}/{1}, replaced entity {2}/{3}: '
                    '{4} non-deleted self-link entit{5}:{6}{7}'.format(
                    index + 1, len(group_list), entity.client_id, entity.object_id,
                    len(self_entity_list),
                    'y' if len(self_entity_list) == 1 else 'ies',
                    '\n' if len(self_entity_list) > 1 else ' ',
                    pprint.pformat([(e.client_id, e.object_id) for e in self_entity_list])))

                # Replacing found reference entities, and then recursively replacing any entities
                # referencing them.

                for self_entity in self_entity_list:

                    entity_kwargs = {
                        'client_id': client_id,
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
                            entity_kwargs[name] = getattr(self_entity, name)

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

                    merge_entity = Entity(**entity_kwargs)
                    DBSession.add(merge_entity)

                    log.debug(
                        'merge_bulk: group {0}/{1}, replaced entity {2}/{3}, self-link '
                        'entity {4}/{5} replaced by entity {6}/{7}:\n{8}'.format(
                        index + 1, len(group_list),
                        entity.client_id, entity.object_id,
                        self_entity.client_id, self_entity.object_id,
                        merge_entity.client_id, merge_entity.object_id,
                        pprint.pformat(dict(object_id = merge_entity.object_id, **entity_kwargs))))

                    # Marking replaced entity as deleted and replaced due to merge.

                    replace_entity_dict[(self_entity.client_id, self_entity.object_id)] = \
                        (merge_entity.client_id, merge_entity.object_id)

                    mark_delete_merge(self_entity, 'merged_by',
                        [merge_entity.client_id, merge_entity.object_id])

                    # Recursively looking up entities which reference replaced entity and replacing them
                    # too, if required.

                    self_reference_replace(self_entity)

            # Marking merged lexical entries as deleted and merged.

            for (c_id, o_id), entry in sorted(entry_dict['merge_entry_dict'].items()):

                mark_delete_merge(entry, 'merged_to',
                    [merge_entry.client_id, merge_entry.object_id])

                # Looking up any non-deleted entities representing links to the merged lexical entry, just
                # in case filtering out any entities that will be merged.

                link_entity_list = DBSession.query(Entity).filter_by(
                    link_client_id = entry.client_id, link_object_id = entry.object_id,
                    marked_for_deletion = False).all()

                log.debug(
                    'merge_bulk: group {0}/{1}, merged lexical entry {2}/{3}: '
                    '{4} non-deleted incoming link entit{5}:{6}{7}'.format(
                    index + 1, len(group_list), entry.client_id, entry.object_id,
                    len(link_entity_list),
                    'y' if len(link_entity_list) == 1 else 'ies',
                    '\n' if len(link_entity_list) > 1 else ' ',
                    pprint.pformat([(e.client_id, e.object_id) for e in link_entity_list])))

                # Replacing such links, and then recursively replacing any entities referencing them.

                for link_entity in link_entity_list:

                    entity_kwargs = {
                        'client_id': client_id,
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
                            entity_kwargs[name] = getattr(link_entity, name)

                    # Checking that link entity does not additionally reference one of the merge entities
                    # through self_client/object_id or one of the merge entries through parent_client/
                    # object_id (in that case link replacement breaks, but it should be impossible).

                    self_id = (link_entity.self_client_id, link_entity.self_object_id)
                    parent_id = (link_entity.parent_client_id, link_entity.parent_object_id)

                    if (self_id in entry_dict['merge_entity_set'] or
                        parent_id in entry_dict['merge_entry_dict']):

                        return {'error':
                            'Unexpected additional reference from entity {0}/{1} (lexical '
                            'entry group {2}), please contact developers.'.format(
                                link_entity.client_id, link_entity.object_id, entry_id_list)}

                    # Creating new entity to replace link entity.

                    merge_entity = Entity(**entity_kwargs)
                    DBSession.add(merge_entity)

                    log.debug(
                        'merge_bulk: group {0}/{1}, merged lexical entry {2}/{3}, incoming '
                        'link entity {4}/{5} replaced by entity {6}/{7}:\n{8}'.format(
                        index + 1, len(group_list),
                        entry.client_id, entry.object_id,
                        link_entity.client_id, link_entity.object_id,
                        merge_entity.client_id, merge_entity.object_id,
                        pprint.pformat(dict(object_id = merge_entity.object_id, **entity_kwargs))))

                    # Marking replaced entity as deleted and replaced due to merge.

                    replace_entity_dict[(link_entity.client_id, link_entity.object_id)] = \
                        (merge_entity.client_id, merge_entity.object_id)

                    mark_delete_merge(link_entity, 'merged_by',
                        [merge_entity.client_id, merge_entity.object_id])

                    # Recursively looking up entities which reference replaced entity and replacing them
                    # too, if required.

                    self_reference_replace(link_entity, merge_entity)

    # If something is not write, we report it.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('merge_bulk: exception')
        log.debug(traceback_string)

        request.response.status = HTTPInternalServerError.code
        return {'error': str(exception)}

    # Returning identifiers of new lexical entries.

    log.debug('merge_bulk: result{0}{1}'.format(
        '\n' if len(result_list) > 1 else ' ', pprint.pformat(result_list)))

    return result_list

