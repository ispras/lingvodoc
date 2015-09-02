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


class TestEditDictionaryFailureCondition(unittest.TestCase):

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

    def test_edit_dictionary(self):
        from lingvodoc.views import edit_dictionary
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        request.matchdict['name'] = 'new_name'
        response = edit_dictionary(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestDeleteDictionarySuccessCondition(unittest.TestCase):

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
            new_dict = Dictionary(client_id=1, object_id=1, name='test')
            DBSession.add(new_dict)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_delete_dictionary(self):
        from lingvodoc.views import delete_dictionary
        from lingvodoc.models import (
            Dictionary
            )
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        response = delete_dictionary(request)

        self.assertEqual(response['status'], HTTPOk.code)
        dictionary = DBSession.query(Dictionary).filter_by(client_id=1, object_id=1).first()
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

    def test_delete_dictionary(self):
        from lingvodoc.views import delete_dictionary
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        response = delete_dictionary(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestCreateDictionarySuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.testing_securitypolicy(userid='1',
                                           permissive=True)
        import webtest
        from pyramid import  paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            User,
            Client,
            Passhash,
            Language,
            BaseGroup
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_user = User(id=1, login='test')
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)
            new_language = Language(client_id=1, object_id=1, translation_string = 'WHAT')
            DBSession.add(new_language)
            new_base_group = BaseGroup(id=1, dictionary_default=True, name='for_testing', readable_name='For testing')

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_dictionary(self):
        from lingvodoc.models import (
            Dictionary,
            Group
             )
        response = self.app.post('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post('/dictionary', params={'name': 'imaname', 'parent_client_id': 1, 'parent_object_id': 1})
        self.assertEqual(response.status_int , HTTPOk.code)

        dictionary = DBSession.query(Dictionary).filter_by(name='imaname').first()
        self.assertNotEqual(dictionary, None)
        self.assertEqual(dictionary.object_id, 1)
        self.assertEqual(dictionary.client_id, 2)
        group = DBSession.query(Group).filter_by(subject='dictionary1_2', base_group_id=1).first()
        self.assertNotEqual(dictionary, group)



class TestCreateDictionaryFailureCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.testing_securitypolicy(userid='1',
                                           permissive=True)
        import webtest
        from pyramid import  paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            User,
            Client,
            Passhash
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_dictionary(self):
        from lingvodoc.views import create_language
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language
             )
        response = self.app.post('/dictionary', params={'name': 'imastring'}, status = HTTPBadRequest.code)
        self.assertEqual(response.status_int, HTTPBadRequest.code)


class TestViewDictionaryStatusSuccessCondition(unittest.TestCase):

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
            new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
            DBSession.add(new_dict)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_dictionary_status(self):
        from lingvodoc.views import view_dictionary_status
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        response = view_dictionary_status(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['state'], 'WiP')


class TestViewDictionaryFailureSuccessCondition(unittest.TestCase):

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

    def test_view_dictionary_status(self):
        from lingvodoc.views import view_dictionary_status
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        response = view_dictionary_status(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestEditDictionaryStatusSuccessCondition(unittest.TestCase):

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
            new_dict = Dictionary(client_id=1, object_id=1, name='test', state='WiP')
            DBSession.add(new_dict)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_dictionary_status(self):
        from lingvodoc.views import edit_dictionary_status
        from lingvodoc.models import Dictionary
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        request.matchdict['state'] = 'testing'
        response = edit_dictionary_status(request)
        self.assertEqual(response['status'], HTTPOk.code)
        dictionary = DBSession.query(Dictionary).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(dictionary, None)
        self.assertEqual(dictionary.state, 'testing')


class TestEditDictionaryStatusFailureCondition(unittest.TestCase):

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

    def test_view_dictionary_status(self):
        from lingvodoc.views import edit_dictionary_status
        from lingvodoc.models import Dictionary
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        request.matchdict['state'] = 'testing'
        response = edit_dictionary_status(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


