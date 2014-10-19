import os
import sys
import transaction

from sqlalchemy import engine_from_config

from pyramid.paster import (
    get_appsettings,
    setup_logging,
    )

from pyramid.scripts.common import parse_vars

from ..models import (
    DBSession,
    Base,
    User,
    Passhash,
    Locale,
    BaseGroup,
    Group
    )


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri> [var=value]\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


def main(argv=sys.argv):
    if len(argv) < 2:
        usage(argv)
    config_uri = argv[1]
    options = parse_vars(argv[2:])
    setup_logging(config_uri)
    settings = get_appsettings(config_uri, options=options)
    accounts = get_appsettings(config_uri, 'accounts')
    engine = engine_from_config(settings, 'sqlalchemy.')

    DBSession.configure(bind=engine)
    Base.metadata.create_all(engine)
    with transaction.manager:

        # creating administrator account
        print(accounts.__dict__)
        print(accounts['administrator_login'])
        admin_account = DBSession.query(User).filter_by(login='admin').first()
        if not admin_account:
            print("Admin record not found, initializing")
            admin_user = User(login=accounts['administrator_login'])
            pwd = Passhash(password=accounts['administrator_password'])
            admin_user.password = pwd
            DBSession.add(admin_user)

        # creating base locales
        ru_locale = Locale(id=1, shortcut="ru", name="Русский")
        en_locale = Locale(id=2, shortcut="en", name="English")
        de_locale = Locale(id=3, shortcut="de", name="Deutsch")
        fr_locale = Locale(id=4, shortcut="fr", name="Le français")

        DBSession.add(ru_locale)
        DBSession.add(en_locale)
        DBSession.add(de_locale)
        DBSession.add(fr_locale)

        # creating base groups
        can_create_dictionaries = BaseGroup(name="can_create_dictionaries", readable_name="Can create dictionaries")
        can_create_languages = BaseGroup(name="can_create_languages", readable_name="Can create languages")
        can_edit_languages = BaseGroup(name="can_edit_languages", readable_name="Can edit languages")
        can_delete_languages = BaseGroup(name="can_delete_languages", readable_name="Can delete languages")
        can_create_groups = BaseGroup(name="can_create_groups", readable_name="Can create groups")
        can_create_organizations = BaseGroup(name="can_create_organizations", readable_name="Can create organizations")
        can_edit_organizations = BaseGroup(name="can_edit_organizations", readable_name="Can edit organizations")
        can_edit_users = BaseGroup(name="can_edit_users", readable_name="Can edit users")
        can_change_dictionary_info = BaseGroup(name="can_change_dictionary_info", readable_name="Can change dictionary info")
        can_add_words = BaseGroup(name="can_add_words", readable_name="Can add words")
        can_set_defaults = BaseGroup(name="can_set_defaults", readable_name="Can set default entries for publication")
        can_publish = BaseGroup(name="can_publish", readable_name="Can publish dictionaries")

        DBSession.add(can_create_dictionaries)
        DBSession.add(can_create_languages)
        DBSession.add(can_edit_languages)
        DBSession.add(can_delete_languages)
        DBSession.add(can_create_groups)
        DBSession.add(can_create_organizations)
        DBSession.add(can_edit_organizations)
        DBSession.add(can_edit_users)
        DBSession.add(can_change_dictionary_info)
        DBSession.add(can_add_words)
        DBSession.add(can_set_defaults)
        DBSession.add(can_publish)
        DBSession.flush()

        # creating admin groups

        adm_can_create_dictionaries = Group(base_group_id=can_create_dictionaries.id, subject="ANY")
        adm_can_create_languages = Group(base_group_id=can_create_languages.id, subject="ANY")
        adm_can_edit_languages = Group(base_group_id=can_edit_languages.id, subject="ANY")
        adm_can_delete_languages = Group(base_group_id=can_delete_languages.id, subject="ANY")
        adm_can_create_groups = Group(base_group_id=can_create_groups.id, subject="ANY")
        adm_can_create_organizations = Group(base_group_id=can_create_organizations.id, subject="ANY")
        adm_can_edit_organizations = Group(base_group_id=can_edit_organizations.id, subject="ANY")
        adm_can_edit_users = Group(base_group_id=can_edit_users.id, subject="ANY")
        adm_can_change_dictionary_info = Group(base_group_id=can_change_dictionary_info.id, subject="ANY")
        adm_can_add_words = Group(base_group_id=can_add_words.id, subject="ANY")
        adm_can_set_defaults = Group(base_group_id=can_set_defaults.id, subject="ANY")
        adm_can_publish = Group(base_group_id=can_publish.id, subject="ANY")

        DBSession.add(adm_can_create_dictionaries)
        DBSession.add(adm_can_create_languages)
        DBSession.add(adm_can_edit_languages)
        DBSession.add(adm_can_delete_languages)
        DBSession.add(adm_can_create_groups)
        DBSession.add(adm_can_create_organizations)
        DBSession.add(adm_can_edit_organizations)
        DBSession.add(adm_can_edit_users)
        DBSession.add(adm_can_change_dictionary_info)
        DBSession.add(adm_can_add_words)
        DBSession.add(adm_can_set_defaults)
        DBSession.add(adm_can_publish)