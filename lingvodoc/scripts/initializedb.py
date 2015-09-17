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
    Language,
    Locale,
    BaseGroup,
    Group,
    Dictionary,
    DictionaryPerspective,
    Client
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
        # Creating global administrator
        admin_account = DBSession.query(User).filter_by(login=accounts['administrator_login']).first()
        if not admin_account:
            print("Admin record not found, initializing")
            admin_account = User(id=1,
                                 login=accounts['administrator_login'],
                                 name="Администратор",
                                 intl_name="System Administrator",
                                 )
            pwd = Passhash(password=accounts['administrator_password'])
            admin_account.password = pwd
            client = Client(id=1,
                            user_id=admin_account.id)
            DBSession.add(pwd)
            DBSession.add(admin_account)
            DBSession.add(client)

            DBSession.flush()
        # Initializing base locales and languages
        russian_language = Language(object_id=1,
                                    client_id=1,
                                    translation_string="Russian language")
        english_language = Language(object_id=2,
                                    client_id=1,
                                    translation_string="English language")
        finnish_language = Language(object_id=3,
                                    client_id=1,
                                    translation_string="Finnish language")
        french_language = Language(object_id=4,
                                   client_id=1,
                                   translation_string="French language")
        german_language = Language(object_id=5,
                                   client_id=1,
                                   translation_string="German language")
        for lang in [russian_language, english_language, finnish_language, french_language, german_language]:
            DBSession.add(lang)

        # # creating base locales
        ru_locale = Locale(id=1, parent_client_id=1, parent_object_id=1, shortcut="ru", intl_name="Russian (Русский)")
        en_locale = Locale(id=2, parent_client_id=1, parent_object_id=2, shortcut="en", intl_name="English")
        fi_locale = Locale(id=3, parent_client_id=1, parent_object_id=3, shortcut="fi", intl_name="Finnish (Suomi)")
        fr_locale = Locale(id=4, parent_client_id=1, parent_object_id=4, shortcut="fr", intl_name="French (Français)")
        de_locale = Locale(id=5, parent_client_id=1, parent_object_id=5, shortcut="de", intl_name="German (Deutsch)")

        for locale in [ru_locale, en_locale, fi_locale, fr_locale, de_locale]:
            DBSession.add(locale)

        base_groups = []
# authenticated
        base_groups.append(BaseGroup(translation_string="Can create dictionaries",
                                     subject="dictionary",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="language",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="organization",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="translation_string",
                                     action="create"))
# owner
        base_groups.append(BaseGroup(translation_string="",
                                     subject="languages",
                                     action="edit"))
        # only if orphaned
        base_groups.append(BaseGroup(translation_string="",
                                     subject="languages",
                                     action="delete"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="edit_user",
                                     action="edit"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="dictionary",
                                     action="edit"))

# owner + assigned
        base_groups.append(BaseGroup(translation_string="",
                                     subject="role",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="role",
                                     action="delete"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="organization",
                                     action="edit"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="perspective",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="perspective",
                                     action="edit"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="lexical_entries_and_entities",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="approve_entities",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="approve_entities",
                                     action="delete"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="perspective",
                                     action="edit"))
        base_groups.append(BaseGroup(translation_string="",
                                     subject="merge",
                                     action="create"))

        for base_group in base_groups:
            DBSession.add(base_group)

        DBSession.flush()






        # # creating base groups
        # can_create_dictionaries = BaseGroup(name = "can_create_dictionaries", readable_name="Can create dictionaries")
        # can_create_languages = BaseGroup(name="can_create_languages", readable_name="Can create languages")
        # can_edit_languages = BaseGroup(name="can_edit_languages", readable_name="Can edit languages")
        # can_delete_languages = BaseGroup(name="can_delete_languages", readable_name="Can delete languages")
        # can_create_groups = BaseGroup(name="can_create_groups", readable_name="Can create groups")
        # can_create_organizations = BaseGroup(name="can_create_organizations", readable_name="Can create organizations")
        # can_edit_organizations = BaseGroup(name="can_edit_organizations", readable_name="Can edit organizations")
        # can_edit_users = BaseGroup(name="can_edit_users", readable_name="Can edit users")
        # can_change_dictionary_info = BaseGroup(name="can_change_dictionary_info", readable_name="Can change dictionary info")
        # can_invite_collaborators = BaseGroup(name="can_invite_collaborators", readable_name="Can invite collaborators")
        # can_add_words = BaseGroup(name="can_add_words", readable_name="Can add words")
        # can_delete_words = BaseGroup(name="can_delete_words", readable_name="Can delete words")
        # can_set_defaults = BaseGroup(name="can_set_defaults", readable_name="Can set default entries for publication")
        # can_publish = BaseGroup(name="can_publish", readable_name="Can publish dictionaries")
        #
        # DBSession.add(can_create_dictionaries)
        # DBSession.add(can_create_languages)
        # DBSession.add(can_edit_languages)
        # DBSession.add(can_delete_languages)
        # DBSession.add(can_create_groups)
        # DBSession.add(can_create_organizations)
        # DBSession.add(can_edit_organizations)
        # DBSession.add(can_edit_users)
        # DBSession.add(can_change_dictionary_info)
        # DBSession.add(can_invite_collaborators)
        # DBSession.add(can_add_words)
        # DBSession.add(can_delete_words)
        # DBSession.add(can_set_defaults)
        # DBSession.add(can_publish)
        # DBSession.flush()
        #
        # # creating admin groups
        #
        # adm_can_create_dictionaries = Group(base_group_id=can_create_dictionaries.id, subject="ANY")
        # adm_can_create_languages = Group(base_group_id=can_create_languages.id, subject="ANY")
        # adm_can_edit_languages = Group(base_group_id=can_edit_languages.id, subject="ANY")
        # adm_can_delete_languages = Group(base_group_id=can_delete_languages.id, subject="ANY")
        # adm_can_create_groups = Group(base_group_id=can_create_groups.id, subject="ANY")
        # adm_can_create_organizations = Group(base_group_id=can_create_organizations.id, subject="ANY")
        # adm_can_edit_organizations = Group(base_group_id=can_edit_organizations.id, subject="ANY")
        # adm_can_edit_users = Group(base_group_id=can_edit_users.id, subject="ANY")
        # adm_can_change_dictionary_info = Group(base_group_id=can_change_dictionary_info.id, subject="ANY")
        # adm_can_invite_collaborators = Group(base_group_id=can_invite_collaborators.id, subject="ANY")
        # adm_can_add_words = Group(base_group_id=can_add_words.id, subject="ANY")
        # adm_can_delete_words = Group(base_group_id=can_delete_words.id, subject="ANY")
        # adm_can_set_defaults = Group(base_group_id=can_set_defaults.id, subject="ANY")
        # adm_can_publish = Group(base_group_id=can_publish.id, subject="ANY")
        #
        # DBSession.add(adm_can_create_dictionaries)
        # DBSession.add(adm_can_create_languages)
        # DBSession.add(adm_can_edit_languages)
        # DBSession.add(adm_can_delete_languages)
        # DBSession.add(adm_can_create_groups)
        # DBSession.add(adm_can_create_organizations)
        # DBSession.add(adm_can_edit_organizations)
        # DBSession.add(adm_can_edit_users)
        # DBSession.add(adm_can_change_dictionary_info)
        # DBSession.add(adm_can_invite_collaborators)
        # DBSession.add(adm_can_add_words)
        # DBSession.add(adm_can_delete_words)
        # DBSession.add(adm_can_set_defaults)
        # DBSession.add(adm_can_publish)
        # DBSession.flush()
        #
        # admin_account.groups = [adm_can_create_dictionaries,
        #                         adm_can_create_languages,
        #                         adm_can_edit_languages,
        #                         adm_can_delete_languages,
        #                         adm_can_create_groups,
        #                         adm_can_create_organizations,
        #                         adm_can_edit_organizations,
        #                         adm_can_edit_users,
        #                         adm_can_change_dictionary_info,
        #                         adm_can_invite_collaborators,
        #                         adm_can_add_words,
        #                         adm_can_delete_words,
        #                         adm_can_set_defaults,
        #                         adm_can_publish]
        # dictionary = Dictionary(object_id=1,client_id=1, name = 'idk')
        # DBSession.add(dictionary)
        # DBSession.flush()
        # persp = DictionaryPerspective(object_id=1,client_id=1, parent_object_id=1,parent_client_id=1, name='persp')
        # DBSession.add(persp)
        # DBSession.flush()
        # new_user = User(login='test', default_locale_id = 1)
        # new_pass = Passhash(password='pass')
        # DBSession.add(new_pass)
        # new_user.password = new_pass
        # DBSession.add(new_user)
        # new_user2 = User(login='test2', default_locale_id = 1)
        # new_pass = Passhash(password='pass')
        # DBSession.add(new_pass)
        # new_user2.password = new_pass
        # DBSession.add(new_user2)
        # DBSession.flush()
        # new_client = Client(id=1, user=new_user)
        # DBSession.add(new_client)
        # DBSession.flush()