import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError


class TestViewDictionaryFailureCondition(unittest.TestCase):

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

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_dictionary(self):
        from lingvodoc.views import view_dictionary
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        response = view_dictionary(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestViewDictionarySuccessCondition(unittest.TestCase):

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
            new_dict=Dictionary(client_id=1, object_id=1, name='test')
            DBSession.add(new_dict)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_dictionary(self):
        from lingvodoc.views import view_dictionary
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        response = view_dictionary(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['name'], 'test')


class TestEditDictionarySuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_lang = Language(client_id=1, object_id=1)
            DBSession.add(new_lang)
            new_dict = Dictionary(client_id=1, object_id=1, name='test')
            DBSession.add(new_dict)
            
    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_dictionary(self):
        from lingvodoc.views import edit_dictionary
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language
            )
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        request.matchdict['parent_client_id'] = 1
        request.matchdict['parent_object_id'] = 1
        request.matchdict['name'] = 'new_name'
        response = edit_dictionary(request)
        self.assertEqual(response['status'], HTTPOk.code)
        dictionary = DBSession.query(Dictionary).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(dictionary, None)
        self.assertEqual(dictionary.name, 'new_name')


