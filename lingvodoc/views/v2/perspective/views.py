__author__ = 'alexander'

from collections import deque
import base64
import datetime
import hashlib
import json
import logging
import multiprocessing

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPForbidden,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.renderers import render_to_response
from pyramid.request import Request
from pyramid.response import Response
from pyramid.security import authenticated_userid
from pyramid.view import view_config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from lingvodoc.cache.caching import MEMOIZE
from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    Group,
    LexicalEntry,
    Organization,
    User,
    TranslationAtom,
    TranslationGist,
    Field,
    DictionaryPerspectiveToField
)
from lingvodoc.views.v2.utils import (
    cache_clients,
    create_object,
    get_user_by_client_id,
    user_counter,
    view_perspective_from_object,
    view_field_from_object
)

log = logging.getLogger(__name__)


@view_config(route_name='all_perspectives', renderer = 'json', request_method='GET')
def perspectives_list(request):  # tested
    response = list()
    is_template = None
    try:
        is_template = request.GET.get('is_template')
    except:
        pass
    state_translation_gist_client_id = request.params.get('state_translation_gist_client_id', None)
    state_translation_gist_object_id = request.params.get('state_translation_gist_object_id', None)
    persps = DBSession.query(DictionaryPerspective).filter(DictionaryPerspective.marked_for_deletion==False)
    if is_template is not None:
        if type(is_template) == str:
            if is_template.lower() == 'true':
                is_template = True
            elif is_template.lower() == 'false':
                is_template = False
            else:
                request.response.status = HTTPBadRequest.code
                # TODO: write normal return
                return

        persps = persps.filter(DictionaryPerspective.is_template == is_template)
    if state_translation_gist_client_id and state_translation_gist_object_id:
        persps = persps.filter(DictionaryPerspective.state_translation_gist_client_id==state_translation_gist_client_id,
                               DictionaryPerspective.state_translation_gist_object_id==state_translation_gist_object_id)
    perspectives = []
    for perspective in persps:
        resp = view_perspective_from_object(request, perspective)
        if 'error' not in resp:
            perspectives.append(resp)
    response = perspectives
    request.response.status = HTTPOk.code

    return response


@view_config(route_name='perspective', renderer='json', request_method='GET')
@view_config(route_name='perspective_outside', renderer='json', request_method='GET')
def view_perspective(request): # tested & in docs
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = None
    if parent_client_id and parent_object_id:
        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    response = view_perspective_from_object(request, perspective)
    if 'error' in response:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}
    request.response.status = HTTPOk.code
    return response


# TODO: completely broken!
@view_config(route_name='perspective_hash', renderer='json', request_method='PUT', permission='edit')
def edit_perspective_hash(request):
    import requests
    try:
        response = dict()
        client_id = request.matchdict.get('perspective_client_id')
        object_id = request.matchdict.get('perspective_id')
        client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        parent_client_id = request.matchdict.get('dictionary_client_id')
        parent_object_id = request.matchdict.get('dictionary_object_id')
        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such dictionary in the system")}

        perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if perspective:
            if not perspective.marked_for_deletion:
                l1es = list()
                # l1es = DBSession.query(LevelOneEntity)\
                #     .join(LexicalEntry,
                #           and_(LevelOneEntity.parent_client_id == LexicalEntry.client_id,
                #                LevelOneEntity.parent_object_id == LexicalEntry.object_id,
                #                LexicalEntry.parent_client_id == client_id,
                #                LexicalEntry.parent_object_id == object_id))\
                #     .filter(func.lower(LevelOneEntity.entity_type).like('%sound%'), or_(LevelOneEntity.additional_metadata == None,
                #                                                                         not_(LevelOneEntity.additional_metadata.like('%hash%'))))
                count_l1e = l1es.count()
                for l1e in l1es:

                    url = l1e.content
                    try:
                        r = requests.get(url)
                        hash = hashlib.sha224(r.content).hexdigest()
                        old_meta = l1e.additional_metadata
                        hash_dict = {'hash': hash}
                        if old_meta:
                            new_meta = json.loads(old_meta)
                            new_meta.update(hash_dict)
                        else:
                            new_meta = hash_dict
                        l1e.additional_metadata = json.dumps(new_meta)
                    except:
                        print('fail with sound', l1e.client_id, l1e.object_id)
                # l2es = DBSession.query(LevelTwoEntity)\
                #     .join(LevelOneEntity,
                #           and_(LevelTwoEntity.parent_client_id == LevelOneEntity.client_id,
                #                LevelTwoEntity.parent_object_id == LevelOneEntity.object_id))\
                #     .join(LexicalEntry,
                #           and_(LevelOneEntity.parent_client_id == LexicalEntry.client_id,
                #                LevelOneEntity.parent_object_id == LexicalEntry.object_id,
                #                LexicalEntry.parent_client_id == client_id,
                #                LexicalEntry.parent_object_id == object_id))\
                #     .filter(func.lower(LevelTwoEntity.entity_type).like('%markup%'), or_(LevelTwoEntity.additional_metadata == None,
                #                                                                         not_(LevelTwoEntity.additional_metadata.like('%hash%'))))
                l2es = list()
                count_l2e = l2es.count()
                for l2e in l2es:
                    url = l2e.content
                    try:
                        r = requests.get(url)
                        hash = hashlib.sha224(r.content).hexdigest()
                        old_meta = l2e.additional_metadata
                        hash_dict = {'hash': hash}
                        if old_meta:
                            new_meta = json.loads(old_meta)
                            new_meta.update(hash_dict)
                        else:
                            new_meta = hash_dict
                        l2e.additional_metadata = json.dumps(new_meta)
                    except:
                        print('fail with markup', l2e.client_id, l2e.object_id)
                response['count_l1e'] = count_l1e
                response['count_l2e'] = count_l2e
                request.response.status = HTTPOk.code
                return response
        else:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such perspective in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}


@view_config(route_name='dangerous_perspectives_hash', renderer='json', request_method='PUT', permission='edit')
def dangerous_perspectives_hash(request):  # TODO: test?
    response = dict()
    perspectives = DBSession.query(DictionaryPerspective)
    for perspective in perspectives:
        path = request.route_url('perspective_hash',
                                 dictionary_client_id=perspective.parent_client_id,
                                 dictionary_object_id=perspective.parent_object_id,
                                 perspective_client_id=perspective.client_id,
                                 perspective_id=perspective.object_id)
        subreq = Request.blank(path)
        subreq.method = 'PUT'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        print('Perspective', perspective.client_id, perspective.object_id, 'ready')
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='perspective_meta', renderer='json', request_method='PUT', permission='edit')
def edit_perspective_meta(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'error': str("No such pair of dictionary/perspective in the system")}
            try:
                req = request.json_body
            except ValueError:
                request.response.status = HTTPBadRequest.code
                return {'error': 'body is invalid json or empty'}
            if perspective.additional_metadata:
                old_meta = json.loads(perspective.additional_metadata)
                new_meta = req
                old_meta.update(new_meta)
                perspective.additional_metadata = json.dumps(old_meta)
            else:
                perspective.additional_metadata = json.dumps(req)
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_meta', renderer='json', request_method='DELETE', permission='edit')
def delete_perspective_meta(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'error': str("No such pair of dictionary/perspective in the system")}
            try:
                req = request.json_body
            except ValueError:
                request.response.status = HTTPBadRequest.code
                return {'error': 'body is invalid json or empty'}
            old_meta = json.loads(perspective.additional_metadata)
            new_meta = req
            for entry in new_meta:
                if entry in old_meta:
                    del old_meta[entry]
            perspective.additional_metadata = json.dumps(old_meta)
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_meta', renderer='json', request_method='GET')
def view_perspective_meta(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'error': str("No such pair of dictionary/perspective in the system")}

            old_meta = json.loads(perspective.additional_metadata)
            response = old_meta
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_tree', renderer='json', request_method='GET')
@view_config(route_name='perspective_outside_tree', renderer='json', request_method='GET')
def view_perspective_tree(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = None
    if parent_client_id and parent_object_id:
        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            tree = []
            resp = view_perspective_from_object(request, perspective)
            resp.update({"type": "perspective"})
            tree.append(resp)
            dictionary = perspective.parent
            path = request.route_url('dictionary',
                                 client_id=dictionary.client_id,
                                 object_id=dictionary.object_id)
            subreq = Request.blank(path)
            subreq.method = 'GET'
            subreq.headers = request.headers
            resp = request.invoke_subrequest(subreq)
            if 'error' not in resp.json:
                elem = resp.json.copy()
                elem.update({'type': 'dictionary'})
                tree.append(elem)
            parent = dictionary.parent
            while parent:
                path = request.route_url('language',
                                     client_id=parent.client_id,
                                     object_id=parent.object_id)
                subreq = Request.blank(path)
                subreq.method = 'GET'
                subreq.headers = request.headers
                resp = request.invoke_subrequest(subreq)
                parent = parent.parent
                if 'error' not in resp.json:
                    elem = resp.json.copy()
                    elem.update({'type': 'language'})
                    tree.append(elem)
                else:
                    parent = None

                request.response.status = HTTPOk.code
            return tree

    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_info', renderer='json', request_method='GET', permission='view')
def perspective_info(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    starting_date = request.GET.get('starting_date')
    if starting_date:
        starting_date = datetime.datetime.strptime(starting_date, "%d%m%Y").date()
    ending_date = request.GET.get('ending_date')
    if ending_date:
        ending_date = datetime.datetime(ending_date)
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective) \
        .options(joinedload('lexicalentry').joinedload('leveloneentity').joinedload('leveltwoentity').joinedload('publishleveltwoentity')) \
        .options(joinedload('lexicalentry').joinedload('leveloneentity').joinedload('publishleveloneentity')) \
        .options(joinedload('lexicalentry').joinedload('groupingentity').joinedload('publishgroupingentity')) \
        .options(joinedload('lexicalentry').joinedload('publishleveloneentity')) \
        .options(joinedload('lexicalentry').joinedload('publishleveltwoentity')) \
        .options(joinedload('lexicalentry').joinedload('publishgroupingentity')) \
        .filter_by(client_id=client_id, object_id=object_id).first()

    if perspective:
        if not perspective.marked_for_deletion:
            result = []
            path = request.route_url('perspective_fields',
                                     dictionary_client_id=perspective.parent_client_id,
                                     dictionary_object_id=perspective.parent_object_id,
                                     perspective_client_id=perspective.client_id,
                                     perspective_id=perspective.object_id
                                     )
            subreq = Request.blank(path)
            subreq.method = 'GET'
            subreq.headers = request.headers
            resp = request.invoke_subrequest(subreq)
            fields = resp.json["fields"]
            types = []
            for field in fields:
                entity_type = field['entity_type']
                if entity_type not in types:
                    types.append(entity_type)
                if 'contains' in field:
                    for field2 in field['contains']:
                        entity_type = field2['entity_type']
                        if entity_type not in types:
                            types.append(entity_type)

            clients_to_users_dict = cache_clients()

            for lex in perspective.lexicalentry:
                result = user_counter(lex.track(True), result, starting_date, ending_date, types, clients_to_users_dict)

            response['count'] = result
            request.response.status = HTTPOk.code
            return response

    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name = 'create_perspective', renderer = 'json', request_method = 'POST', permission='create')
def create_perspective(request):  # tested & in docs
    try:
        variables = {'auth': authenticated_userid(request)}
        parent_client_id = request.matchdict.get('dictionary_client_id')
        parent_object_id = request.matchdict.get('dictionary_object_id')

        try:
            if type(request.json_body) == str:
                req = json.loads(request.json_body)
            else:
                req = request.json_body
        except AttributeError:
            request.response.status = HTTPBadRequest.code
            return {'error': "invalid json"}
        translation_gist_client_id = req['translation_gist_client_id']
        translation_gist_object_id = req['translation_gist_object_id']
        is_template = req.get('is_template')
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such dictionary in the system")}
        coord = {}
        latitude = req.get('latitude')
        longitude = req.get('longitude')
        if latitude:
            coord['latitude'] = latitude
        if longitude:
            coord['longitude'] = longitude
        additional_metadata = req.get('additional_metadata')
        if additional_metadata:
            additional_metadata.update(coord)
        else:
            additional_metadata = coord
        additional_metadata = json.dumps(additional_metadata)

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = json.dumps({'searchstring': 'WiP'})
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)

        if 'error' not in resp.json:
            state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json['client_id']
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])

        perspective = DictionaryPerspective(client_id=variables['auth'],
                                            state_translation_gist_object_id=state_translation_gist_object_id,
                                            state_translation_gist_client_id=state_translation_gist_client_id,
                                            parent=parent,
                                            import_source=req.get('import_source'),
                                            import_hash=req.get('import_hash'),
                                            additional_metadata=additional_metadata,
                                            translation_gist_client_id=translation_gist_client_id,
                                            translation_gist_object_id=translation_gist_object_id
                                            )
        if is_template is not None:
            perspective.is_template = is_template
        DBSession.add(perspective)
        DBSession.flush()
        owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
        owner = owner_client.user
        for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
            new_group = Group(parent=base,
                              subject_object_id=perspective.object_id, subject_client_id=perspective.client_id)
            if user not in new_group.users:
                new_group.users.append(user)
            if owner not in new_group.users:
                new_group.users.append(owner)
            DBSession.add(new_group)
            DBSession.flush()
        request.response.status = HTTPOk.code
        return {'object_id': perspective.object_id,
                'client_id': perspective.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='perspectives', renderer='json', request_method='GET')
def view_perspectives(request):
    response = list()
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}
    perspectives = []
    for perspective in parent.dictionaryperspective:
        path = request.route_url('perspective',
                                 dictionary_client_id=parent_client_id,
                                 dictionary_object_id=parent_object_id,
                                 perspective_client_id=perspective.client_id,
                                 perspective_id=perspective.object_id)
        subreq = Request.blank(path)
        subreq.method = 'GET'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if 'error' not in resp.json:
            perspectives += [resp.json]
    response = perspectives
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='perspective_roles', renderer='json', request_method='GET', permission='view')
def view_perspective_roles(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('client_id')
    parent_object_id = request.matchdict.get('object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            bases = DBSession.query(BaseGroup).filter_by(perspective_default=True)
            roles_users = dict()
            roles_organizations = dict()
            for base in bases:
                group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                         subject_object_id=object_id,
                                                         subject_client_id=client_id).first()
                perm = base.name
                users = []
                for user in group.users:
                    users += [user.id]
                organizations = []
                for org in group.organizations:
                    organizations += [org.id]
                roles_users[perm] = users
                roles_organizations[perm] = organizations
            response['roles_users'] = roles_users
            response['roles_organizations'] = roles_organizations

            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'POST', permission='create')
def edit_perspective_roles(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('client_id')
    parent_object_id = request.matchdict.get('object_id')

    if type(request.json_body) == str:
        req = json.loads(request.json_body)
    else:
        req = request.json_body
    roles_users = None
    if 'roles_users' in req:
        roles_users = req['roles_users']
    roles_organizations = None
    if 'roles_organizations' in req:
        roles_organizations = req['roles_organizations']

    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective and not perspective.marked_for_deletion:
        if roles_users:
            for role_name in roles_users:
                base = DBSession.query(BaseGroup).filter_by(name=role_name, perspective_default=True).first()
                if not base:
                    log.debug("Not found role: " + role_name)
                    request.response.status = HTTPNotFound.code
                    return {'error': str("No such role in the system")}

                group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                         subject_object_id=object_id,
                                                         subject_client_id=client_id).first()

                client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()

                userlogged = DBSession.query(User).filter_by(id=client.user_id).first()

                permitted = False
                if userlogged in group.users:
                    permitted = True
                if not permitted:
                    for org in userlogged.organizations:
                        if org in group.organizations:
                            permitted = True
                            break

                if permitted:
                    users = roles_users[role_name]
                    for userid in users:
                        user = DBSession.query(User).filter_by(id=userid).first()
                        if user:
                            if user not in group.users:
                                group.users.append(user)
                else:
                    request.response.status = HTTPForbidden.code
                    return {'error': str("Not enough permission")}

        if roles_organizations:
            for role_name in roles_organizations:
                base = DBSession.query(BaseGroup).filter_by(name=role_name, perspective_default=True).first()
                if not base:
                    request.response.status = HTTPNotFound.code
                    return {'error': str("No such role in the system")}

                group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                         subject_object_id=object_id,
                                                         subject_client_id=client_id).first()

                client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()

                userlogged = DBSession.query(User).filter_by(id=client.user_id).first()

                permitted = False
                if userlogged in group.users:
                    permitted = True
                if not permitted:
                    for org in userlogged.organizations:
                        if org in group.organizations:
                            permitted = True
                            break

                if permitted:
                    orgs = roles_organizations[role_name]
                    for orgid in orgs:
                        org = DBSession.query(Organization).filter_by(id=orgid).first()
                        if org:
                            if org not in group.organizations:
                                group.organizations.append(org)
                else:
                    request.response.status = HTTPForbidden.code
                    return {'error': str("Not enough permission")}

        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'DELETE', permission='delete')
def delete_perspective_roles(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('client_id')
    parent_object_id = request.matchdict.get('object_id')
    req = request.json_body
    roles_users = None
    if 'roles_users' in req:
        roles_users = req['roles_users']
    roles_organizations = None
    if 'roles_organizations' in req:
        roles_organizations = req['roles_organizations']

    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if roles_users:
                for role_name in roles_users:
                    base = DBSession.query(BaseGroup).filter_by(name=role_name, perspective_default=True).first()
                    if not base:
                        request.response.status = HTTPNotFound.code
                        return {'error': str("No such role in the system")}

                    group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                             subject_object_id=object_id,
                                                             subject_client_id=client_id).first()

                    client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()

                    userlogged = DBSession.query(User).filter_by(id=client.user_id).first()

                    permitted = False
                    if userlogged in group.users:
                        permitted = True
                    if not permitted:
                        for org in userlogged.organizations:
                            if org in group.organizations:
                                permitted = True
                                break

                    if permitted:
                        users = roles_users[role_name]
                        for userid in users:
                            user = DBSession.query(User).filter_by(id=userid).first()
                            if user:
                                if user.id == userlogged.id:
                                    request.response.status = HTTPForbidden.code
                                    return {'error': str("Cannot delete roles from self")}
                                if user in group.users:
                                    group.users.remove(user)
                    else:
                        request.response.status = HTTPForbidden.code
                        return {'error': str("Not enough permission")}

            if roles_organizations:
                for role_name in roles_organizations:
                    base = DBSession.query(BaseGroup).filter_by(name=role_name, perspective_default=True).first()
                    if not base:
                        request.response.status = HTTPNotFound.code
                        return {'error': str("No such role in the system")}

                    group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                             subject_object_id=object_id,
                                                             subject_client_id=client_id).first()

                    client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()

                    userlogged = DBSession.query(User).filter_by(id=client.user_id).first()

                    permitted = False
                    if userlogged in group.users:
                        permitted = True
                    if not permitted:
                        for org in userlogged.organizations:
                            if org in group.organizations:
                                permitted = True
                                break

                    if permitted:
                        orgs = roles_organizations[role_name]
                        for orgid in orgs:
                            org = DBSession.query(Organization).filter_by(id=orgid).first()
                            if org:
                                if org in group.organizations:
                                    group.organizations.remove(org)
                    else:
                        request.response.status = HTTPForbidden.code
                        return {'error': str("Not enough permission")}

            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_status', renderer = 'json', request_method = 'GET')
def view_perspective_status(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective and not perspective.marked_for_deletion:
        if perspective.parent != parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such pair of dictionary/perspective in the system")}
        response['state_translation_gist_client_id'] = perspective.state_translation_gist_client_id
        response['state_translation_gist_object_id'] = perspective.state_translation_gist_object_id
        atom = DBSession.query(TranslationAtom).filter_by(parent_client_id=perspective.state_translation_gist_client_id,
                                                          parent_object_id=perspective.state_translation_gist_object_id,
                                                          locale_id=int(request.cookies['locale_id'])).first()
        response['status'] = atom.content
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_status', renderer = 'json', request_method = 'PUT', permission='edit')
def edit_perspective_status(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective and not perspective.marked_for_deletion:
        if perspective.parent != parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such pair of dictionary/perspective in the system")}
        if type(request.json_body) == str:
            req = json.loads(request.json_body)
        else:
            req = request.json_body
        perspective.state_translation_gist_client_id = req['state_translation_gist_client_id']
        perspective.state_translation_gist_object_id = req['state_translation_gist_object_id']
        atom = DBSession.query(TranslationAtom).filter_by(parent_client_id=req['state_translation_gist_client_id'],
                                                          parent_object_id=req['state_translation_gist_object_id'],
                                                          locale_id=int(request.cookies['locale_id'])).first()
        response['status'] = atom.content
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='field', renderer='json', request_method='GET')
def view_field(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    field = DBSession.query(Field).filter_by(client_id=client_id, object_id=object_id).first()
    field = Field()
    if field:
        return view_field_from_object(request=request, field=field)
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such field in the system")}


@view_config(route_name='create_field', renderer='json', request_method='POST')
def create_field(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        try:
            if type(request.json_body) == str:
                req = json.loads(request.json_body)
            else:
                req = request.json_body
        except AttributeError:
            request.response.status = HTTPBadRequest.code
            return {'error': "invalid json"}
        translation_gist_client_id = req['translation_gist_client_id']
        translation_gist_object_id = req['translation_gist_object_id']
        data_type_translation_gist_client_id = req['data_type_translation_gist_client_id']
        data_type_translation_gist_object_id = req['data_type_translation_gist_object_id']

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        field = Field(client_id=variables['auth'],
                                            data_type_translation_gist_client_id=data_type_translation_gist_client_id,
                                            data_type_translation_gist_object_id=data_type_translation_gist_object_id,
                                            translation_gist_client_id=translation_gist_client_id,
                                            translation_gist_object_id=translation_gist_object_id
                                            )

        if req.get('is_translatable', None):
            field.is_translatable = bool(req['is_translatable'])
        DBSession.add(field)
        DBSession.flush()
        request.response.status = HTTPOk.code
        return {'object_id': field.object_id,
                'client_id': field.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


def create_nested_field(field, perspective, client_id, upper_level, link_ids):
    field_object = DictionaryPerspectiveToField(client_id=client_id,
                                                perspective=perspective,
                                                field_client_id=field['client_id'],
                                                field_object_id=field['object_id'],
                                                upper_level=upper_level)
    if field.get('link'):
        # if field_object.field.data_type_translation_gist_client_id != link_ids['client_id'] or field_object.field.data_type_translation_gist_client_id != link_ids['client_id']:
        #     return {'error':'wrong type for link'}
        field_object.link_client_id = field['link']['client_id']
        field_object.link_object_id = field['link']['object_id']
    DBSession.flush()
    contains = field.get('contains', None)
    if contains:
        for subfield in contains:
            create_nested_field(subfield, perspective, client_id, upper_level=field_object, link_ids=link_ids)
    return


def view_nested_field(request, field, link_ids):
    field_object = field.field
    field_json = view_field_from_object(request=request, field=field_object)
    if 'error' in field_json:
        return field_json
    contains = list()
    for subfield in field.dictionaryperspectivetofield:
        subfield_json = view_nested_field(request, subfield, link_ids)
        if 'error' in subfield_json:
            return subfield_json
        contains.append(subfield_json)
    if contains:
        field_json['contains'] = contains

    if field_object.data_type_translation_gist_client_id == link_ids['client_id'] \
            and field_object.data_type_translation_gist_object_id == link_ids['object_id']:
        field_json['link'] = {'client_id': field.link_client_id, 'object_id': field.link_object_id}
    return field_json


@view_config(route_name='perspective_fields', renderer='json', request_method='GET')
def view_perspective_fields(request):
    response = list()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective and not perspective.marked_for_deletion:
        fields = DBSession.query(DictionaryPerspectiveToField)\
            .filter_by(perspective=perspective, upper_level=None)\
            .all()
        try:
            link_gist = DBSession.query(TranslationGist)\
                .join(TranslationAtom)\
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'link',
                        TranslationAtom.locale_id == 2).one()
            link_ids = {'client_id':link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            request.response.status = HTTPNotFound.code
            return {'error': str("Something wrong with the base")}
        for field in fields:
            response.append(view_nested_field(request, field, link_ids))
        request.response.status = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_fields', renderer='json', request_method='PUT')
def update_perspective_fields(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    variables = {'auth': authenticated_userid(request)}
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")

    if perspective and not perspective.marked_for_deletion:
        try:
            if type(request.json_body) == str:
                req = json.loads(request.json_body)
            else:
                req = request.json_body
        except AttributeError:
            request.response.status = HTTPBadRequest.code
            return {'error': "invalid json"}
        try:
            link_gist = DBSession.query(TranslationGist)\
                .join(TranslationAtom)\
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'link',
                        TranslationAtom.locale_id == 2).one()
            link_ids = {'client_id':link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            request.response.status = HTTPNotFound.code
            return {'error': str("Something wrong with the base")}
        fields = DBSession.query(DictionaryPerspectiveToField)\
            .filter_by(perspective=perspective)\
            .all()
        DBSession.flush()
        for field in fields:
            DBSession.delete(field)
        for field in req:
            create_nested_field(field=field,
                                perspective=perspective,
                                client_id=client.id,
                                upper_level=None,
                                link_ids=link_ids)

        request.response.status = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


# TODO: completely broken!
@view_config(route_name='lexical_entries_all', renderer='json', request_method='GET', permission='view')
def lexical_entries_all(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')

    sort_criterion = request.params.get('sort_by') or 'Translation'
    start_from = request.params.get('start_from') or 0
    count = request.params.get('count') or 200

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            # lexes = DBSession.query(LexicalEntry) \
            #     .options(joinedload('leveloneentity').joinedload('leveltwoentity').joinedload('publishleveltwoentity')) \
            #     .options(joinedload('leveloneentity').joinedload('publishleveloneentity')) \
            #     .options(joinedload('groupingentity').joinedload('publishgroupingentity')) \
            #     .options(joinedload('publishleveloneentity')) \
            #     .options(joinedload('publishleveltwoentity')) \
            #     .options(joinedload('publishgroupingentity')) \
            #     .filter(LexicalEntry.parent == parent) \
            #     .group_by(LexicalEntry) \
            #     .join(LevelOneEntity) \
            #     .order_by(func.min(case([(LevelOneEntity.entity_type != sort_criterion, 'яяяяяя')], else_=LevelOneEntity.content))) \
            #     .offset(start_from).limit(count)
            lexes = list()

            result = deque()
            for entry in lexes.all():
                result.append(entry.track(False))

            response['lexical_entries'] = list(result)

            request.response.status = HTTPOk.code
            return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='lexical_entries_all_count', renderer='json', request_method='GET', permission='view')
def lexical_entries_all_count(request): # tested
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')

    sort_criterion = request.params.get('sort_by') or 'Translation'
    start_from = request.params.get('start_from') or 0
    count = request.params.get('count') or 20

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            lexical_entries_count = DBSession.query(LexicalEntry)\
                .filter_by(marked_for_deletion=False, parent_client_id=parent.client_id, parent_object_id=parent.object_id).count()
            return {"count": lexical_entries_count}
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


# TODO: completely broken!
@view_config(route_name='lexical_entries_published', renderer='json', request_method='GET', permission='view')
@MEMOIZE
def lexical_entries_published(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')

    sort_criterion = request.params.get('sort_by') or 'Translation'
    start_from = request.params.get('start_from') or 0
    count = request.params.get('count') or 20

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            # NOTE: if lexical entry doesn't contain l1e it will not be shown here. But it seems to be ok.
            # NOTE: IMPORTANT: 'яяяяя' is a hack - something wrong with postgres collation if we use \uffff
            # lexes = DBSession.query(LexicalEntry) \
            #     .options(joinedload('leveloneentity').joinedload('leveltwoentity').joinedload('publishleveltwoentity')) \
            #     .options(joinedload('leveloneentity').joinedload('publishleveloneentity')) \
            #     .options(joinedload('groupingentity').joinedload('publishgroupingentity')) \
            #     .options(joinedload('publishleveloneentity')) \
            #     .options(joinedload('publishleveltwoentity')) \
            #     .options(joinedload('publishgroupingentity')) \
            #     .filter(LexicalEntry.parent == parent) \
            #     .group_by(LexicalEntry, LevelOneEntity.content) \
            #     .join(LevelOneEntity, and_(LevelOneEntity.parent_client_id == LexicalEntry.client_id,
            #                                LevelOneEntity.parent_object_id == LexicalEntry.object_id,
            #                                LevelOneEntity.marked_for_deletion == False)) \
            #     .join(PublishLevelOneEntity, and_(PublishLevelOneEntity.entity_client_id == LevelOneEntity.client_id,
            #                                       PublishLevelOneEntity.entity_object_id == LevelOneEntity.object_id,
            #                                       PublishLevelOneEntity.marked_for_deletion == False)) \
            #     .order_by(func.min(case([(LevelOneEntity.entity_type != sort_criterion, 'яяяяяя')], else_=LevelOneEntity.content))) \
            #     .offset(start_from).limit(count)
            lexes = list()

            result = deque()

            for entry in lexes.all():
                result.append(entry.track(True))
            response['lexical_entries'] = list(result)

            request.response.status = HTTPOk.code
            return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


# TODO: completely broken!
@view_config(route_name='lexical_entries_published_count', renderer='json', request_method='GET', permission='view')
def lexical_entries_published_count(request):
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            # lexical_entries_count = DBSession.query(LexicalEntry)\
            #     .filter_by(marked_for_deletion=False, parent_client_id=parent.client_id, parent_object_id=parent.object_id)\
            #     .outerjoin(PublishGroupingEntity)\
            #     .outerjoin(PublishLevelOneEntity)\
            #     .outerjoin(PublishLevelTwoEntity)\
            #     .filter(or_(PublishGroupingEntity.marked_for_deletion==False,
            #                 PublishLevelOneEntity.marked_for_deletion==False,
            #                 PublishLevelTwoEntity.marked_for_deletion==False,
            #                 ))\
            #     .group_by(LexicalEntry).count()
            lexical_entries_count = None

            return {"count": lexical_entries_count}
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


# TODO: completely broken!
@view_config(route_name='approve_entity', renderer='json', request_method='PATCH', permission='create')
def approve_entity(request):
    try:
        if type(request.json_body) == str:
            req = json.loads(request.json_body)
        else:
            req = request.json_body
        variables = {'auth': request.authenticated_userid}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        # {""}
        for entry in req['entities']:
            if entry['type'] == 'leveloneentity':
                # entity = DBSession.query(LevelOneEntity).\
                #     filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()
                entity = None
                if entity:
                    if not entity.publishleveloneentity:
                        # publishent = PublishLevelOneEntity(client_id=client.id, object_id=DBSession.query(PublishLevelOneEntity).filter_by(client_id=client.id).count() + 1,
                        #                                    entity=entity, parent=entity.parent)
                        # DBSession.add(publishent)
                        publishent = None
                    else:
                        for ent in entity.publishleveloneentity:
                            if ent.marked_for_deletion:
                                ent.marked_for_deletion = False
            elif entry['type'] == 'leveltwoentity':
                # entity = DBSession.query(LevelTwoEntity).\
                #     filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()
                entity = None
                if entity:
                    if not entity.publishleveltwoentity:
                        # publishent = PublishLevelTwoEntity(client_id=client.id, object_id=DBSession.query(PublishLevelTwoEntity).filter_by(client_id=client.id).count() + 1,
                        #                                    entity=entity, parent=entity.parent.parent)
                        # DBSession.add(publishent)
                        publishent = None
                    else:
                        for ent in entity.publishleveltwoentity:
                            if ent.marked_for_deletion:
                                ent.marked_for_deletion = False
            elif entry['type'] == 'groupingentity':
                # entity = DBSession.query(GroupingEntity).\
                #     filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()
                entity = None
                if entity:
                    if not entity.publishgroupingentity:
                        # publishent = PublishGroupingEntity(client_id=client.id, object_id=DBSession.query(PublishGroupingEntity).filter_by(client_id=client.id).count() + 1,
                        #                                    entity=entity, parent=entity.parent)
                        # DBSession.add(publishent)
                        publishent = None
                    else:
                        for ent in entity.publishgroupingentity:
                            if ent.marked_for_deletion:
                                ent.marked_for_deletion = False
            else:
                raise CommonException("Unacceptable type")

        request.response.status = HTTPOk.code
        return {}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


# TODO: completely broken!
@view_config(route_name='approve_entity', renderer='json', request_method='DELETE', permission='delete')
def disapprove_entity(request):
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
        for entry in req['entities']:
            if entry['type'] == 'leveloneentity':
                # entity = DBSession.query(LevelOneEntity).\
                #     filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()
                entity = None
                if entity:
                    for ent in entity.publishleveloneentity:
                        ent.marked_for_deletion = True
                        DBSession.flush()
                else:
                    log.debug("WARNING: NO ENTITY")
            elif entry['type'] == 'leveltwoentity':
                # entity = DBSession.query(LevelTwoEntity).\
                #     filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()
                entity = None
                if entity:
                    for ent in entity.publishleveltwoentity:
                        ent.marked_for_deletion = True
                        DBSession.flush()
            elif entry['type'] == 'groupingentity':
                # entity = DBSession.query(GroupingEntity).\
                #     filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()
                entity = None
                if entity:
                    for ent in entity.publishgroupingentity:
                        ent.marked_for_deletion = True
                        DBSession.flush()
            else:
                raise CommonException("Unacceptable type")

        request.response.status = HTTPOk.code
        return {}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


# TODO: completely broken!
@view_config(route_name='approve_all', renderer='json', request_method='PATCH', permission='create')
def approve_all(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    entities = []
    if parent:
        if not parent.marked_for_deletion:
            dictionary_client_id = parent.parent_client_id
            dictionary_object_id = parent.parent_object_id
            lexes = DBSession.query(LexicalEntry).filter_by(parent=parent).all()
            for lex in lexes:
                # levones = DBSession.query(LevelOneEntity).filter_by(parent=lex).all()
                levones = list()
                for levone in levones:
                    entities += [{'type': 'leveloneentity',
                                         'client_id': levone.client_id,
                                         'object_id': levone.object_id}]
                    for levtwo in levone.leveltwoentity:
                        entities += [{'type': 'leveltwoentity',
                                             'client_id':levtwo.client_id,
                                             'object_id':levtwo.object_id}]
                # groupents = DBSession.query(GroupingEntity).filter_by(parent=lex).all()
                groupents = list()
                for groupent in groupents:
                    entities += [{'type': 'groupingentity',
                                         'client_id': groupent.client_id,
                                         'object_id': groupent.object_id}]
            url = request.route_url('approve_entity',
                                    dictionary_client_id=dictionary_client_id,
                                    dictionary_object_id=dictionary_object_id,
                                    perspective_client_id=client_id,
                                    perspective_id=object_id)
            subreq = Request.blank(url)
            jsn = dict()
            jsn['entities'] = entities
            subreq.json = json.dumps(jsn)
            subreq.method = 'PATCH'
            headers = {'Cookie':request.headers['Cookie']}
            subreq.headers = headers
            request.invoke_subrequest(subreq)

            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='approve_all_outer', renderer='json', request_method='PATCH', permission='create')
def approve_outer(request):  # TODO: create test.
    from lingvodoc.scripts.approve import approve_all_outer
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    cli_id = request.matchdict.get('dictionary_client_id')
    obj_id = request.matchdict.get('dictionary_object_id')

    # convert_one(blob.real_storage_path,
    #             user.login,
    #             user.password.hash,
    #             parent_client_id,
    #             parent_object_id)

    # NOTE: doesn't work on Mac OS otherwise
    client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    user = client.user
    p = multiprocessing.Process(target=approve_all_outer, args=(user.login,
                                                          user.password.hash,
                                                          cli_id,
                                                          obj_id,
                                                          client_id,
                                                          object_id))
    log.debug("Conversion started")
    p.start()
    request.response.status = HTTPOk.code
    return {"status": "Your dictionary is being approved."
                      " Wait 5-15 minutes."}


@view_config(route_name='edit_dictionary', renderer='../templates/edit_dictionary.pt', request_method='GET')
def edit_dictionary_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    if user is None:
        response = Response()
        return HTTPFound(location=request.route_url('login'), headers=response.headers)

    dictionary_client_id = request.matchdict.get('dictionary_client_id')
    dictionary_object_id = request.matchdict.get('dictionary_object_id')
    perspective_client_id = request.matchdict.get('perspective_client_id')
    perspective_id = request.matchdict.get('perspective_id')

    variables = {'client_id': client_id, 'user': user, 'dictionary_client_id': dictionary_client_id,
                 'dictionary_object_id': dictionary_object_id, 'perspective_client_id': perspective_client_id,
                 'perspective_id': perspective_id}

    return render_to_response('../templates/edit_dictionary.pt', variables, request=request)

@view_config(route_name='view_dictionary', renderer='../templates/view_dictionary.pt', request_method='GET')
def view_dictionary_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)

    dictionary_client_id = request.matchdict.get('dictionary_client_id')
    dictionary_object_id = request.matchdict.get('dictionary_object_id')
    perspective_client_id = request.matchdict.get('perspective_client_id')
    perspective_id = request.matchdict.get('perspective_id')

    variables = {'user': user, 'dictionary_client_id': dictionary_client_id,
                 'dictionary_object_id': dictionary_object_id, 'perspective_client_id': perspective_client_id,
                 'perspective_id': perspective_id}

    return render_to_response('../templates/view_dictionary.pt', variables, request=request)


@view_config(route_name='publish_dictionary', renderer='../templates/publish_dictionary.pt', request_method='GET')
def publish_dictionary_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    if user is None:
        response = Response()
        return HTTPFound(location=request.route_url('login'), headers=response.headers)

    dictionary_client_id = request.matchdict.get('dictionary_client_id')
    dictionary_object_id = request.matchdict.get('dictionary_object_id')
    perspective_client_id = request.matchdict.get('perspective_client_id')
    perspective_id = request.matchdict.get('perspective_id')

    variables = {'client_id': client_id, 'user': user, 'dictionary_client_id': dictionary_client_id,
                 'dictionary_object_id': dictionary_object_id, 'perspective_client_id': perspective_client_id,
                 'perspective_id': perspective_id}

    return render_to_response('../templates/publish_dictionary.pt', variables, request=request)


# TODO: completely broken!
@view_config(route_name='create_entities_bulk', renderer='json', request_method='POST', permission='create')
def create_entities_bulk(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        response = dict()
        req = request.json_body

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        inserted_items = []
        for item in req:
            if item['level'] == 'leveloneentity':
                parent = DBSession.query(LexicalEntry).filter_by(client_id=item['parent_client_id'], object_id=item['parent_object_id']).first()
                # entity = LevelOneEntity(client_id=client.id,
                #                         object_id=DBSession.query(LevelOneEntity).filter_by(client_id=client.id).count() + 1,
                #                         entity_type=item['entity_type'],
                #                         locale_id=item['locale_id'],
                #                         additional_metadata=item.get('additional_metadata'),
                #                         parent=parent)
                entity = None
            elif item['level'] == 'groupingentity':
                parent = DBSession.query(LexicalEntry).filter_by(client_id=item['parent_client_id'], object_id=item['parent_object_id']).first()
                # entity = GroupingEntity(client_id=client.id,
                #                         object_id=DBSession.query(GroupingEntity).filter_by(client_id=client.id).count() + 1,
                #                         entity_type=item['entity_type'],
                #                         locale_id=item['locale_id'],
                #                         additional_metadata=item.get('additional_metadata'),
                #                         parent=parent)
                entity = None
            elif item['level'] == 'leveltwoentity':
                parent = DBSession.query(LevelOneEntity).filter_by(client_id=item['parent_client_id'], object_id=item['parent_object_id']).first()
                # entity = LevelTwoEntity(client_id=client.id,
                #                         object_id=DBSession.query(LevelTwoEntity).filter_by(client_id=client.id).count() + 1,
                #                         entity_type=item['entity_type'],
                #                         locale_id=item['locale_id'],
                #                         additional_metadata=item.get('additional_metadata'),
                #                         parent=parent)
                entity = None
            DBSession.add(entity)
            DBSession.flush()
            data_type = item.get('data_type')
            filename = item.get('filename')
            real_location = None
            url = None
            if data_type == 'sound' or data_type == 'markup':
                real_location, url = create_object(request, item['content'], entity, data_type, filename)

            if url and real_location:
                entity.content = url
                old_meta = entity.additional_metadata

                need_hash = True
                if old_meta:
                    new_meta=json.loads(old_meta)
                    if new_meta.get('hash'):
                        need_hash = False
                if need_hash:
                    hash = hashlib.sha224(base64.urlsafe_b64decode(req['content'])).hexdigest()
                    hash_dict = {'hash': hash}
                    if old_meta:
                        new_meta = json.loads(old_meta)
                        new_meta.update(hash_dict)
                    else:
                        new_meta = hash_dict
                    entity.additional_metadata = json.dumps(new_meta)
            else:
                entity.content = item['content']
            DBSession.add(entity)
            inserted_items.append({"client_id": entity.client_id, "object_id": entity.object_id})
        request.response.status = HTTPOk.code
        return inserted_items
    #    except KeyError as e:
    #        request.response.status = HTTPBadRequest.code
    #        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='perspective', renderer='json', request_method='PUT', permission='edit')
def edit_perspective(request):  # tested & in docs
    try:
        response = dict()
        client_id = request.matchdict.get('perspective_client_id')
        object_id = request.matchdict.get('perspective_id')
        client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        parent_client_id = request.matchdict.get('dictionary_client_id')
        parent_object_id = request.matchdict.get('dictionary_object_id')
        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such dictionary in the system")}

        perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if perspective:
            if not perspective.marked_for_deletion:
                if perspective.parent != parent:
                    request.response.status = HTTPNotFound.code
                    return {'error': str("No such pair of dictionary/perspective in the system")}
                req = request.json_body

                # TODO: Status 500 will be returned if arguments are invalid; add try/catch
                if 'translation_gist_client_id' in req:
                    perspective.translation_gist_client_id = req['translation_gist_client_id']
                if 'translation_gist_object_id' in req:
                    perspective.translation_gist_object_id = req['translation_gist_object_id']
                if 'parent_client_id' in req:
                    perspective.parent_client_id = req['parent_client_id']
                if 'parent_object_id' in req:
                    perspective.parent_object_id = req['parent_object_id']

                is_template = req.get('is_template')
                if is_template is not None:
                    perspective.is_template = is_template
                request.response.status = HTTPOk.code
                return response
        else:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such perspective in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}


@view_config(route_name='perspective', renderer='json', request_method='DELETE', permission='delete')
def delete_perspective(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'error': str("No such pair of dictionary/perspective in the system")}
            perspective.marked_for_deletion = True
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}