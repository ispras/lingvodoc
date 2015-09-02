import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError


class TestDictionariesListSuccessCondition(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Dictionary
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_dict=Dictionary(client_id=1,object_id=1,name='test')
            DBSession.add(new_dict)
            new_dict=Dictionary(client_id=1,object_id=2,name='test2')
            DBSession.add(new_dict)

    def tearDown(self):
        from lingvodoc.models import (
            Base,
            Dictionary
            )
        from sqlalchemy import create_engine
        DBSession.remove()
        testing.tearDown()

    def test_passing_view(self):
        from lingvodoc.views import dictionaries_list
        request = testing.DummyRequest()
        response = dictionaries_list(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['dictionaries'], [{'object_id': 1, 'client_id': 1}, {'object_id':2,'client_id':1}])
