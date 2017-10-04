__author__ = 'alexander'

from lingvodoc.views.v2.sociolinguistics import check_socio
from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    Client,
    DBSession,
    User,
    UserBlobs,
    ObjectTOC
)
from lingvodoc.views.v2.utils import (
    create_object,
    get_user_by_client_id,
    check_client_id
)
from lingvodoc.scripts.convert_rules import rules

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk,
    HTTPForbidden,
    HTTPUnauthorized
)
from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError

import logging
import os
import random
import string
import sys
import time

log = logging.getLogger(__name__)


@view_config(route_name='convert', renderer='json', request_method='POST')
def convert(request):  # TODO: test when convert in blobs will be needed
    import requests
    try:
        variables = {'auth': request.authenticated_userid}
        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        out_type = req['out_type']
        client_id = req['client_id']
        object_id = req['object_id']

        blob = DBSession.query(UserBlobs).filter_by(client_id=client_id, object_id=object_id).first()
        if not blob:
            raise KeyError("No such file")
        r = requests.get(blob.content)
        if not r:
            raise CommonException("Cannot access file")
        content = r.content
        try:
            n = 10
            filename = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                                              for c in range(n))
            extension = os.path.splitext(blob.content)[1]
            f = open(filename + extension, 'wb')
        except Exception as e:
            request.response.status = HTTPInternalServerError.code
            return {'error': str(e)}
        try:
            f.write(content)
            f.close()
            data_type = blob.data_type
            for rule in rules:
                if data_type == rule.in_type and out_type == rule.out_type:
                    if extension in rule.in_extensions:
                        if os.path.getsize(filename) / 1024 / 1024.0 < rule.max_in_size:
                            content = rule.convert(filename, req.get('config'), rule.converter_config)
                            if sys.getsizeof(content) / 1024 / 1024.0 < rule.max_out_size:
                                request.response.status = HTTPOk.code
                                return {'content': content}
                    raise KeyError("Cannot access file")
        except Exception as e:
            request.response.status = HTTPInternalServerError.code
            return {'error': str(e)}
        finally:
            os.remove(filename)
            pass
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='upload_user_blob', renderer='json', request_method='POST')
def upload_user_blob(request):  # TODO: remove blob Object
    variables = {'auth': authenticated_userid(request)}
    response = dict()
    filename = request.POST['blob'].filename
    input_file = request.POST['blob'].file

    class Object(object):
        pass

    client_id = variables['auth']
    if request.POST.get('client_id', None):
        if check_client_id(authenticated=variables['auth'], client_id=request.POST['client_id']):
            client_id = request.POST['client_id']
        else:
            request.response.status_code = HTTPBadRequest
            return {'error': 'client_id from another user'}

    blob = Object()
    blob.client_id = client_id
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    blob.data_type = request.POST['data_type']

    blob.filename = filename



    current_user = DBSession.query(User).filter_by(id=client.user_id).first()
    object_id = request.POST.get('object_id', None)

    blob_object = UserBlobs(object_id=object_id,
                            client_id=blob.client_id,
                            name=filename,
                            data_type=blob.data_type,
                            user_id=current_user.id)

    current_user.userblobs.append(blob_object)
    blob_object.real_storage_path, blob_object.content = create_object(request, input_file, blob_object, blob.data_type,
                                                                       blob.filename, json_input=False)
    if blob.data_type == "sociolinguistics":
        try:
            check_socio(blob_object.real_storage_path)
        except Exception as e:
            request.response.status = HTTPBadRequest.code
            response = {"error": str(e)}
            return response

    DBSession.add(blob_object)
    DBSession.flush()

    request.response.status = HTTPOk.code
    response = {"client_id": blob_object.client_id, "object_id": blob_object.object_id, "content": blob_object.content}
    return response


@view_config(route_name='get_user_blob', renderer='json', request_method='GET')
def get_user_blob(request):  # TODO: test
    variables = {'auth': authenticated_userid(request)}
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    blob = DBSession.query(UserBlobs).filter_by(client_id=client_id, object_id=object_id).first()
    if blob:
        response = {'name': blob.name, 'content': blob.content, 'data_type': blob.data_type,
                    'client_id': blob.client_id, 'object_id': blob.object_id, 'created_at': blob.created_at}
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': 'No such blob in the system'}


@view_config(route_name='delete_user_blob', renderer='json', request_method='DELETE')
def delete_user_blob(request):
    user = get_user_by_client_id(authenticated_userid(request))
    if user is None:
        request.response.status = HTTPUnauthorized.code
        return {'error': "Guests can not delete resources."}
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    if user != get_user_by_client_id(client_id):
        request.response.status = HTTPForbidden.code
        return {'error': "That file doesn't belong to you."}
    blob = DBSession.query(UserBlobs).filter_by(client_id=client_id, object_id=object_id).first()
    if not blob:
        request.response.status = HTTPNotFound.code
        return {'error': 'No such blob in the system'}

    filelocation = blob.real_storage_path
    DBSession.delete(blob)
    objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=blob.client_id,
                                                     object_id=blob.object_id).one()
    DBSession.delete(objecttoc)
    request.response.status = HTTPOk.code
    try:
        os.unlink(filelocation)
    except:
        # NOTE: intentionally not an error
        return {"warning": "File can not be deleted physically; deleting from DMBS only."}
    return


@view_config(route_name='list_user_blobs', renderer='json', request_method='GET')
def list_user_blobs(request):  # TODO: test
    variables = {'auth': authenticated_userid(request)}
    allowed_global_types = ["sociolinguistics"]
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    data_type = request.params.get('data_type')
    is_global = request.params.get('is_global')
    if data_type:
        if not is_global:
            user_blobs = DBSession.query(UserBlobs).filter_by(user_id=client.user_id, data_type=data_type).all()
        else:
            if data_type in allowed_global_types:
                user_blobs = DBSession.query(UserBlobs).filter_by(data_type=data_type).all()
            else:
                request.response.status = HTTPForbidden.code
                return {"error": "You can not list that data type globally."}
    else:
        user_blobs = DBSession.query(UserBlobs).filter_by(user_id=client.user_id).all()
    request.response.status = HTTPOk.code
    response = [{'name': blob.name, 'content': blob.content, 'data_type': blob.data_type,
                 'client_id': blob.client_id, 'object_id': blob.object_id, 'created_at': blob.created_at}
                for blob in user_blobs]
    return response


@view_config(route_name='blob_upload', renderer='templates/user_upload.pt', request_method='GET')
def blob_upload_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    if user is None:
        response = Response()
        return HTTPFound(location=request.route_url('login'), headers=response.headers)

    dictionary_client_id = request.matchdict.get('dictionary_client_id')
    dictionary_object_id = request.matchdict.get('dictionary_object_id')
    perspective_client_id = request.matchdict.get('perspective_client_id')
    perspective_object_id = request.matchdict.get('perspective_object_id')

    variables = {'client_id': client_id, 'user': user, 'dictionary_client_id': dictionary_client_id,
                 'dictionary_object_id': dictionary_object_id, 'perspective_client_id': perspective_client_id,
                 'perspective_object_id': perspective_object_id}

    return render_to_response('templates/user_upload.pt', variables, request=request)
