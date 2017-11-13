__author__ = 'alexander'

from collections import deque
import base64
import datetime
import hashlib
import json
import logging
import multiprocessing

from sqlalchemy.orm.attributes import flag_modified

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPForbidden,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from sqlalchemy.sql.expression import case, true, false

from sqlalchemy.sql.functions import coalesce

from sqlalchemy.orm import aliased

from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_
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
    Entity,
    PublishingEntity,
    Group,
    LexicalEntry,
    Organization,
    User,
    TranslationAtom,
    TranslationGist,
    Field,
    DictionaryPerspectiveToField,
    UserBlobs,
    ObjectTOC
)
from lingvodoc.views.v2.utils import (
    cache_clients,
    create_object,
    get_user_by_client_id,
    user_counter,
    view_perspective_from_object,
    view_field_from_object,
    check_client_id
)
from lingvodoc.views.v2.utils import (
    add_user_to_group,
    fulfill_permissions_on_perspectives,
    FakeObject
)
from lingvodoc.views.v2.delete import real_delete_perspective
from pdb import set_trace

log = logging.getLogger(__name__)


@view_config(route_name='permissions_on_perspectives', renderer='json', request_method='GET')
def permissions_on_perspectives(request):

    client_id = authenticated_userid(request)

    subreq = Request.blank('/translation_service_search')
    subreq.method = 'POST'
    subreq.headers = request.headers
    subreq.json = {'searchstring': 'Published'}
    headers = dict()
    if request.headers.get('Cookie'):
        headers = {'Cookie': request.headers['Cookie']}
    subreq.headers = headers
    resp = request.invoke_subrequest(subreq)

    if 'error' not in resp.json:
        published_gist_object_id, published_gist_client_id = resp.json['object_id'], resp.json['client_id']
    else:
        raise KeyError("Something wrong with the base", resp.json['error'])

    subreq = Request.blank('/translation_service_search')
    subreq.method = 'POST'
    subreq.headers = request.headers
    subreq.json = {'searchstring': 'Limited access'}  # todo: fix
    headers = dict()
    if request.headers.get('Cookie'):
        headers = {'Cookie': request.headers['Cookie']}
    subreq.headers = headers
    resp = request.invoke_subrequest(subreq)

    if 'error' not in resp.json:
        limited_gist_object_id, limited_gist_client_id = resp.json['object_id'], resp.json['client_id']
    else:
        raise KeyError("Something wrong with the base", resp.json['error'])

    intermediate = dict()

    limited = DBSession.query(DictionaryPerspective.client_id, DictionaryPerspective.object_id, ).filter(
        and_(DictionaryPerspective.state_translation_gist_client_id == limited_gist_client_id,
             DictionaryPerspective.state_translation_gist_object_id == limited_gist_object_id)
    )

    limited_perms = [("limited", True), ("read", False), ("write", False), ("publish", False)]
    for pers in limited.all():
        fulfill_permissions_on_perspectives(intermediate, pers, limited_perms)

    published = DBSession.query(DictionaryPerspective.client_id, DictionaryPerspective.object_id, ).filter(
        and_(DictionaryPerspective.state_translation_gist_client_id == published_gist_client_id,
             DictionaryPerspective.state_translation_gist_object_id == published_gist_object_id)
    )
    published_perms = [("read", True), ("write", False), ("publish", False)]
    for pers in published.all():
        fulfill_permissions_on_perspectives(intermediate, pers, published_perms)

    if not client_id:
        return intermediate

    user_id = DBSession.query(Client).filter(client_id == Client.id).first().user_id
    editor_basegroup = DBSession.query(BaseGroup).filter(and_(BaseGroup.subject == "lexical_entries_and_entities", BaseGroup.action == "create")).first()
    editable_perspectives = DBSession.query(Group).join(Group.users).filter(and_(User.id == user_id, Group.base_group_id == editor_basegroup.id)).all()
    pers = FakeObject()
    editable_perms = [("write", True)]
    for i in editable_perspectives:
        pers.client_id = i.subject_client_id
        pers.object_id = i.subject_object_id
        fulfill_permissions_on_perspectives(intermediate, pers, editable_perms)

    reader_basegroup = DBSession.query(BaseGroup).filter(and_(BaseGroup.subject == "approve_entities", BaseGroup.action == "view")).first()
    readable_perspectives = DBSession.query(Group).join(Group.users).filter(and_(User.id == user_id, Group.base_group_id == reader_basegroup.id)).all()
    pers = FakeObject()
    readable_perms = [("read", True)]
    for i in readable_perspectives:
        pers.client_id = i.subject_client_id
        pers.object_id = i.subject_object_id
        fulfill_permissions_on_perspectives(intermediate, pers, readable_perms)

    publisher_basegroup = DBSession.query(BaseGroup).filter(and_(BaseGroup.subject == "approve_entities", BaseGroup.action == "create")).first()
    approvable_perspectives = DBSession.query(Group).join(Group.users).filter(and_(User.id == user_id, Group.base_group_id == publisher_basegroup.id)).all()
    pers = FakeObject()
    approvable_perms = [("publish", True)]
    for i in approvable_perspectives:
        pers.client_id = i.subject_client_id
        pers.object_id = i.subject_object_id
        fulfill_permissions_on_perspectives(intermediate, pers, approvable_perms)

    return intermediate


@view_config(route_name='all_perspectives', renderer='json', request_method='GET')
def perspectives_list(request):  # tested
    response = list()
    is_template = None
    try:
        is_template = request.GET.get('is_template')
    except:
        pass

    published = request.params.get('published', None)
    visible = request.params.get('visible', None)


    subreq = Request.blank('/translation_service_search')
    subreq.method = 'POST'
    subreq.headers = request.headers
    subreq.json = {'searchstring': 'Published'}
    headers = {'Cookie': request.headers['Cookie']}
    subreq.headers = headers
    resp = request.invoke_subrequest(subreq)
    if 'error' not in resp.json:
        state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
            'client_id']
        published_gist = (state_translation_gist_client_id, state_translation_gist_object_id)
    else:
        raise KeyError("Something wrong with the base", resp.json['error'])
    subreq = Request.blank('/translation_service_search')
    subreq.method = 'POST'
    subreq.headers = request.headers
    subreq.json = {'searchstring': 'Limited access'}
    headers = {'Cookie': request.headers['Cookie']}
    subreq.headers = headers
    resp = request.invoke_subrequest(subreq)
    if 'error' not in resp.json:
        state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
            'client_id']
        limited_gist = (state_translation_gist_client_id, state_translation_gist_object_id)
    else:
        raise KeyError("Something wrong with the base", resp.json['error'])

    atom_perspective_name_alias = aliased(TranslationAtom, name="PerspectiveName")
    atom_perspective_name_fallback_alias = aliased(TranslationAtom, name="PerspectiveNameFallback")
    persps = DBSession.query(DictionaryPerspective,
                             TranslationAtom,
                             coalesce(atom_perspective_name_alias.content,
                                      atom_perspective_name_fallback_alias.content,
                                      "No translation for your locale available").label("Translation")
                             ).filter(DictionaryPerspective.marked_for_deletion == False)
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

    visible_persps = None
    if visible:
        user = Client.get_user_by_client_id(authenticated_userid(request))
        visible_persps = [(-1, -1)] #hack to avoid empty in_
        if user:
            for group in user.groups:
                if group.base_group_id == 21 or group.base_group_id == 22:
                    visible_persps.append((group.subject_client_id, group.subject_object_id))

        persps = persps.filter(or_(and_(DictionaryPerspective.state_translation_gist_client_id == published_gist[0],
                                        DictionaryPerspective.state_translation_gist_object_id == published_gist[1]),
                                   tuple_(DictionaryPerspective.client_id, DictionaryPerspective.object_id).in_(visible_persps)))
    else:
        if published:
            persps = persps.filter(or_(and_(DictionaryPerspective.state_translation_gist_client_id == published_gist[0],
                                            DictionaryPerspective.state_translation_gist_object_id == published_gist[1]),
                                       and_(DictionaryPerspective.state_translation_gist_client_id == limited_gist[0],
                                            DictionaryPerspective.state_translation_gist_object_id == limited_gist[1])))


        # if user:
        #     visible_persps = DBSession.query(user)

    persps = persps.join(TranslationAtom,
                         and_(
                             TranslationAtom.parent_client_id == DictionaryPerspective.state_translation_gist_client_id,
                             TranslationAtom.parent_object_id == DictionaryPerspective.state_translation_gist_object_id)).filter(
        TranslationAtom.locale_id == int(request.cookies['locale_id'])).join(
        atom_perspective_name_alias, and_(
            atom_perspective_name_alias.parent_client_id == DictionaryPerspective.translation_gist_client_id,
            atom_perspective_name_alias.parent_object_id == DictionaryPerspective.translation_gist_object_id,
            atom_perspective_name_alias.locale_id == int(request.cookies['locale_id'])), isouter=True).join(
        atom_perspective_name_fallback_alias, and_(
            atom_perspective_name_fallback_alias.parent_client_id == DictionaryPerspective.translation_gist_client_id,
            atom_perspective_name_fallback_alias.parent_object_id == DictionaryPerspective.translation_gist_object_id,
            atom_perspective_name_fallback_alias.locale_id == 2), isouter=True)

    blobs = DBSession.query(UserBlobs).filter(UserBlobs.data_type == 'pdf').all()
    blobs_fast_dict = {}
    for blob in blobs:
        if blob.client_id not in blobs_fast_dict:
            blobs_fast_dict[blob.client_id] = dict()
        blobs_fast_dict[blob.client_id][blob.object_id] = {'name': blob.name,
                                                           'content': blob.content,
                                                           'data_type': blob.data_type,
                                                           'client_id': blob.client_id,
                                                           'object_id': blob.object_id,
                                                           'created_at': blob.created_at}

    row2dict = lambda r: {c.name: getattr(r, c.name) for c in r.__table__.columns}
    perspectives = []
    for perspective in persps.all():
        resp = row2dict(perspective.DictionaryPerspective)
        resp['status'] = perspective.TranslationAtom.content or "Unknown state"
        if perspective.DictionaryPerspective.additional_metadata:
            resp['additional_metadata'] = list(perspective.DictionaryPerspective.additional_metadata.keys())
        else:
            resp['additional_metadata'] = []
        resp['translation'] = perspective.Translation or "Unknown perspective name"

        if perspective.DictionaryPerspective.additional_metadata:
            if 'location' in perspective.DictionaryPerspective.additional_metadata:
                resp['location'] = perspective.DictionaryPerspective.additional_metadata['location']
            if 'info' in perspective.DictionaryPerspective.additional_metadata:
                resp['info'] = perspective.DictionaryPerspective.additional_metadata['info']
                info_list = resp['info'].get('content')
                for info in info_list:
                    blob_client_id, blob_object_id = info['info']['content']['client_id'], info['info']['content']['object_id']
                    if blob_client_id in blobs_fast_dict and blob_object_id in blobs_fast_dict[blob_client_id]:
                        resp['info']['content'] = blobs_fast_dict[blob_client_id][blob_object_id]
        perspectives.append(resp)

    response = perspectives
    request.response.status = HTTPOk.code

    return response


@view_config(route_name='all_perspectives_meta', renderer='json', request_method='GET')
def perspectives_meta_list(request):  # tested
    response = list()
    is_template = None
    try:
        is_template = request.GET.get('is_template')
    except:
        pass
    state_translation_gist_client_id = request.params.get('state_translation_gist_client_id', None)
    state_translation_gist_object_id = request.params.get('state_translation_gist_object_id', None)
    persps = DBSession.query(DictionaryPerspective).filter(DictionaryPerspective.marked_for_deletion == False,
                                                           DictionaryPerspective.additional_metadata != {})
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
        persps = persps.filter(
            DictionaryPerspective.state_translation_gist_client_id == state_translation_gist_client_id,
            DictionaryPerspective.state_translation_gist_object_id == state_translation_gist_object_id)
    perspectives = []
    for perspective in persps:
        # resp = view_perspective_from_object(request, perspective)
        resp = perspective.additional_metadata
        if resp:
            resp.update({'client_id': perspective.client_id, 'object_id': perspective.object_id})
        else:
            resp = {'client_id': perspective.client_id, 'object_id': perspective.object_id}
        if 'error' not in resp:
            perspectives.append(resp)
    response = perspectives
    request.response.status = HTTPOk.code

    return response


@view_config(route_name='perspective', renderer='json', request_method='GET')
@view_config(route_name='perspective_outside', renderer='json', request_method='GET')
def view_perspective(request):  # tested & in docs
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = None
    if parent_client_id and parent_object_id:
        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such dictionary in the system %s %s %s %s") % (
            client_id, object_id, parent_client_id, parent_object_id)}

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
        object_id = request.matchdict.get('perspective_object_id')
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
                            old_meta.update(hash_dict)
                        else:
                            old_meta = hash_dict
                        l1e.additional_metadata = old_meta
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
                            old_meta.update(hash_dict)
                        else:
                            old_meta = hash_dict
                        l2e.additional_metadata = old_meta
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
                                 perspective_object_id=perspective.object_id)
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
    object_id = request.matchdict.get('perspective_object_id')
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
                old_meta = perspective.additional_metadata
                new_meta = req
                old_meta.update(new_meta)
                flag_modified(perspective, 'additional_metadata')
            else:
                perspective.additional_metadata = req
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_meta', renderer='json', request_method='DELETE', permission='edit')
def delete_perspective_meta(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
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
            old_meta = perspective.additional_metadata
            new_meta = req
            for entry in new_meta:
                if entry in old_meta:
                    del old_meta[entry]
            perspective.additional_metadata = old_meta
            flag_modified(perspective, 'additional_metadata')
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_meta', renderer='json', request_method='POST')
def view_perspective_meta(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
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

        old_meta = perspective.additional_metadata
        # import pdb
        # pdb.set_trace()
        try:
            req = request.json_body
        except AttributeError:
            request.response.status = HTTPBadRequest.code
            return {'error': "invalid json"}
        except ValueError:
            request.response.status = HTTPBadRequest.code
            return {'error': "invalid json"}

        if req:
            new_meta = dict()
            for key in req:
                if old_meta.get(key):
                    new_meta[key] = old_meta[key]
                else:
                    request.response.status = HTTPNotFound.code
                    return {'error': str("No such key in metadata:, %s" % key)}

            response = new_meta
            request.response.status = HTTPOk.code
            return response
        else:
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
    object_id = request.matchdict.get('perspective_object_id')
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
    object_id = request.matchdict.get('perspective_object_id')
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
        .options(joinedload('lexicalentry').joinedload('leveloneentity').joinedload('leveltwoentity').joinedload(
        'publishleveltwoentity')) \
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
                                     perspective_object_id=perspective.object_id
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
                result = user_counter(lex.track(True, int(request.cookies.get('locale_id') or 2)), result, starting_date, ending_date, types, clients_to_users_dict)

            response['count'] = result
            request.response.status = HTTPOk.code
            return response

    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='create_perspective', renderer='json', request_method='POST', permission='create')
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
        object_id = req.get('object_id', None)
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']):
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}

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

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': 'WiP'}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)

        if 'error' not in resp.json:
            state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                'client_id']
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])

        perspective = DictionaryPerspective(client_id=client_id,
                                            object_id=object_id,
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
        if not object_id:
            for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
                new_group = Group(parent=base,
                                  subject_object_id=perspective.object_id, subject_client_id=perspective.client_id)
                add_user_to_group(user, new_group)
                add_user_to_group(owner, new_group)
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


@view_config(route_name='complex_create', renderer='json', request_method='POST', permission='create')
def complex_create(request):
    try:
        parent_client_id = request.matchdict.get('dictionary_client_id')
        parent_object_id = request.matchdict.get('dictionary_object_id')
        result = list()
        try:
            if type(request.json_body) == str:
                req = json.loads(request.json_body)
            else:
                req = request.json_body
        except AttributeError:
            request.response.status = HTTPBadRequest.code
            return {'error': "invalid json"}
        fake_ids = dict()
        for perspective_json in req:
            path = request.route_url('create_perspective',
                                     dictionary_client_id=parent_client_id,
                                     dictionary_object_id=parent_object_id)
            subreq = Request.blank(path)
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = perspective_json
            headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
            perspective = resp.json
            result.append({'object_id': perspective['object_id'],
                           'client_id': perspective['client_id']})
            perspective_json['client_id'] = perspective['client_id']
            perspective_json['object_id'] = perspective['object_id']
            fake_ids[perspective_json['fake_id']] = perspective
        # set_trace()
        for perspective_json in req:
            path = request.route_url('perspective_fields',
                                     dictionary_client_id=parent_client_id,
                                     dictionary_object_id=parent_object_id,
                                     perspective_client_id=perspective_json['client_id'],
                                     perspective_object_id=perspective_json['object_id'])
            subreq = Request.blank(path)
            subreq.method = 'PUT'
            subreq.headers = request.headers
            for field in perspective_json['fields']:
                if field.get('link') and field['link'].get('fake_id'):
                    field['link'] = fake_ids[field['link']['fake_id']]
            subreq.json = perspective_json['fields']
            headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)
        return result
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
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    published = request.params.get('published', None)
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such dictionary in the system")}
    perspectives = list()

    if published:
        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': 'Published'}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        if 'error' not in resp.json:
            state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                'client_id']
            published = (state_translation_gist_client_id, state_translation_gist_object_id)
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])
        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': 'Limited access'}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        if 'error' not in resp.json:
            state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                'client_id']
            limited = (state_translation_gist_client_id, state_translation_gist_object_id)
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])

    for perspective in parent.dictionaryperspective:
        path = request.route_url('perspective',
                                 dictionary_client_id=parent_client_id,
                                 dictionary_object_id=parent_object_id,
                                 perspective_client_id=perspective.client_id,
                                 perspective_object_id=perspective.object_id)
        subreq = Request.blank(path)
        subreq.method = 'GET'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if published and not ((
                                              published[0] == resp.json.get('state_translation_gist_client_id') and
                                              published[1] == resp.json.get('state_translation_gist_object_id'))
                              or (
                            limited[0] == resp.json.get('state_translation_gist_client_id') and
                            limited[1] == resp.json.get('state_translation_gist_object_id'))
                              ):
            continue
        if 'error' not in resp.json:
            perspectives += [resp.json]
    request.response.status = HTTPOk.code
    return perspectives


@view_config(route_name='perspective_roles', renderer='json', request_method='GET')
def view_perspective_roles(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
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
                if not group:
                    print(base.name)
                    continue
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


@view_config(route_name='perspective_roles', renderer='json', request_method='POST', permission='create')
def edit_perspective_roles(request):
    DBSession.execute("LOCK TABLE user_to_group_association IN EXCLUSIVE MODE;")
    DBSession.execute("LOCK TABLE organization_to_group_association IN EXCLUSIVE MODE;")
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    parent_client_id = request.matchdict.get('client_id')
    parent_object_id = request.matchdict.get('object_id')

    url = request.route_url('perspective_roles',
                            client_id=parent_client_id,
                            object_id=parent_object_id,
                            perspective_client_id=client_id,
                            perspective_object_id=object_id)
    subreq = Request.blank(url)
    subreq.method = 'GET'
    headers = {'Cookie': request.headers['Cookie']}
    subreq.headers = headers
    previous = request.invoke_subrequest(subreq).json_body

    if type(request.json_body) == str:
        req = json.loads(request.json_body)
    else:
        req = request.json_body

    for role_name in req['roles_users']:
        remove_list = list()
        for user in req['roles_users'][role_name]:
            if user in previous['roles_users'][role_name]:
                previous['roles_users'][role_name].remove(user)
                remove_list.append(user)
        for user in remove_list:
            req['roles_users'][role_name].remove(user)

    for role_name in req['roles_organizations']:
        remove_list = list()
        for user in req['roles_organizations'][role_name]:
            if user in previous['roles_organizations'][role_name]:
                previous['roles_organizations'][role_name].remove(user)
                req['roles_organizations'][role_name].remove(user)
        for user in remove_list:
            req['roles_users'][role_name].remove(user)

    delete_flag = False

    for role_name in previous['roles_users']:
        if previous['roles_users'][role_name]:
            delete_flag = True
            break

    for role_name in previous['roles_organizations']:
        if previous['roles_organizations'][role_name]:
            delete_flag = True
            break

    if delete_flag:
        subreq = Request.blank(url)
        subreq.json = previous
        subreq.method = 'PATCH'
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        request.invoke_subrequest(subreq)

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
                if not permitted:
                    override_group = DBSession.query(Group).filter_by(base_group_id=base.id, subject_override=True).first()
                    if userlogged in override_group.users:
                        permitted = True

                if permitted:
                    users = roles_users[role_name]
                    for userid in users:
                        user = DBSession.query(User).filter_by(id=userid).first()
                        if user:
                            if user not in group.users:
                                group.users.append(user)
                else:
                    if roles_users[role_name]:
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
                if not permitted:
                    override_group = DBSession.query(Group).filter_by(base_group_id=base.id, subject_override=True).first()
                    if userlogged in override_group.users:
                        permitted = True

                if permitted:
                    orgs = roles_organizations[role_name]
                    for orgid in orgs:
                        org = DBSession.query(Organization).filter_by(id=orgid).first()
                        if org:
                            if org not in group.organizations:
                                group.organizations.append(org)
                else:
                    if roles_organizations[role_name]:
                        request.response.status = HTTPForbidden.code
                        return {'error': str("Not enough permission")}

        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_roles', renderer='json', request_method='PATCH', permission='delete')
def delete_perspective_roles(request):  # TODO: test
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
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
                    if not permitted:
                        override_group = DBSession.query(Group).filter_by(base_group_id=base.id, subject_override=True).first()
                        if userlogged in override_group.users:
                            permitted = True

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
                        if roles_users[role_name]:
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
                    if not permitted:
                        override_group = DBSession.query(Group).filter_by(base_group_id=base.id, subject_override=True).first()
                        if userlogged in override_group.users:
                            permitted = True

                    if permitted:
                        orgs = roles_organizations[role_name]
                        for orgid in orgs:
                            org = DBSession.query(Organization).filter_by(id=orgid).first()
                            if org:
                                if org in group.organizations:
                                    group.organizations.remove(org)
                    else:
                        if roles_organizations[role_name]:
                            request.response.status = HTTPForbidden.code
                            return {'error': str("Not enough permission")}

            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='perspective_status', renderer='json', request_method='GET')
def view_perspective_status(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
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


@view_config(route_name='perspective_status', renderer='json', request_method='PUT', permission='edit')
def edit_perspective_status(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
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
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    field = DBSession.query(Field).filter_by(client_id=client_id, object_id=object_id).first()
    if field:
        return view_field_from_object(request=request, field=field)
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such field in the system")}


@view_config(route_name='fields', renderer='json', request_method='GET')
def all_fields(request):
    fields = DBSession.query(Field).filter_by(marked_for_deletion=False).all() #todo: think about desktop and sync
    response = list()
    for field in fields:
        response.append(view_field_from_object(request=request, field=field))
    request.response.code = HTTPOk.code
    return response


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
            print('invalid json')
            request.response.status = HTTPBadRequest.code
            return {'error': "invalid json"}

        translation_gist_client_id = req['translation_gist_client_id']
        translation_gist_object_id = req['translation_gist_object_id']
        data_type_translation_gist_client_id = req['data_type_translation_gist_client_id']
        data_type_translation_gist_object_id = req['data_type_translation_gist_object_id']
        object_id = req.get('object_id', None)
        marked_for_deletion = req.get('object_id', None)

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            print('invalid client id')
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']):
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}

        field = Field(client_id=client_id,
                      object_id=object_id,
                      data_type_translation_gist_client_id=data_type_translation_gist_client_id,
                      data_type_translation_gist_object_id=data_type_translation_gist_object_id,
                      translation_gist_client_id=translation_gist_client_id,
                      translation_gist_object_id=translation_gist_object_id,
                      marked_for_deletion=marked_for_deletion
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


def create_nested_field(field, perspective, client_id, upper_level, link_ids, position):
    field_object = DictionaryPerspectiveToField(client_id=client_id,
                                                parent=perspective,
                                                field_client_id=field['client_id'],
                                                field_object_id=field['object_id'],
                                                upper_level=upper_level,
                                                position=position)
    if field.get('link'):
        # if field_object.field.data_type_translation_gist_client_id != link_ids['client_id'] or field_object.field.data_type_translation_gist_client_id != link_ids['client_id']:
        #     return {'error':'wrong type for link'}
        field_object.link_client_id = field['link']['client_id']
        field_object.link_object_id = field['link']['object_id']
    DBSession.flush()
    contains = field.get('contains', None)
    if contains:
        inner_position = 1
        for subfield in contains:
            create_nested_field(subfield,
                                perspective,
                                client_id,
                                upper_level=field_object,
                                link_ids=link_ids,
                                position=inner_position)
            inner_position += 1
    return


def view_nested_field(request, field, link_ids):
    row2dict = lambda r: {c.name: getattr(r, c.name) for c in r.__table__.columns}
    field_object = field.field
    field_json = view_field_from_object(request=request, field=field_object)
    field_json['position'] = field.position
    if 'error' in field_json:
        return field_json
    contains = list()
    for subfield in field.dictionaryperspectivetofield:  # todo: order subfields
        if not subfield.marked_for_deletion:
            subfield_json = view_nested_field(request, subfield, link_ids)
            if 'error' in subfield_json:
                return subfield_json
            contains.append(subfield_json)
    if contains:
        field_json['contains'] = contains
    if field_object.data_type_translation_gist_client_id == link_ids['client_id'] \
            and field_object.data_type_translation_gist_object_id == link_ids['object_id']:
        field_json['link'] = {'client_id': field.link_client_id, 'object_id': field.link_object_id}
    upd_json = row2dict(field)
    field_json.update(upd_json)
    return field_json


@view_config(route_name='perspective_fields', renderer='json', request_method='GET')
def view_perspective_fields(request):
    response = list()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective and not perspective.marked_for_deletion:
        fields = DBSession.query(DictionaryPerspectiveToField) \
            .filter_by(parent=perspective, upper_level=None, marked_for_deletion=False) \
            .order_by(DictionaryPerspectiveToField.position) \
            .all()
        try:
            link_gist = DBSession.query(TranslationGist) \
                .join(TranslationAtom) \
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'Link',
                        TranslationAtom.locale_id == 2).one()
            link_ids = {'client_id': link_gist.client_id, 'object_id': link_gist.object_id}
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
    object_id = request.matchdict.get('perspective_object_id')
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
            link_gist = DBSession.query(TranslationGist) \
                .join(TranslationAtom) \
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'Link',
                        TranslationAtom.locale_id == 2).one()
            link_ids = {'client_id': link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            request.response.status = HTTPNotFound.code
            return {'error': str("Something wrong with the base")}
        fields = DBSession.query(DictionaryPerspectiveToField) \
            .filter_by(parent=perspective) \
            .all()
        DBSession.flush()
        for field in fields:
            # DBSession.delete(field)
            field.marked_for_deletion = True
        position = 1
        for field in req:
            create_nested_field(field=field,
                                perspective=perspective,
                                client_id=client.id,
                                upper_level=None,
                                link_ids=link_ids, position=position)
            position += 1
        request.response.status = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='all_perspective_authors', renderer='json', request_method='GET')
def all_perspective_authors(request):
    response = list()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent and not parent.marked_for_deletion:
        authors = DBSession.query(User).join(User.clients).join(Entity, Entity.client_id == Client.id) \
            .join(Entity.parent).join(Entity.publishingentity) \
            .filter(LexicalEntry.parent_client_id == parent.client_id,
                    LexicalEntry.parent_object_id == parent.object_id,
                    LexicalEntry.marked_for_deletion == False,
                    Entity.marked_for_deletion == False)
        response = [o.id for o in authors.all()]
        request.response.status = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='all_perspective_clients', renderer='json', request_method='GET')
def all_perspective_clients(request):
    response = list()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent and not parent.marked_for_deletion:
        clients = DBSession.query(Client).join(Entity, Entity.client_id == Client.id) \
            .join(Entity.parent).join(Entity.publishingentity) \
            .filter(LexicalEntry.parent_client_id == parent.client_id,
                    LexicalEntry.parent_object_id == parent.object_id,
                    LexicalEntry.marked_for_deletion == False,
                    Entity.marked_for_deletion == False)
        response = [o.id for o in clients.all()]
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
    object_id = request.matchdict.get('perspective_object_id')
    authors = request.params.getall('authors')
    clients = request.params.getall('clients')
    start_date = request.params.get('start_date', )
    if start_date:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = request.params.get('end_date')
    if end_date:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    field_client_id = int(request.params.get('field_client_id', 66))
    field_object_id = int(request.params.get('field_object_id', 10))
    start_from = request.params.get('start_from') or 0
    count = request.params.get('count') or 20

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent and not parent.marked_for_deletion:

        lexes = DBSession.query(LexicalEntry).join(LexicalEntry.entity).join(Entity.publishingentity) \
            .filter(LexicalEntry.parent == parent, LexicalEntry.marked_for_deletion == False,
                    Entity.marked_for_deletion == False)
        if authors or clients:
            lexes = lexes.join(Client, Entity.client_id == Client.id)
        if authors:
            lexes = lexes.join(Client.user).filter(User.id.in_(authors))
        if clients:
            lexes = lexes.filter(Client.id.in_(clients))
        if start_date:
            lexes = lexes.filter(Entity.created_at >= start_date)
        if end_date:
            lexes = lexes.filter(Entity.created_at <= end_date)  # todo: check if field=field ever works
        lexes = lexes \
            .order_by(func.min(case(
            [(or_(Entity.field_client_id != field_client_id,
                  Entity.field_object_id != field_object_id),
              'яяяяяя')],
            else_=Entity.content))) \
            .group_by(LexicalEntry) \
            .offset(start_from).limit(count)

        result = deque()
        # print([o.client_id for o in lexes.all()])
        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes.all()]

        result = LexicalEntry.track_multiple(lexes_composite_list, int(request.cookies.get('locale_id') or 2), publish=None, accept=True)

        response = list(result)

        request.response.status = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='lexical_entries_all_count', renderer='json', request_method='GET')
def lexical_entries_all_count(request):  # tested
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    authors = request.params.getall('authors')
    clients = request.params.getall('clients')
    start_date = request.params.get('start_date', )
    if start_date:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = request.params.get('end_date')
    if end_date:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent and not parent.marked_for_deletion:
        lexical_entries_count = DBSession.query(LexicalEntry).join(LexicalEntry.entity) \
            .join(Entity.publishingentity) \
            .filter(LexicalEntry.parent == parent, LexicalEntry.marked_for_deletion == False,
                    Entity.marked_for_deletion == False)
        if authors or clients or start_date or end_date:
            lexical_entries_count = lexical_entries_count.join(LexicalEntry.entity)
        if authors or clients:
            lexical_entries_count = lexical_entries_count.join(Client, Entity.client_id == Client.id)
        if authors:
            lexical_entries_count = lexical_entries_count.join(Client.user).filter(User.id.in_(authors))
        if clients:
            lexical_entries_count = lexical_entries_count.filter(Client.id.in_(clients))
        if start_date:
            lexical_entries_count = lexical_entries_count.filter(Entity.created_at >= start_date)
        if end_date:
            lexical_entries_count = lexical_entries_count.filter(Entity.created_at <= end_date)
        lexical_entries_count = lexical_entries_count.group_by(LexicalEntry).count()
        return {"count": lexical_entries_count}
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


# TODO: completely broken!
@view_config(route_name='lexical_entries_published', renderer='json', request_method='GET')
def lexical_entries_published(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    authors = request.params.getall('authors')
    clients = request.params.getall('clients')
    start_date = request.params.get('start_date', )
    if start_date:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = request.params.get('end_date')
    if end_date:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    field_client_id = int(request.params.get('field_client_id', 66))
    field_object_id = int(request.params.get('field_object_id', 10))
    start_from = request.params.get('start_from') or 0
    count = request.params.get('count') or 20
    preview_mode = False

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent and not parent.marked_for_deletion:

        if (parent.state == 'Limited access' or parent.parent.state == 'Limited access') and "view:lexical_entries_and_entities:" + client_id + ":" + object_id not in request.effective_principals:
            log.debug("PREVIEW MODE")
            preview_mode = True
        lexes = DBSession.query(LexicalEntry) \
            .join(LexicalEntry.entity).join(Entity.publishingentity) \
            .filter(LexicalEntry.parent == parent, PublishingEntity.published == True,
                    Entity.marked_for_deletion == False, LexicalEntry.marked_for_deletion == False)
        if authors or clients:
            lexes = lexes.join(Client, Entity.client_id == Client.id)
        if authors:
            lexes = lexes.join(Client.user).filter(User.id.in_(authors))
        if clients:
            lexes = lexes.filter(Client.id.in_(clients))
        if start_date:
            lexes = lexes.filter(Entity.created_at >= start_date)
        if end_date:
            lexes = lexes.filter(Entity.created_at <= end_date)
        lexes = lexes.group_by(LexicalEntry) \
            .order_by(func.min(case(
            [(or_(Entity.field_client_id != field_client_id,
                  Entity.field_object_id != field_object_id),
              'яяяяяя')],
            else_=Entity.content))) \
            .group_by(LexicalEntry) \
            .offset(start_from).limit(count)

        # lexes = list()

        result = deque()

        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes.all()]

        result = LexicalEntry.track_multiple(lexes_composite_list, int(request.cookies.get('locale_id') or 2), publish=True, accept=True)

        response = list(result)
        if preview_mode:
            if int(start_from) > 0 or int(count) > 20:
                for i in response:
                    for j in i['contains']:
                        j['content'] = 'Entity hidden: you \nhave only demo access'
                        j['contains'] = []


        request.response.status = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='lexical_entries_not_accepted', renderer='json', request_method='GET')
def lexical_entries_not_accepted(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    authors = request.params.getall('authors')
    clients = request.params.getall('clients')
    start_date = request.params.get('start_date', )
    if start_date:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = request.params.get('end_date')
    if end_date:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    field_client_id = int(request.params.get('field_client_id', 66))
    field_object_id = int(request.params.get('field_object_id', 10))
    start_from = request.params.get('start_from') or 0
    count = request.params.get('count') or 20

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent and not parent.marked_for_deletion:
        lexes = DBSession.query(LexicalEntry).filter_by(marked_for_deletion=False, parent_client_id=parent.client_id,
                                                        parent_object_id=parent.object_id) \
            .join(LexicalEntry.entity).join(Entity.publishingentity) \
            .filter(PublishingEntity.accepted == False)
        if authors or clients:
            lexes = lexes.join(Client, Entity.client_id == Client.id)
        if authors:
            lexes = lexes.join(Client.user).filter(User.id.in_(authors))
        if clients:
            lexes = lexes.filter(Client.id.in_(clients))
        if start_date:
            lexes = lexes.filter(Entity.created_at >= start_date)
        if end_date:
            lexes = lexes.filter(Entity.created_at <= end_date)
        lexes = lexes.group_by(LexicalEntry) \
            .order_by(func.min(case(
            [(or_(Entity.field_client_id != field_client_id,
                  Entity.field_object_id != field_object_id),
              'яяяяяя')],
            else_=Entity.content))) \
            .group_by(LexicalEntry) \
            .offset(start_from).limit(count)

        result = deque()
        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes.all()]

        result = LexicalEntry.track_multiple(lexes_composite_list, int(request.cookies.get('locale_id') or 2), publish=None, accept=False)

        response = list(result)

        request.response.status = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='lexical_entries_published_count', renderer='json', request_method='GET')
def lexical_entries_published_count(request):
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    authors = request.params.getall('authors')
    clients = request.params.getall('clients')
    start_date = request.params.get('start_date', )
    if start_date:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = request.params.get('end_date')
    if end_date:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            lexical_entries_count = DBSession.query(LexicalEntry) \
                .join(LexicalEntry.entity).join(Entity.publishingentity) \
                .filter(LexicalEntry.parent == parent, PublishingEntity.published == True,
                        Entity.marked_for_deletion == False, LexicalEntry.marked_for_deletion == False)
            if authors or clients or start_date or end_date:
                lexical_entries_count = lexical_entries_count.join(LexicalEntry.entity)
            if authors or clients:
                lexical_entries_count = lexical_entries_count.join(Client, Entity.client_id == Client.id)
            if authors:
                lexical_entries_count = lexical_entries_count.join(Client.user).filter(User.id.in_(authors))
            if clients:
                lexical_entries_count = lexical_entries_count.filter(Client.id.in_(clients))
            if start_date:
                lexical_entries_count = lexical_entries_count.filter(Entity.created_at >= start_date)
            if end_date:
                lexical_entries_count = lexical_entries_count.filter(Entity.created_at <= end_date)
            lexical_entries_count = lexical_entries_count.group_by(LexicalEntry).count()
            # lexical_entries_count = None

            return {"count": lexical_entries_count}
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


@view_config(route_name='lexical_entries_not_accepted_count', renderer='json', request_method='GET')
def lexical_entries_not_accepted_count(request):
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    authors = request.params.getall('authors')
    clients = request.params.getall('clients')
    start_date = request.params.get('start_date', )
    if start_date:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
    end_date = request.params.get('end_date')
    if end_date:
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            lexical_entries_count = DBSession.query(LexicalEntry).filter_by(marked_for_deletion=False,
                                                                            parent_client_id=parent.client_id,
                                                                            parent_object_id=parent.object_id) \
                .join(LexicalEntry.entity).join(Entity.publishingentity) \
                .filter(PublishingEntity.accepted == False)
            if authors or clients or start_date or end_date:
                lexical_entries_count = lexical_entries_count.join(LexicalEntry.entity)
            if authors or clients:
                lexical_entries_count = lexical_entries_count.join(Client, Entity.client_id == Client.id)
            if authors:
                lexical_entries_count = lexical_entries_count.join(Client.user).filter(User.id.in_(authors))
            if clients:
                lexical_entries_count = lexical_entries_count.filter(Client.id.in_(clients))
            if start_date:
                lexical_entries_count = lexical_entries_count.filter(Entity.created_at >= start_date)
            if end_date:
                lexical_entries_count = lexical_entries_count.filter(Entity.created_at <= end_date)
            lexical_entries_count = lexical_entries_count.group_by(LexicalEntry).count()
            # lexical_entries_count = None

            return {"count": lexical_entries_count}
    else:
        request.response.status = HTTPNotFound.code
        return {'error': str("No such perspective in the system")}


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
        for entry in req:
            entity = DBSession.query(Entity). \
                filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()

            group = DBSession.query(Group).join(BaseGroup).filter(
                BaseGroup.subject == 'approve_entities',
                Group.subject_client_id == entity.parent.parent.client_id,
                Group.subject_object_id == entity.parent.parent.object_id,
                BaseGroup.action == 'create').one()
            if user in group.users:
                if entity:
                    entity.publishingentity.published = True
                else:
                    raise CommonException("no such entity in system")
            else:
                raise CommonException("Forbidden")

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


@view_config(route_name='accept_entity', renderer='json', request_method='PATCH', permission='create')
def accept_entity(request):
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
        for entry in req:
            entity = DBSession.query(Entity). \
                filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()
            if entity:
                group = DBSession.query(Group).join(BaseGroup).filter(
                    BaseGroup.subject == 'lexical_entries_and_entities',
                    Group.subject_client_id == entity.parent.parent.client_id,
                    Group.subject_object_id == entity.parent.parent.object_id,
                    BaseGroup.action == 'create').one()
                override_group = DBSession.query(Group).join(BaseGroup).filter(
                        BaseGroup.subject == 'lexical_entries_and_entities',
                        Group.subject_override == True,
                        BaseGroup.action == 'create').one()
                if user in group.users or user in override_group.users:
                    if entity:
                        entity.publishingentity.accepted = True
                    else:
                        raise CommonException("no such entity in system")
                else:
                    raise CommonException("Forbidden")
            else:
                raise CommonException("no such entity in system")

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


@view_config(route_name='approve_entity', renderer='json', request_method='DELETE', permission='delete')
def disapprove_entity(request):
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
        for entry in req:
            entity = DBSession.query(Entity). \
                filter_by(client_id=entry['client_id'], object_id=entry['object_id']).first()

            group = DBSession.query(Group).join(BaseGroup).filter(
                BaseGroup.subject == 'approve_entities',
                Group.subject_client_id == entity.parent.parent.client_id,
                Group.subject_object_id == entity.parent.parent.object_id,
                BaseGroup.action == 'delete').one()
            if user in group.users:
                if entity:
                    entity.publishingentity.published = False
                else:
                    raise CommonException("no such entity in system")
            else:
                raise CommonException("Forbidden")

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


@view_config(route_name='approve_all', renderer='json', request_method='PATCH', permission='create')
def approve_all(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            dictionary_client_id = parent.parent_client_id
            dictionary_object_id = parent.parent_object_id
            entities = DBSession.query(PublishingEntity).join(Entity,
                                                              and_(Entity.client_id == PublishingEntity.client_id,
                                                                   Entity.object_id == PublishingEntity.object_id))\
                .join(Entity.parent).filter(LexicalEntry.parent == parent).all()
            for entity in entities:
                entity.published = True
            # url = request.route_url('approve_entity',
            #                         dictionary_client_id=dictionary_client_id,
            #                         dictionary_object_id=dictionary_object_id,
            #                         perspective_client_id=client_id,
            #                         perspective_object_id=object_id)
            # subreq = Request.blank(url)
            # jsn = entities
            # subreq.json = jsn
            # subreq.method = 'PATCH'
            # headers = {'Cookie': request.headers['Cookie']}
            # subreq.headers = headers
            # request.invoke_subrequest(subreq)

            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}


@view_config(route_name='accept_all', renderer='json', request_method='PATCH', permission='create')
def accept_all(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')

    parent = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if parent:
        if not parent.marked_for_deletion:
            dictionary_client_id = parent.parent_client_id
            dictionary_object_id = parent.parent_object_id
            entities = DBSession.query(Entity).join(Entity.parent).filter(LexicalEntry.parent == parent).all()

            url = request.route_url('accept_entity',
                                    dictionary_client_id=dictionary_client_id,
                                    dictionary_object_id=dictionary_object_id,
                                    perspective_client_id=client_id,
                                    perspective_object_id=object_id)
            subreq = Request.blank(url)
            jsn = [{'client_id': o.client_id, 'object_id': o.object_id} for o in entities]
            subreq.json = jsn
            subreq.method = 'PATCH'
            headers = {'Cookie': request.headers['Cookie']}
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
    object_id = request.matchdict.get('perspective_object_id')
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
                parent = DBSession.query(LexicalEntry).filter_by(client_id=item['parent_client_id'],
                                                                 object_id=item['parent_object_id']).first()

                client_id = variables['auth']
                if 'client_id' in item:
                    if check_client_id(authenticated=client.id, client_id=item['client_id']):
                        client_id = item['client_id']
                    else:
                        request.response.status_code = HTTPBadRequest
                        return {'error': 'client_id from another user'}

                entity = Entity(client_id=client_id,
                                        object_id=item.get('object_id', None),
                                        entity_type=item['entity_type'],
                                        locale_id=item['locale_id'],
                                        additional_metadata=item.get('additional_metadata'),
                                        parent=parent)
                group = DBSession.query(Group).join(BaseGroup).filter(BaseGroup.subject == 'lexical_entries_and_entities',
                                                                      Group.subject_client_id == entity.parent.parent.client_id,
                                                                      Group.subject_object_id == entity.parent.parent.object_id,
                                                                      BaseGroup.action == 'create').one()
                if user in group.users:
                    entity.publishingentity.accepted = True
                upper_level = None
                if item.get('self_client_id') and item.get('self_object_id'):
                    upper_level = DBSession.query(Entity).filter_by(client_id=item['self_client_id'],
                                                                      object_id=item['self_object_id']).first()
                    if not upper_level:
                        return {'error': str("No such upper level in the system")}
                if upper_level:
                    entity.upper_level = upper_level
                filename = req.get('filename')
                real_location = None
                url = None
                tr_atom = DBSession.query(TranslationAtom).join(TranslationGist, and_(
                    TranslationAtom.locale_id == 2,
                    TranslationAtom.parent_client_id == TranslationGist.client_id,
                    TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
                    TranslationGist.client_id == Field.data_type_translation_gist_client_id,
                    TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
                    Field.client_id == req['field_client_id'], Field.object_id == req['field_object_id']).first()
                data_type = tr_atom.content.lower()
                if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
                    real_location, url = create_object(request, req['content'], entity, data_type, filename)
                    entity.content = url
                    old_meta = entity.additional_metadata
                    need_hash = True
                    if old_meta:
                        if old_meta.get('hash'):
                            need_hash = False
                    if need_hash:
                        hash = hashlib.sha224(base64.urlsafe_b64decode(req['content'])).hexdigest()
                        hash_dict = {'hash': hash}
                        if old_meta:
                            old_meta.update(hash_dict)
                        else:
                            old_meta = hash_dict
                        entity.additional_metadata = old_meta
                    if 'markup' in data_type:
                        name = filename.split('.')
                        ext = name[len(name) - 1]
                        if ext.lower() == 'textgrid':
                            data_type = 'praat markup'
                        elif ext.lower() == 'eaf':
                            data_type = 'elan markup'
                    entity.additional_metadata['data_type'] = data_type
                elif data_type == 'link':
                    try:
                        entity.link_client_id = req['link_client_id']
                        entity.link_object_id = req['link_object_id']
                    except (KeyError, TypeError):
                        request.response.status = HTTPBadRequest.code
                        return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
                else:
                    entity.content = req['content']
                # return None
                DBSession.add(entity)
            inserted_items.append({"client_id": entity.client_id, "object_id": entity.object_id})
        request.response.status = HTTPOk.code
        return inserted_items
    # except KeyError as e:
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
        object_id = request.matchdict.get('perspective_object_id')
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
    object_id = request.matchdict.get('perspective_object_id')
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
            if 'desktop' in request.registry.settings:
                real_delete_perspective(perspective, request.registry.settings)
            else:
                perspective.marked_for_deletion = True
                objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=perspective.client_id,
                                                                 object_id=perspective.object_id).one()
                objecttoc.marked_for_deletion = True
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such perspective in the system")}
