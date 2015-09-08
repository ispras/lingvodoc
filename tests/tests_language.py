import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError


class TestViewLanguageSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from lingvodoc.models import (
            Base,
            Language,
            UserEntitiesTranslationString,
            Locale
            )
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            DBSession.add(ru_locale)
            DBSession.flush()
            new_uets = UserEntitiesTranslationString(object_id = 1, client_id = 1, locale_id=1, translation_string = 'test', translation = 'working')
            DBSession.add(new_uets)
            new_lang=Language(client_id=1, object_id=1, translation_string = 'test')
            DBSession.add(new_lang)

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
        self.assertEqual(response['translation_string'], 'working')


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


class TestEditLanguageSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            Language,
            Locale,
            UserEntitiesTranslationString
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            DBSession.add(ru_locale)
            DBSession.flush()
            new_uets = UserEntitiesTranslationString(object_id = 1, client_id = 1, locale_id=1, translation_string = 'test', translation = 'not working')
            DBSession.add(new_uets)
            new_lang = Language(client_id=1, object_id=1, translation_string='test')
            DBSession.add(new_lang)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_language(self):
        from lingvodoc.views import edit_language
        from lingvodoc.models import (
            Language,
            UserEntitiesTranslationString
            )
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        request.json_body = {'translation_string':'new_translation_string', 'translation':'working'}
        response = edit_language(request)
        self.assertEqual(response['status'], HTTPOk.code)
        language = DBSession.query(Language).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(language, None)
        uets = DBSession.query(UserEntitiesTranslationString).filter_by(translation_string=language.translation_string, locale_id=1).first()
        self.assertNotEqual(uets, None)
        self.assertEqual(uets.translation, 'working')


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

    def test_edit_language(self):
        from lingvodoc.views import edit_language
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 42
        request.matchdict['object_id'] = 42
        request.json_body = {'translation_string':'new_translation_string'}
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
        from lingvodoc.views import delete_language
        from lingvodoc.models import (
            Language
            )
        request = testing.DummyRequest()
        request.matchdict['client_id'] = 1
        request.matchdict['object_id'] = 1
        response = delete_language(request)

        self.assertEqual(response['status'], HTTPOk.code)
        language = DBSession.query(Language).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(language, None)
        self.assertEqual(language.marked_for_deletion, True)


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
            Passhash,
            Locale,
            UserEntitiesTranslationString
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            DBSession.add(ru_locale)
            en_locale = Locale(id=2, shortcut="en", intl_name="English")
            DBSession.add(en_locale)
            DBSession.flush()
            new_user = User(id=1, login='test', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)
            new_uets= UserEntitiesTranslationString(client_id = 1, object_id = 1, locale_id=2, translation_string = 'imastring')
            DBSession.add(new_uets)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_language(self):
        from lingvodoc.models import (
            Language,
            UserEntitiesTranslationString
             )
        response = self.app.post('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post_json('/language', params={'translation_string': 'imastring', 'translation': 'imatranslation'})
        self.assertEqual(response.status_int , HTTPOk.code)

        language = DBSession.query(Language).filter_by(translation_string='imastring').first()
        self.assertNotEqual(language, None)
        self.assertEqual(language.object_id, 1)
        self.assertEqual(language.client_id, 2)

        uets = DBSession.query(UserEntitiesTranslationString).filter_by(translation_string='imastring', locale_id=2).first()
        self.assertNotEqual(uets, None)
        self.assertEqual(uets.translation, None)

        uets = DBSession.query(UserEntitiesTranslationString).filter_by(translation_string='imastring', locale_id=1).first()
        self.assertNotEqual(uets, None)
        self.assertEqual(uets.translation, 'imatranslation')


class TestCreateLanguageFailureCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.testing_securitypolicy(userid='1',
                                           permissive=True)
        import webtest
        from pyramid import paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_language(self):
        response = self.app.post_json('/language', params={'translation_string': 'imastring'}, status = HTTPBadRequest.code)
        self.assertEqual(response.status_int, HTTPBadRequest.code)


