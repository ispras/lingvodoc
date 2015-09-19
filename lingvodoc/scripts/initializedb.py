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
    DictionaryPerspectiveField,
    Client,
    Email
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
        print("Admin record not found, initializing")
        admin_account = User(login=accounts['administrator_login'],
                             name="Администратор",
                             intl_name="System Administrator",
                             )
        pwd = Passhash(password=accounts['administrator_password'])
        email = Email(email="al@somestuff.ru")
        admin_account.password = pwd
        client = Client(user_id=admin_account.id)
        DBSession.add(pwd)
        DBSession.add(admin_account)
        email.user = admin_account
        DBSession.add(email)
        DBSession.add(client)

        DBSession.flush()
        # Initializing base locales and languages
        russian_language = Language(client_id=client.id,
                                    translation_string="Russian language")
        english_language = Language(client_id=client.id,
                                    translation_string="English language")
        finnish_language = Language(client_id=client.id,
                                    translation_string="Finnish language")
        french_language = Language(client_id=client.id,
                                   translation_string="French language")
        german_language = Language(client_id=client.id,
                                   translation_string="German language")
        for lang in [russian_language, english_language, finnish_language, french_language, german_language]:
            DBSession.add(lang)
        DBSession.flush()

        # # creating base locales
        ru_locale = Locale(parent_client_id=client.id, parent_object_id=russian_language.object_id, shortcut="ru", intl_name="Russian (Русский)")
        en_locale = Locale(parent_client_id=client.id, parent_object_id=english_language.object_id, shortcut="en", intl_name="English")
        fi_locale = Locale(parent_client_id=client.id, parent_object_id=finnish_language.object_id, shortcut="fi", intl_name="Finnish (Suomi)")
        fr_locale = Locale(parent_client_id=client.id, parent_object_id=french_language.object_id, shortcut="fr", intl_name="French (Français)")
        de_locale = Locale(parent_client_id=client.id, parent_object_id=german_language.object_id, shortcut="de", intl_name="German (Deutsch)")

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

        fake_dictionary = Dictionary(client_id=client.id,
                                     #object_id=1,
                                     name="Fake dictionary",
                                     state="Service")
        DBSession.add(fake_dictionary)
        DBSession.flush()

        dialeqt_template = DictionaryPerspective(client_id=client.id,
                                                 #object_id=1,
                                                 parent_client_id=fake_dictionary.client_id,
                                                 parent_object_id=fake_dictionary.object_id,
                                                 is_template=True,
                                                 state="Service",
                                                 name="Lingvodoc desktop version")
        DBSession.add(dialeqt_template)
        DBSession.flush()

        word_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                             #object_id=1,
                                             client_id=client.id,
                                             entity_type="Word", data_type="text", level="L1E", position=1,
                                             state="enabled")
        transcription_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                      #object_id=2,
                                                      client_id=client.id,
                                                      entity_type="Transcription", data_type="text",
                                                      level="L1E", position=2,
                                                      state="enabled")
        translation_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                    #object_id=3,
                                                    client_id=client.id,
                                                    entity_type="Translation",
                                                    data_type="text", level="L1E", position=3,
                                                    state="enabled")
        sound_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                              #object_id=4,
                                              client_id=client.id,
                                              entity_type="Sound", data_type="sound", level="L1E", position=4,
                                              state="enabled")
        for field in [word_ld, transcription_ld, translation_ld, sound_ld]:
            DBSession.add(field)
        DBSession.flush()
        praat_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                              entity_object_id=sound_ld.object_id, entity_client_id=sound_ld.client_id,
                                              #object_id=5,
                                              client_id=client.id,
                                              entity_type="Praat markup", data_type="markup", level="L2E", position=5,
                                              state="enabled")
        paradigm_word_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                      #object_id=6,
                                                      client_id=client.id,
                                                      entity_type="Paradigm word", data_type="text", level="L1E",
                                                      group="Paradigm", position=6,
                                                      state="enabled")
        paradigm_transcription_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                               #object_id=7,
                                                               client_id=client.id,
                                                               entity_type="Paradigm transcription", data_type="text",
                                                               level="L1E", position=7,
                                                               state="enabled")
        paradigm_translation_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                             #object_id=8,
                                                             client_id=client.id,
                                                             entity_type="Paradigm translation", data_type="text",
                                                             level="L1E", position=8,
                                                             state="enabled")
        paradigm_sound_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                       #object_id=9,
                                                       client_id=client.id,
                                                       entity_type="Paradigm sound", data_type="sound", level="L1E",
                                                       position=9,
                                                       state="enabled")
        for field in [praat_ld, paradigm_word_ld, paradigm_transcription_ld,
                      paradigm_translation_ld, paradigm_sound_ld]:
            DBSession.add(field)
        DBSession.flush()
        paradigm_praat_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                       entity_object_id=paradigm_sound_ld.object_id, entity_client_id=paradigm_sound_ld.client_id,
                                                       #object_id=10,
                                                       client_id=client.id,
                                                       entity_type="Paradigm Praat markup", data_type="markup",
                                                       level="L2E", position=10,
                                                       state="enabled")
        etymology_ld = DictionaryPerspectiveField(parent_object_id=dialeqt_template.object_id, parent_client_id=dialeqt_template.client_id,
                                                  #object_id=11,
                                                  client_id=client.id,
                                                  entity_type="Etymology", data_type="grouping_tag", level="GE",
                                                  position=11,
                                                  state="enabled")
        for field in [paradigm_praat_ld, etymology_ld]:
            DBSession.add(field)

        regular_dictionary_template = DictionaryPerspective(client_id=client.id,
                                                            #object_id=1,
                                                            parent_client_id=fake_dictionary.client_id,
                                                            parent_object_id=fake_dictionary.object_id,
                                                            is_template=True,
                                                            state="Service",
                                                            name="Regular dictionary")
        DBSession.add(regular_dictionary_template)
        DBSession.flush()

        # protoform_ordinary = DictionaryPerspectiveField(parent_object_id=2, parent_client_id=client.id,
        #                                                 object_id=, client_id=client.id,
        #                                                 entity_type="", data_type=, level=, position=,
        #                                                 state="enabled")
        # word_ordinary
        # transcription_ordinary
        # duration_1_vowel_ordinary
        # intensity_1_vowel_ordinary
        # native_speaker_ordinary
        # dialect_ordinary
        # translation_ld_ordinary
        # grammatical_form_ordinary
        # it_is_formed_from_ordinary
        # similarity_ordinary
        # the_page_ordinary
        # the_line_ordinary
        # the_head_ordinary
        # the_verse_ordinary
        # notes_ordinary
        # sound_ordinary
        # DBSession.flush()
        # praat_ordinary
        # paradigm_word_ordinary
        # paradigm_transcription_ordinary
        # paradigm_translation_ordinary
        # paradigm_sound_ordinary
        # DBSession.flush()
        # paradigm_praat_ordinary
        # etymology_ordinary
        #
        # gram_cat_morph = DictionaryPerspectiveField(parent_object_id=3, parent_client_id=client.id,
        #                                             object_id=, client_id=client.id,
        #                                             entity_type=, data_type=, level=, position=)
        # form_morph
        # transcription_morph
        # variants_morph
        # native_speaker_morph
        # text_morph
        # dialect_morph
        # in_combination_with_cat_morph
        # frequency_morph
        # number_of_an_affix_morph
        # the_page_morph
        # the_line_morph
        # notes_morph



