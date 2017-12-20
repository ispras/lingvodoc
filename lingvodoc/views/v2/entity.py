__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.utils.creation import create_object
from lingvodoc.utils.verification import check_client_id
from lingvodoc.views.v2.delete import real_delete_entity
from lingvodoc.models import (
    Client,
    DBSession,
    Entity,
    Field,
    LexicalEntry,
    TranslationAtom,
    TranslationGist,
    User,
    Group,
    BaseGroup,
    ObjectTOC
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_

import base64
import hashlib
import json
import os
from webob.multidict import MultiDict, NoVars
from lingvodoc.utils.elan_functions import eaf_wordlist

@view_config(route_name='get_entity_indict', renderer='json', request_method='GET')
@view_config(route_name='get_entity', renderer='json', request_method='GET', permission='view')
def view_entity(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    entity = DBSession.query(Entity).filter_by(client_id=client_id, object_id=object_id).first()
    if entity and not entity.marked_for_deletion:
        # TODO: fix urls to relative urls in content
        response = entity.track(False)
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such entity in the system")}


@view_config(route_name='get_entity_indict', renderer='json', request_method='DELETE', permission='delete')
@view_config(route_name='get_entity', renderer='json', request_method='DELETE', permission='delete')
def delete_entity(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    entity = DBSession.query(Entity).filter_by(client_id=client_id, object_id=object_id).first()
    if entity and not entity.marked_for_deletion:
        if 'desktop' in request.registry.settings:
            real_delete_entity(entity, request.registry.settings)
        else:
            entity.marked_for_deletion = True
            objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=entity.client_id,
                                                             object_id=entity.object_id).one()
            objecttoc.marked_for_deletion = True
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such entity in the system")}


@view_config(route_name='create_entity', renderer='json', request_method='POST')
def create_entity(request):  # tested
    try:
        # req = None
        content = None
        if request.content_type in ['application/x-www-form-urlencoded','multipart/form-data'] and type(request.POST) == MultiDict:
            data = request.POST
            if not data:
                return {'error': 'empty request'}
            elif not "entity" in data:
                return {'error': 'entity key not nound'}
            elif not "content" in data:
                return {'error': 'content key not nound'}
            req = data['entity']
            if type(req) == str:
                req = json.loads(req)
            else:
                req = json.loads(req.file.read().decode())
            # if "content" in data:
            content = data['content']
        elif request.content_type == 'application/json' and type(request.POST) == NoVars:
            req = request.json_body

        variables = {'auth': authenticated_userid(request)}
        response = dict()
        parent_client_id = request.matchdict.get('lexical_entry_client_id')
        parent_object_id = request.matchdict.get('lexical_entry_object_id')
        # if not req:
        #     req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        object_id = req.get('object_id', None)
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(LexicalEntry).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such lexical entry in the system")}

        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']) or user.id == 1:
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}

        # if 'content' not in req is None:  # in link entity there is no content
        #     request.response.status = HTTPBadRequest.code
        #     return {'error': 'Missing value: content'}

        additional_metadata = req.get('additional_metadata')
        upper_level = None
        # import pdb
        # pdb.set_trace(v
        # data_type = DBSession.query(TranslationAtom).filter(TranslationAtom.locale_id == 2).join(TranslationGist, and_(
        #     TranslationAtom.parent_client_id == TranslationGist.client_id,
        #     TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
        #     TranslationGist.client_id == Field.data_type_translation_gist_client_id,
        #     TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
        #     Field.client_id == req['field_client_id'], Field.object_id == req['field_object_id']).first()
        tr_atom = DBSession.query(TranslationAtom).join(TranslationGist, and_(
            TranslationAtom.locale_id == 2,
            TranslationAtom.parent_client_id == TranslationGist.client_id,
            TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
            TranslationGist.client_id == Field.data_type_translation_gist_client_id,
            TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
            Field.client_id == req['field_client_id'], Field.object_id == req['field_object_id']).first()
        data_type = tr_atom.content.lower()
        if req.get('self_client_id') and req.get('self_object_id'):
            upper_level = DBSession.query(Entity).filter_by(client_id=req['self_client_id'],
                                                              object_id=req['self_object_id']).first()
            if not upper_level:
                return {'error': str("No such upper level in the system")}
        entity = Entity(client_id=client_id,
                        object_id = object_id,
                        field_client_id=req['field_client_id'],
                        field_object_id=req['field_object_id'],
                        locale_id=req.get('locale_id'),
                        additional_metadata=additional_metadata,
                        parent=parent)
        group = DBSession.query(Group).join(BaseGroup).filter(BaseGroup.subject == 'lexical_entries_and_entities',
                                                              Group.subject_client_id == entity.parent.parent.client_id,
                                                              Group.subject_object_id == entity.parent.parent.object_id,
                                                              BaseGroup.action == 'create').one()
        override_group = DBSession.query(Group).join(BaseGroup).filter(
                BaseGroup.subject == 'lexical_entries_and_entities',
                Group.subject_override == True,
                BaseGroup.action == 'create').one()
        if user in group.users or user in override_group.users:
            entity.publishingentity.accepted = True
        if upper_level:
            entity.upper_level = upper_level
        filename = req.get('filename')
        real_location = None
        url = None
        if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
            if content is not None:
                real_location, url = create_object(request, content.file, entity, data_type, filename, json_input=False)
            else:
                real_location, url = create_object(request, req['content'], entity, data_type, filename)

            entity.content = url
            old_meta = entity.additional_metadata
            need_hash = True
            if old_meta:
                if old_meta.get('hash'):
                    need_hash = False
            if need_hash:
                if content is not None:
                    hash = hashlib.sha224(content.file.read()).hexdigest()
                else:
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


            if 'elan' in data_type:
                bag_of_words = list(eaf_wordlist(entity))
                entity.additional_metadata['bag_of_words'] = bag_of_words

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
        request.response.status = HTTPOk.code
        response['client_id'] = entity.client_id
        response['object_id'] = entity.object_id
        return response

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}