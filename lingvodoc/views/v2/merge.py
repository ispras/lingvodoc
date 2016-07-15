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
    Group,
    LexicalEntry,
    User
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
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError

import json
import logging

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
            subreq.json = json.dumps({'parent_object_id': parent_object_id, 'parent_client_id': parent_client_id,
                                'translation_string': translation_string, 'translation': translation})
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
            subreq.json = json.dumps({'translation_string': translation_string, 'translation': translation})
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
        subreq.json = json.dumps({'fields': fields})
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
                    metadata = json.loads(lex.additional_metadata)
                metadata['came_from'] = {'client_id': lex.parent_client_id, 'object_id': lex.parent_object_id}
                lex.additional_metadata = json.dumps(metadata)
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


@view_config(route_name='merge_suggestions', renderer='json', request_method='POST')
def merge_suggestions(request):  # TODO: test
    req = request.json
    entity_type_primary = req.get('entity_type_primary') or 'Transcription'
    entity_type_secondary = req.get('entity_type_secondary') or 'Translation'
    threshold = req['threshold'] or 0.2
    levenstein = req['levenstein'] or 1
    client_id = req['client_id']
    object_id = req['object_id']
    lexes = list(DBSession.query(LexicalEntry).filter_by(parent_client_id=client_id,
                                                         parent_object_id=object_id,
                                                         marked_for_deletion=False).all())
    if not lexes:
        return json.dumps([])
    # first_persp = json.loads(lexes[0].additional_metadata)['came_from']
    lexes_1 = [o.track(False) for o in lexes]
    remove_deleted(lexes_1)
    lexes_2 = list(lexes_1)

    def parse_response(elem):
        words = filter(lambda x: x['entity_type'] == entity_type_primary and not x['marked_for_deletion'], elem['contains'])
        words = map(lambda x: x['content'], words)
        trans = filter(lambda x: x['entity_type'] == entity_type_secondary and not x['marked_for_deletion'], elem['contains'])
        trans = map(lambda x: x['content'], trans)
        tuples_res = [(i_word, i_trans, (elem['client_id'], elem['object_id'])) for i_word in words for i_trans in trans]
        return tuples_res

    tuples_1 = [parse_response(i) for i in lexes_1]
    tuples_1 = [item for sublist in tuples_1 for item in sublist]
    tuples_2 = [parse_response(i) for i in lexes_2]
    tuples_2 = [item for sublist in tuples_2 for item in sublist]

    def get_dict(elem):
        return {'suggestion': [
            {'lexical_entry_client_id': elem[0][0], 'lexical_entry_object_id': elem[0][1]},
            {'lexical_entry_client_id': elem[1][0], 'lexical_entry_object_id': elem[1][1]}
        ], 'confidence': elem[2]}
    if (not tuples_1) or (not tuples_2):
        return {}
    results = [get_dict(i) for i in mergeDicts(tuples_1, tuples_2, float(threshold), int(levenstein))]
    results = sorted(results, key=lambda k: k['confidence'])
    return results
