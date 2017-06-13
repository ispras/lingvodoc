__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.views.v2.convert.core import async_convert_dictionary
from lingvodoc.views.v2.utils import (
    get_user_by_client_id
)
from lingvodoc.queue.client import (
    QueueClient
)
from lingvodoc.models import (
    Client,
    DBSession,
    DictionaryPerspective,
    User,
    UserBlobs,
    Entity
)

from lingvodoc.scripts.lingvodoc_converter import convert_one, get_dict_attributes

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPOk
)
from pyramid.request import Request
from pyramid.security import (
    authenticated_userid,
)
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError

import multiprocessing
import logging
import random
import os
import string
import sys
import time

log = logging.getLogger(__name__)


@view_config(route_name='convert_dictionary_check', renderer='json', request_method='POST')
def convert_dictionary_check(request):  # TODO: test
    import sqlite3
    req = request.json_body

    client_id = req['blob_client_id']
    object_id = req['blob_object_id']
    # parent_client_id = req['parent_client_id']
    # parent_object_id = req['parent_object_id']
    client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    user = client.user

    blob = DBSession.query(UserBlobs).filter_by(client_id=client_id, object_id=object_id).first()
    filename = blob.real_storage_path
    sqconn = sqlite3.connect(filename)
    res = get_dict_attributes(sqconn)
    dialeqt_id = res['dialeqt_id']
    persps = DBSession.query(DictionaryPerspective).filter(DictionaryPerspective.import_hash == dialeqt_id).all()
    perspectives = []
    for perspective in persps:
        path = request.route_url('perspective',
                                 dictionary_client_id=perspective.parent_client_id,
                                 dictionary_object_id=perspective.parent_object_id,
                                 perspective_client_id=perspective.client_id,
                                 perspective_object_id=perspective.object_id)
        subreq = Request.blank(path)
        subreq.method = 'GET'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if 'error' not in resp.json:
            perspectives += [resp.json]
    request.response.status = HTTPOk.code
    return perspectives


@view_config(route_name='convert_dictionary', renderer='json', request_method='POST')
def convert_dictionary(request):  # TODO: test
    req = request.json_body
    args = dict()
    args['client_id'] = req['blob_client_id']
    args['object_id'] = req['blob_object_id']
    args['parent_client_id'] = req['parent_client_id']
    args['parent_object_id'] = req['parent_object_id']
    args['dictionary_client_id'] = req.get('dictionary_client_id')
    args['dictionary_object_id'] = req.get('dictionary_object_id')
    args['perspective_client_id'] = req.get('perspective_client_id')
    args['perspective_object_id'] = req.get('perspective_object_id')
    args['user_id'] = authenticated_userid(request)
    #import pdb
    #pdb.set_trace()
    #import time
    #time.sleep(1)
    task_id = QueueClient.generate_task_id(args['user_id'])
    res = async_convert_dictionary.delay(task_id=task_id, **args)
    log.debug("Conversion started")
    QueueClient.add_task(get_user_by_client_id(args['user_id']), task_id, res)
    request.response.status = HTTPOk.code
    return {"status": "Your dictionary is being converted."
                      " Wait 5-15 minutes and you will see new dictionary in your dashboard."}


@view_config(route_name='convert_markup', renderer='string', request_method='POST')
def convert_markup(request):
    import requests
    from lingvodoc.scripts.convert_rules import praat_to_elan
    try:
        variables = {'auth': request.authenticated_userid}
        req = request.json_body
        # out_type = req['out_type']
        client_id = req['client_id']
        object_id = req['object_id']

        entity = DBSession.query(Entity).filter_by(client_id=client_id, object_id=object_id).first()
        # l2e = None
        if not entity:
            raise KeyError("No such file")
        r = requests.get(entity.content)
        if not r:
            raise CommonException("Cannot access file")
        content = r.content
        try:
            n = 10
            filename = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                                              for c in range(n))
            # extension = os.path.splitext(blob.content)[1]
            f = open(filename, 'wb')
        except Exception as e:
            request.response.status = HTTPInternalServerError.code
            return {'error': str(e)}
        try:
            f.write(content)
            f.close()
            if os.path.getsize(filename) / (10 * 1024 * 1024.0) < 1:
                if 'data_type' in entity.additional_metadata :
                    if 'praat' in entity.additional_metadata['data_type']:
                        content = praat_to_elan(filename)
                        if sys.getsizeof(content) / (10 * 1024 * 1024.0) < 1:
                            # filename2 = 'abc.xml'
                            # f2 = open(filename2, 'w')
                            # try:
                            #     f2.write(content)
                            #     f2.close()
                            #     # os.system('xmllint --noout --dtdvalid ' + filename2 + '> xmloutput 2>&1')
                            #     os.system('xmllint --dvalid ' + filename2 + '> xmloutput 2>&1')
                            # except:
                            #     print('fail with xmllint')
                            # finally:
                            #     pass
                            #     os.remove(filename2)
                            return content
                    elif 'elan' in entity.additional_metadata['data_type']:
                        with open(filename, 'r') as f:
                            return f.read()
                    else:
                        raise KeyError("Not allowed convert option")
                    raise KeyError('File too big')
                raise KeyError("Not allowed convert option")
            raise KeyError('File too big')
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
