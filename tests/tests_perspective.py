import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError


class TestViewPerspectiveFailureCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Dictionary,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_perspective(self):
        from lingvodoc.views import view_perspective
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 42
        request.matchdict['perspective_object_id'] = 42
        response = view_perspective(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestViewPerspectiveSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Dictionary,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_dict = DictionaryPerspective(client_id=1, object_id=1, name='test')
            DBSession.add(new_dict)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_perspective(self):
        from lingvodoc.views import view_perspective
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 1
        request.matchdict['perspective_object_id'] = 1
        response = view_perspective(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['name'], 'test')


class TestEditPerspectiveSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Dictionary,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_persp = DictionaryPerspective(client_id=1, object_id=1, name='test')
            DBSession.add(new_persp)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_perspective(self):
        from lingvodoc.views import edit_perspective
        from lingvodoc.models import (
            Base,
            Dictionary,
            DictionaryPerspective
            )
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 1
        request.matchdict['perspective_object_id'] = 1
        request.matchdict['name'] = 'new_name'
        response = edit_perspective(request)
        self.assertEqual(response['status'], HTTPOk.code)
        persp = DBSession.query(DictionaryPerspective).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(persp, None)
        self.assertEqual(persp.name, 'new_name')


class TestEditPerspectiveFailureCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_perspective(self):
        from lingvodoc.views import edit_perspective
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 42
        request.matchdict['perspective_object_id'] = 42
        request.matchdict['name'] = 'new_name'
        response = edit_perspective(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestDeletetPerspectiveSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            DictionaryPerspective
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_persp = DictionaryPerspective(client_id=1, object_id=1, name='test')
            DBSession.add(new_persp)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_delete_perspective(self):
        from lingvodoc.views import delete_perspective
        from lingvodoc.models import (
            DictionaryPerspective
            )
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 1
        request.matchdict['perspective_object_id'] = 1
        response = delete_perspective(request)

        self.assertEqual(response['status'], HTTPOk.code)
        dictionary = DBSession.query(DictionaryPerspective).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(dictionary, None)
        self.assertEqual(dictionary.marked_for_deletion, True)


class TestDeleteDictionaryFailureCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_delete_perspective(self):
        from lingvodoc.views import delete_perspective
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 42
        request.matchdict['perspective_object_id'] = 42
        response = delete_perspective(request)
        self.assertEqual(response['status'], HTTPNotFound.code)
