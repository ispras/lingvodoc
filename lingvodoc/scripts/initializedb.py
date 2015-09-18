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

# everyone
#         base_groups.append(BaseGroup(translation_string="Can view users",
#                                      subject="users",
#                                      action="view"))
#         base_groups.append(BaseGroup(translation_string="Can view organizations",
#                                      subject="dictionary",
#                                      action="view"))
#         base_groups.append(BaseGroup(translation_string="Can get dictionaries list",
#                                      subject="dictionary",
#                                      action="view"))
#         base_groups.append(BaseGroup(translation_string="Can get languages list",
#                                      subject="language",
#                                      action="view"))

# authenticated
        base_groups.append(BaseGroup(translation_string="Can create dictionaries",
                                     subject="dictionary",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="Can create languages",
                                     subject="language",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="Can create organizations",
                                     subject="organization",
                                     action="create"))
        base_groups.append(BaseGroup(translation_string="Can create translation strings",
                                     subject="translation_string",
                                     action="create"))
# owner
        base_groups.append(BaseGroup(translation_string="Can edit languages",
                                     subject="language",
                                     action="edit"))
        # only if orphaned
        base_groups.append(BaseGroup(translation_string="Can delete languages",
                                     subject="language",
                                     action="delete"))
        base_groups.append(BaseGroup(translation_string="Can edit user",
                                     subject="edit_user",
                                     action="edit"))
        base_groups.append(BaseGroup(translation_string="Can edit dictionary options",
                                     subject="dictionary",
                                     action="edit",
                                     dictionary_default=True))

# owner + assigned
        base_groups.append(BaseGroup(translation_string="Can get dictionary role list",
                                     subject="dictionary_role",
                                     action="view",
                                     dictionary_default=True))
        base_groups.append(BaseGroup(translation_string="Can get perspective role list",
                                     subject="perspective_role",
                                     action="view",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can view published lexical entries",
                                     subject="approve_entities",
                                     action="view",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can create dictionary roles and assign collaborators",
                                     subject="dictionary_role",
                                     action="create",
                                     dictionary_default=True))
        base_groups.append(BaseGroup(translation_string="Can create perspective roles and assign collaborators",
                                     subject="perspective_role",
                                     action="create",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can resign users from dictionary editors",
                                     subject="dictionary_role",
                                     action="delete",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can resign users from perspective editors",
                                     subject="perspective_role",
                                     action="delete",
                                     dictionary_default=True))
        base_groups.append(BaseGroup(translation_string="Can edit organization",
                                     subject="organization",
                                     action="edit",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can create perspectives",
                                     subject="perspective",
                                     action="create",
                                     dictionary_default=True))
        base_groups.append(BaseGroup(translation_string="Can edit perspective",
                                     subject="perspective",
                                     action="edit",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can create lexical entries",
                                     subject="lexical_entries_and_entities",
                                     action="create",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can approve lexical entries and publish",
                                     subject="approve_entities",
                                     action="create",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can deactivate lexical entries",
                                     subject="approve_entities",
                                     action="delete",
                                     perspective_default=True))
        base_groups.append(BaseGroup(translation_string="Can merge dictionaries and perspectives",
                                     subject="merge",
                                     action="create",
                                     perspective_default=True))

        for base_group in base_groups:
            DBSession.add(base_group)

        DBSession.flush()

        # admin groups with overrides
        adm_group_list = []
        for base_group in base_groups:
            adm_group_list.append(Group(base_group_id=base_group.id, subject_override=True))
            for adm_group in adm_group_list:
                DBSession.add(adm_group)
                admin_account.groups.append(adm_group)
        DBSession.flush()