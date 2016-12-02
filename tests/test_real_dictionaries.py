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
from tests.tests import alembicini
from pyramid import paster
from waitress import serve
import json

def pserve():
    myapp = paster.get_app('../' + alembicini)


    def my_serve():
        serve(myapp, host='0.0.0.0', port=6543)


    a = threading.Thread(target=my_serve)
    a.daemon = True
    print('starting server')
    a.run()

    print('server started')


class ConvertTest(MyTestCase):
    pass