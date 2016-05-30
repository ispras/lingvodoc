__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    Client,
    DBSession,
    User,
    UserBlobs
)
from lingvodoc.views.v1.utils import (
    create_object,
    get_user_by_client_id
)
from lingvodoc.scripts.convert_rules import rules

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
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
def upload_user_blob(request):  # TODO: test
    variables = {'auth': authenticated_userid(request)}
    response = dict()
    filename = request.POST['blob'].filename
    input_file = request.POST['blob'].file

    class Object(object):
        pass

    blob = Object()
    blob.client_id = variables['auth']
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    blob.object_id = DBSession.query(UserBlobs).filter_by(client_id=client.id).count() + 1
    blob.data_type = request.POST['data_type']

    blob.filename = filename

    current_user = DBSession.query(User).filter_by(id=client.user_id).first()

    blob_object = UserBlobs(object_id=blob.object_id,
                            client_id=blob.client_id,
                            name=filename,
                            data_type=blob.data_type,
                            user_id=current_user.id)

    current_user.userblobs.append(blob_object)
    DBSession.flush()
    blob_object.real_storage_path, blob_object.content = create_object(request, input_file, blob_object, blob.data_type,
                                                                       blob.filename, json_input=False)
    DBSession.add(blob_object)
    DBSession.add(current_user)
    request.response.status = HTTPOk.code
    response = {"client_id": blob.client_id, "object_id": blob.object_id, "content": blob_object.content}
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
                    'client_id': blob.client_id, 'object_id': blob.object_id}
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such blob in the system")}


@view_config(route_name='list_user_blobs', renderer='json', request_method='GET')
def list_user_blobs(request):  # TODO: test
    variables = {'auth': authenticated_userid(request)}
    #    user_client_ids = [cl_id.id for cl_id in DBSession.query(Client).filter_by(id=variables['auth']).all()]
    #    user_blobs = DBSession.query(UserBlobs).filter_by(client_id.in_(user_client_ids)).all()
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    user_blobs = DBSession.query(UserBlobs).filter_by(user_id=client.user_id).all()
    request.response.status = HTTPOk.code
    response = [{'name': blob.name, 'content': blob.content, 'data_type': blob.data_type,
                 'client_id': blob.client_id, 'object_id': blob.object_id} for blob in user_blobs]
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
    perspective_id = request.matchdict.get('perspective_id')

    variables = {'client_id': client_id, 'user': user, 'dictionary_client_id': dictionary_client_id,
                 'dictionary_object_id': dictionary_object_id, 'perspective_client_id': perspective_client_id,
                 'perspective_id': perspective_id}

    return render_to_response('templates/user_upload.pt', variables, request=request)
