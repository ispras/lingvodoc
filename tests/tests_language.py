# 
# NOTE
#
# See information on how tests are organized and how they should work in the tests' package __init__.py file
# (currently lingvodoc/tests/__init__.py).
#


import unittest
import transaction

from pyramid import testing

from lingvodoc.models import DBSession
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError

import pytest


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
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
            new_uets = UserEntitiesTranslationString(object_id = 1, client_id = 1, locale_id=1,
                                                     translation_string = 'test', translation = 'working')
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


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
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


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
class TestEditLanguageSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        import webtest
        from pyramid import  paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            Language,
            Locale,
            UserEntitiesTranslationString,
            User,
            Passhash,
            Client
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
            DBSession.flush()
            new_uets = UserEntitiesTranslationString(object_id = 1, client_id = 1, locale_id=1,
                                                     translation_string = 'test', translation = 'not working')
            DBSession.add(new_uets)
            new_lang = Language(client_id=1, object_id=1, translation_string='test')
            DBSession.add(new_lang)
            new_lang = Language(client_id=1, object_id=2, translation_string='testy')
            DBSession.add(new_lang)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_language_name(self):
        from lingvodoc.models import (
            Language,
            UserEntitiesTranslationString
            )
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.put_json('/language/1/1', params={'translation_string': 'test', 'translation': 'working'})
        self.assertEqual(response.status_int, HTTPOk.code)
        language = DBSession.query(Language).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(language, None)
        uets = DBSession.query(UserEntitiesTranslationString).\
            filter_by(translation_string=language.translation_string, locale_id=1).first()
        self.assertNotEqual(uets, None)
        self.assertEqual(uets.translation, 'working')

    def test_edit_language_parent(self):
        from lingvodoc.models import (
            Language
            )
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.put_json('/language/1/1', params={'parent_object_id': 2, 'parent_client_id': 1})
        self.assertEqual(response.status_int, HTTPOk.code)
        language = DBSession.query(Language).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(language, None)
        parent = DBSession.query(Language).filter_by(client_id=1, object_id=2).first()
        self.assertNotEqual(parent, None)
        self.assertEqual(language.parent, parent)


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
class TestEditLanguageFailureCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        import webtest
        from pyramid import  paster
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        myapp = paster.get_app('testing.ini')
        self.app = webtest.TestApp(myapp)
        from lingvodoc.models import (
            Base,
            Locale,
            User,
            Passhash,
            Client
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
    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_language_without_login(self):
        response = self.app.put_json('/language/42/42',
                                     params={'translation_string': 'imastring', 'translation': 'imatranslation'},
                                     status = HTTPBadRequest.code)
        self.assertEqual(response.status_int, HTTPBadRequest.code)

    def test_edit_language_with_login(self):
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.put_json('/language/42/42',
                                     params={'translation_string': 'imastring', 'translation': 'imatranslation'},
                                     status = HTTPNotFound.code)
        self.assertEqual(response.status_int, HTTPNotFound.code)


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
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


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
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


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
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
            UserEntitiesTranslationString,
            Language
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
            new_uets= UserEntitiesTranslationString(client_id = 1, object_id = 1, locale_id=2,
                                                    translation_string = 'imastring')
            DBSession.add(new_uets)
            new_lang = Language(client_id=1, object_id=1, translation_string='testy')
            DBSession.add(new_lang)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_create_language(self):
        from lingvodoc.models import (
            Language,
            UserEntitiesTranslationString
             )
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post_json('/language', params={'translation_string': 'imastring',
                                                           'translation': 'imatranslation'})
        self.assertEqual(response.status_int , HTTPOk.code)

        language = DBSession.query(Language).filter_by(translation_string='imastring').first()
        self.assertNotEqual(language, None)
        self.assertEqual(language.object_id, 1)
        self.assertEqual(language.client_id, 2)

        uets = DBSession.query(UserEntitiesTranslationString).\
            filter_by(translation_string='imastring', locale_id=2).first()
        self.assertNotEqual(uets, None)
        self.assertEqual(uets.translation, None)

        uets = DBSession.query(UserEntitiesTranslationString).\
            filter_by(translation_string='imastring', locale_id=1).first()
        self.assertNotEqual(uets, None)
        self.assertEqual(uets.translation, 'imatranslation')

    def test_create_language_with_parent(self):
        from lingvodoc.models import (
            Language,
            UserEntitiesTranslationString
             )
        response = self.app.post_json('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post_json('/language', params={'translation_string': 'imastring2',
                                                           'translation': 'imatranslation2',
                                                           'parent_object_id': 1, 'parent_client_id': 1})
        self.assertEqual(response.status_int , HTTPOk.code)

        language = DBSession.query(Language).filter_by(translation_string='imastring2').first()
        self.assertNotEqual(language, None)
        self.assertEqual(language.object_id, 1)
        self.assertEqual(language.client_id, 2)

        parent = DBSession.query(Language).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(parent, None)
        self.assertEqual(parent, language.parent)

        uets = DBSession.query(UserEntitiesTranslationString).\
            filter_by(translation_string='imastring2', locale_id=1).first()
        self.assertNotEqual(uets, None)
        self.assertEqual(uets.translation, 'imatranslation2')


@pytest.mark.skip(reason = 'Unconverted test from the previous version.')
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
        response = self.app.post_json('/language',
                                      params={'translation_string': 'imastring'}, status = HTTPBadRequest.code)
        self.assertEqual(response.status_int, HTTPBadRequest.code)

