import base64
from hashlib import md5
from lingvodoc.cache.caching import TaskStatus
from lingvodoc.models import Client
from pyramid.response import Response
from pyramid.security import authenticated_userid
from pyramid.view import view_config

import logging
log = logging.getLogger(__name__)


@view_config(route_name='tasks', renderer='json', request_method='GET')
def get_tasks(request):
    client_id = authenticated_userid(request)
    # if not client_id:
    #     return []
    if not client_id:
        ip = request.client_addr if request.client_addr else ""
        useragent = request.headers["User-Agent"] if "User-Agent" in request.headers else ""
        unique_string = "unauthenticated_%s_%s" % (ip, useragent)
        user_id = base64.b64encode(md5(unique_string.encode('utf-8')).digest())[:7]
        tasks = TaskStatus.get_user_tasks(user_id, clear_out=True)
        return tasks
    user = Client.get_user_by_client_id(authenticated_userid(request))
    tasks = TaskStatus.get_user_tasks(user.id, clear_out=True)
    return tasks


@view_config(route_name='delete_task', renderer='json', request_method='DELETE')
def delete_task(request):
    #client_id = authenticated_userid(request)
    # if not client_id:
    #     return {}
    task_id = request.matchdict.get('task_id')
    task_key = "task:" + task_id
    task = TaskStatus.get_from_cache(task_key)
    if task:
        task.delete()
    return {}
