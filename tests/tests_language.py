import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError


class TestViewLanguageFailureCondition(unittest.TestCase):

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

    def test_view_language(self):
        from lingvodoc.views import view_language
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        response = view_language(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestViewLanguageSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Language
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_dict=Language(client_id=1, object_id=1, translation_string = 'test')
            DBSession.add(new_dict)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_language(self):
        from lingvodoc.views import view_language
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        response = view_language(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['translation_string'], 'test')  # bad test


class TestEditLanguageSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Language
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_lang = Language(client_id=1, object_id=1, translation_string='test')
            DBSession.add(new_lang)
            
    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_language(self):
        from lingvodoc.views import edit_language
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language
            )
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        request.matchdict['translation_string'] = 'new_translation_string'
        response = edit_language(request)
        self.assertEqual(response['status'], HTTPOk.code)
        language = DBSession.query(Language).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(language, None)
        self.assertEqual(language.translation_string, 'new_translation_string')


class TestEditLanguageFailureCondition(unittest.TestCase):

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

    def test_view_language(self):
        from lingvodoc.views import edit_language
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        request.matchdict['translation_string'] = 'new_translation_string'
        response = edit_language(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestDeleteLanguageSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Language
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            new_lang = Language(client_id=1, object_id=1, translation_string='test')
            DBSession.add(new_lang)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_delete_language(self):
        from lingvodoc.views import edit_language
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language
            )
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        response = edit_language(request)

        self.assertEqual(response['status'], HTTPOk.code)
        language = DBSession.query(Language).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(language, None)
        self.assertNotEqual(language.marked_for_deletion, True)


class TestDeleteLanguageFailureCondition(unittest.TestCase):

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

    def test_delete_language(self):
        from lingvodoc.views import delete_language
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        response = delete_language(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestCreateLanguageSuccessCondition(unittest.TestCase):

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
        with transaction.manager:
            new_user = User(id=1, login='test')
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_language(self):
        from lingvodoc.views import create_language
        from lingvodoc.models import (
            Base,
            Dictionary,
            Language
             )
        # from webob.multidict import MultiDict
        # from pyramid.request import Request
        # request = testing.DummyRequest()
        # request.registry = self.config.registry
        # request.POST = MultiDict()
        # request.method = 'POST'
        # request.POST.add(key='translation_string', value='something')
        response = self.app.post('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post('/language', params={'testing_string': 'imastring'})
        self.assertEqual(response['status'], HTTPOk.code)
        language = DBSession.query(Language).filter_by(testing_string='imastring').first()
        self.assertNotEqual(language, None)
        print ('CLIENT ID HERE:',language.client_id)
        self.assertNotEqual(language.testing_string, 'imastring')



