__author__ = 'alexander'

'''
This is an example of how to make a queueable task. "test_queue_set" method is used fo setting a task
to queue and "test_queue_get" fetches all tasks of a current authorized user that he/she put in the
queue previously. To make this work you should uncomment decorators and uncomment adding routes in the
__init__ file.
'''

from lingvodoc.views.v2.celery_test.core import test_queue_set_logic
from lingvodoc.views.v2.utils import (
    get_user_by_client_id
)

from lingvodoc.queue.client import QueueClient

from pyramid.httpexceptions import (
    HTTPOk
)
from pyramid.security import authenticated_userid
from pyramid.view import view_config


#@view_config(route_name='test_queue_set', renderer='json', request_method='GET')
def test_queue_set(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    task_id = QueueClient.generate_task_id(client_id)
    res = test_queue_set_logic.delay(task_id)
    QueueClient.add_task(user, task_id, res)
    response = dict()
    request.response.status = HTTPOk.code
    return response


#@view_config(route_name='test_queue_get', renderer='json', request_method='GET')
def test_queue_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    res = QueueClient.get_tasks_info(user)
    request.response.status = HTTPOk.code
    return res
