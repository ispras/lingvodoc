# 
# NOTE
#
# See information on how tests are organized and how they should work in the tests' package __init__.py file
# (currently lingvodoc/tests/__init__.py).
#


from tests.tests import MyTestCase

from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPOk,
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPUnauthorized,
    HTTPFound,
    HTTPForbidden
)

import threading
from .tests import alembic_ini_path
from pyramid import paster
from waitress import serve
import json


def pserve():
    myapp = paster.get_app(alembic_ini_path)


    def my_serve():
        serve(myapp, host='0.0.0.0', port=6543)


    a = threading.Thread(target=my_serve)
    a.daemon = True
    print('starting server')
    a.run()

    print('server started')


class ConvertTest(MyTestCase):
    pass

