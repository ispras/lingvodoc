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
        request.matchdict['perspective_id'] = 42
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
        request.matchdict['perspective_id'] = 1
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
        request.matchdict['perspective_id'] = 1
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
        request.matchdict['perspective_id'] = 42
        request.matchdict['name'] = 'new_name'
        response = edit_perspective(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestDeletePerspectiveSuccessCondition(unittest.TestCase):

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
        request.matchdict['perspective_id'] = 1
        response = delete_perspective(request)

        self.assertEqual(response['status'], HTTPOk.code)
        dictionary = DBSession.query(DictionaryPerspective).filter_by(client_id=1, object_id=1).first()
        self.assertNotEqual(dictionary, None)
        self.assertEqual(dictionary.marked_for_deletion, True)


class TestDeletePerspectiveFailureCondition(unittest.TestCase):

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
        request.matchdict['perspective_id'] = 42
        response = delete_perspective(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestViewPerspectiveStatusSuccessCondition(unittest.TestCase):

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
            new_dict = DictionaryPerspective(client_id=1, object_id=1, name='test', state='WiP')
            DBSession.add(new_dict)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_perspective_status(self):
        from lingvodoc.views import view_perspective_status
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 1
        request.matchdict['perspective_id'] = 1
        response = view_perspective_status(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['state'], 'WiP')


class TestViewPerspectiveFailureSuccessCondition(unittest.TestCase):

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

    def test_view_perspective_status(self):
        from lingvodoc.views import view_perspective_status
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 42
        request.matchdict['perspective_id'] = 42
        response = view_perspective_status(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestViewPerspectiveRolesSuccessCondition(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        from sqlalchemy import create_engine
        engine = create_engine('sqlite://')
        from lingvodoc.models import (
            Base,
            DictionaryPerspective,
            Locale,
            Client,
            User,
            Passhash,
            Language,
            BaseGroup,
            Group
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            en_locale = Locale(id=2, shortcut="en", intl_name="English")
            DBSession.add(ru_locale)
            DBSession.add(en_locale)
            DBSession.flush()
            new_user = User(login='test', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_user2 = User(login='test2', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user2.password = new_pass
            DBSession.add(new_user2)
            new_user3 = User(login='test3', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user3.password = new_pass
            DBSession.add(new_user3)
            new_user4 = User(login='test4', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user4.password = new_pass
            DBSession.add(new_user4)
            DBSession.flush()
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)
            DBSession.flush()
            new_language = Language(client_id=1, object_id=1, translation_string = 'WHAT')
            DBSession.add(new_language)
            new_base_group = BaseGroup(id=1, perspective_default=True, name='for_testing', readable_name='For testing')
            DBSession.add(new_base_group)
            DBSession.flush()
            new_base_group2 = BaseGroup(id=2, perspective_default=True, name='for_testing2', readable_name='For testing 2')
            DBSession.add(new_base_group2)
            DBSession.flush()
            new_perspective = DictionaryPerspective(client_id=1, object_id=1, name='test', state='WiP')
            DBSession.add(new_perspective)
            new_group = Group(parent = new_base_group, subject = 'perspective1_1')
            new_group.users.append(new_user)
            new_group.users.append(new_user3)
            new_group2 = Group(parent = new_base_group2, subject = 'perspective1_1')
            new_group2.users.append(new_user)
            new_group2.users.append(new_user2)
            new_group2.users.append(new_user4)
            DBSession.add(new_group)
            DBSession.add(new_group2)

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_view_perspective_roles(self):
        from lingvodoc.views import view_perspective_roles
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 1
        request.matchdict['perspective_id'] = 1
        response = view_perspective_roles(request)
        self.assertEqual(response['status'], HTTPOk.code)
        self.assertEqual(response['roles'], {'For testing': [1, 3], 'For testing 2': [1,2,4]})


class TestViewPerspectiveRolesFailureCondition(unittest.TestCase):

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

    def test_view_perspective_roles(self):
        from lingvodoc.views import view_perspective_roles
        request = testing.DummyRequest()
        request.matchdict['perspective_client_id'] = 42
        request.matchdict['perspective_id'] = 42
        response = view_perspective_roles(request)
        self.assertEqual(response['status'], HTTPNotFound.code)


class TestEditDictionaryRolesSuccessCondition(unittest.TestCase):

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
            Base,
            DictionaryPerspective,
            Locale,
            Client,
            User,
            Passhash,
            Language,
            BaseGroup,
            Group
            )
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        with transaction.manager:
            ru_locale = Locale(id=1, shortcut="ru", intl_name="Русский")
            en_locale = Locale(id=2, shortcut="en", intl_name="English")
            DBSession.add(ru_locale)
            DBSession.add(en_locale)
            DBSession.flush()
            new_user = User(login='test', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user.password = new_pass
            DBSession.add(new_user)
            new_user2 = User(login='test2', default_locale_id = 1)
            new_pass = Passhash(password='pass')
            DBSession.add(new_pass)
            new_user2.password = new_pass
            DBSession.add(new_user2)
            DBSession.flush()
            new_client = Client(id=1, user=new_user)
            DBSession.add(new_client)
            DBSession.flush()
            new_language = Language(client_id=1, object_id=1, translation_string = 'WHAT')
            DBSession.add(new_language)
            new_base_group = BaseGroup(id=1, perspective_default=True, name='for_testing', readable_name='For testing')
            DBSession.add(new_base_group)
            DBSession.flush()
            new_base_group2 = BaseGroup(id=2, perspective_default=True, name='for_testing2', readable_name='For testing 2')
            DBSession.add(new_base_group2)
            DBSession.flush()
            new_perspective = DictionaryPerspective(client_id=1, object_id=1, name='test', state='WiP')
            DBSession.add(new_perspective)
            new_group = Group(parent = new_base_group, subject = 'perspective1_1')
            new_group.users.append(new_user)
            new_group2 = Group(parent = new_base_group2, subject = 'perspective1_1')
            new_group2.users.append(new_user)
            new_group2.users.append(new_user)
            DBSession.add(new_group)
            DBSession.add(new_group2)
            DBSession.flush()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_edit_perspective_roles(self):
        from lingvodoc.models import Group
        request = testing.DummyRequest()
        response = self.app.post('/signin', params={'login': 'test', 'password': 'pass'})
        response = self.app.post('/dictionary/1/1/perspective/1/1/roles', params={'user_id': 2, 'role_names': ['for_testing','for_testing2']})
        self.assertEqual(response.status_int , HTTPOk.code)
        groups = DBSession.query(Group).filter(Group.base_group_id.in_([1,2])).filter_by(subject='perspective1_1')
        for group in groups:
            print(group.subject.upper(), group.parent.name.upper())
            users = []
            for user in group.users:
                users += [user.id]
            self.assertEqual(users, [1,2])
