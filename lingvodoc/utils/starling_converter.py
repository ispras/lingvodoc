import collections
import transaction
import datetime
from collections import defaultdict
from itertools import chain
import graphene
from lingvodoc.models import (
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession,
    Client as dbClient,
    Language as dbLanguage,
    User as dbUser,
    Field as dbField,
    DictionaryPerspective as dbDictionaryPerspective,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    Organization as dbOrganization,
    UserBlobs as dbUserBlobs,
    LexicalEntry as dbLexicalEntry
)
from lingvodoc.utils.creation import create_gists_with_atoms, update_metadata, add_user_to_group
from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CommonFieldsComposite,
    StateHolder,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError,
    ObjectVal,
    acl_check_by_id,
    LingvodocID,
    UserAndOrganizationsRoles
)

from lingvodoc.utils import statistics
from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary,
                                      create_dictionary_persp_to_field,
                                      edit_role)
from lingvodoc.utils.search import translation_gist_search
from lingvodoc.utils.creation import create_entity, create_lexicalentry


def translation_gist_search_all(searchstring, gist_type):
        translationatom = DBSession.query(dbTranslationAtom) \
            .join(dbTranslationGist). \
            filter(dbTranslationAtom.content == searchstring,
                   dbTranslationAtom.locale_id == 2,
                   dbTranslationGist.type == gist_type) \
            .first()

        if translationatom and translationatom.parent:
            translationgist = translationatom.parent
            return translationgist

def get_field_id_by_name(field_name, gist_type="Service"):
    # TODO: move to utils
    gist = translation_gist_search_all(field_name, gist_type)
    if gist:
        field = DBSession.query(dbField).filter_by(translation_gist_client_id=gist.client_id, translation_gist_object_id=gist.object_id).first()
        return (field.client_id, field.object_id)

def csv_to_columns(path):
    import csv
    csv_file = open(path, "rb").read().decode("utf-8", "ignore")
    lines = [x.rstrip().split('|') for x in csv_file.split("\n")]
    column_dict = dict() #collections.OrderedDict()
    columns = lines[0]
    #lines.pop()
    j = 0
    for line in lines:
        i = 0
        if not j:
            j=1
            continue
        for column in columns:
            if not column in column_dict:
                column_dict[column] = []
            column_dict[column].append(line[i])
            i += 1
    return column_dict

from lingvodoc.scripts.convert_five_tiers import convert_all
from lingvodoc.queue.celery import celery


def graphene_to_dicts(starling_dictionaries):
    result = []
    for dictionary in starling_dictionaries:
        dictionary = dict(dictionary)
        fmap = [dict(x) for x in dictionary.get("field_map")]
        dictionary["field_map"] = fmap
        result.append(dictionary)

    return result

def convert(info, starling_dictionaries):
    ids = [info.context["client_id"], None]
    locale_id = info.context.get('locale_id')
    #convert_start.delay(ids, graphene_to_dicts(starling_dictionaries))
    convert_start(ids, graphene_to_dicts(starling_dictionaries))
    return True

#@celery.task
def convert_start(ids, starling_dictionaries):
    if True:
    #with transaction.manager:
        #starling_dictionaries=fake_starling


        persp_fake_ids = dict()
        etymology_field_id = get_field_id_by_name("Etymology", "Field")
        relation_field_id = get_field_id_by_name("Relation", "Field")



        dictionary_id_links = collections.defaultdict(list)

        fake_id_dict = {}
        fake_link_to_field= {}#collections.defaultdict(list)
        for starling_dictionary in starling_dictionaries:
            fields = starling_dictionary.get("field_map")
            blob_id_as_fake_id = starling_dictionary.get("blob_id")
            for field in fields:
                link_fake_id = field.get("link_fake_id")
                if not link_fake_id:
                    continue
                dictionary_id_links[tuple(blob_id_as_fake_id)].append(tuple(link_fake_id))
                #
                fake_link_to_field[tuple(link_fake_id)] = [x for x in fields if x["starling_type"] == 2]

        # crutch
        #fake_blob_to_fields = {}
        for starling_dictionary in starling_dictionaries:
            fields = starling_dictionary.get("field_map")
            blob_id = tuple(starling_dictionary.get("blob_id"))
            if blob_id in fake_link_to_field:
                old_fields = fake_link_to_field[blob_id]
                for old_field in old_fields:
                    fake_field = old_field.copy()
                    #del fake_field["link_fake_id"]
                    fake_field["starling_type"] = 4
                    if fake_field["field_id"] in [x.get("field_id") for x in fields]:
                        continue
                    fields.append(fake_field)
                    #fake_blob_to_fields[blob_id] = fields
                    starling_dictionary["field_map"] = fields
        #

        blob_to_perspective = dict()
        #perspective_to_collist = {}
        perspective_column_dict = {}
        # getting all values
        #persp_to_starcolumns = dict()

        # all_le = []
        all_entities = []
        persp_to_lexentry = collections.defaultdict(dict)
        copy_field_dict = collections.defaultdict(dict)
        keep_field_dict = collections.defaultdict(dict)
        link_field_dict = collections.defaultdict(dict)
        for starling_dictionary in starling_dictionaries:
            blob_id = tuple(starling_dictionary.get("blob_id"))
            blob = DBSession.query(dbUserBlobs).filter_by(client_id=blob_id[0], object_id=blob_id[1]).first()
            column_dict = csv_to_columns(blob.real_storage_path)





            atoms_to_create = starling_dictionary.get("translation_atoms")
            #translation_gist_id = starling_dictionary.get("translation_gist_id")
            dictionary_translation_gist_id = create_gists_with_atoms(atoms_to_create, None, ids)
            parent_id = starling_dictionary.get("parent_id")

            dbdictionary_obj = create_dbdictionary(id=ids,
                                                   parent_id=parent_id,
                                                   translation_gist_id=dictionary_translation_gist_id)
            atoms_to_create = [{"locale_id": 2, "content": "PERSPECTIVE_NAME"}] #starling_dictionary.get("perspective_atoms")
            #persp_translation_gist_id = starling_dictionary.get("translation_gist_id")
            persp_translation_gist_id = create_gists_with_atoms(atoms_to_create, None, ids)
            dictionary_id = [dbdictionary_obj.client_id, dbdictionary_obj.object_id]
            new_persp = create_perspective(id=ids,
                                    parent_id=dictionary_id,  # TODO: use all object attrs
                                    translation_gist_id=persp_translation_gist_id
                                    )
            perspective_column_dict[blob_id] = column_dict
            blob_to_perspective[blob_id] = new_persp
            perspective_id = [new_persp.client_id, new_persp.object_id]
            fields = starling_dictionary.get("field_map")
            starlingname_to_column = collections.OrderedDict()

            position_counter = 1

            # perspective:field_id


            for field in fields:
                starling_type = field.get("starling_type")
                field_id = tuple(field.get("field_id"))
                starling_name = field.get("starling_name")
                if starling_type == 1:
                    persp_to_field = create_dictionary_persp_to_field(id=ids,
                                     parent_id=perspective_id,
                                     field_id=field_id,
                                     upper_level=None,
                                     link_id=None,
                                     position=position_counter
                                     )
                    position_counter += 1
                    starlingname_to_column[starling_name] = field_id
                    keep_field_dict[blob_id][field_id] = starling_name
                elif starling_type == 2:
                    # copy
                    persp_to_field = create_dictionary_persp_to_field(id=ids,
                                     parent_id=perspective_id,
                                     field_id=field_id,
                                     upper_level=None,
                                     link_id=None,
                                     position=position_counter
                                     )
                    position_counter += 1
                    starlingname_to_column[starling_name] = field_id
                    copy_field_dict[blob_id][field_id] = starling_name
                elif starling_type == 4:
                    persp_to_field = create_dictionary_persp_to_field(id=ids,
                                     parent_id=perspective_id,
                                     field_id=field_id,
                                     upper_level=None,
                                     link_id=None,
                                     position=position_counter
                                     )
                    position_counter += 1
                    #starlingname_to_column[starling_name] = field_id
                    #copy_field_dict[blob_id][field_id] = starling_name


            add_etymology = starling_dictionary.get("add_etymology")
            if add_etymology:
                persp_to_field = create_dictionary_persp_to_field(id=ids,
                                 parent_id=perspective_id,
                                 field_id=etymology_field_id,
                                 upper_level=None,
                                 link_id=None,
                                 position=position_counter
                                 )
                position_counter += 1
                #starlingname_to_column["ETYMOLOGY_PERSPECTIVE_TO_FIELD"] = etymology_field_id
            persp_to_field = create_dictionary_persp_to_field(id=ids,
                     parent_id=perspective_id,
                     field_id=relation_field_id,
                     upper_level=None,
                     link_id=None,
                     position=position_counter
                     )
            #starlingname_to_column["DIRECT_LINK_PERSPECTIVE_TO_FIELD"] = relation_field_id
            fields_marked_as_links = [x.get("starling_name") for x in fields if x.get("starling_type") == 3]
            link_field_dict[blob_id] = fields_marked_as_links


            # blob_link -> perspective_link
            csv_data = column_dict# perspective_column_dict[tuple(blob_id)]
            collist = list(starlingname_to_column)
            le_list = []

            for numb in csv_data["NUMBER"]:#range(0, int(csv_data["NUMBER"][-1])):#csv_data["NUMBER"]:
                numb = int(numb)
                #lexentr = create_lexicalentry(ids, perspective_id, save_object=False)
                lexentr = dbLexicalEntry(object_id=ids[1], client_id=ids[0], parent_client_id=perspective_id[0],
                            parent_object_id=perspective_id[1])
                le_list.append(lexentr)
                persp_to_lexentry[blob_id][numb] = lexentr
            #DBSession.bulk_save_objects(le_list)
            for le in le_list:
                DBSession.add(le)
            DBSession.flush()

            i = 0
            entities_list = []
            for lexentr in le_list:

                #########
                for starling_column_name in starlingname_to_column:
                    field_id = starlingname_to_column[starling_column_name]
                    col_data = csv_data[starling_column_name][i]
                    new_ent = create_entity(id=ids,
                        parent_id=[lexentr.client_id, lexentr.object_id],
                        additional_metadata=None,
                        field_id=field_id,
                        self_id=None,
                        link_id=None, #
                        locale_id=2,
                        filename=None,
                        content=col_data,
                        registry=None,
                        request=None,
                        save_object=False)
                    entities_list.append(new_ent)
                i+=1
            #DBSession.bulk_save_objects(entities_list)
            for ent in entities_list:
                DBSession.add(ent)
            DBSession.flush()
            ##########
        for starling_dictionary in starling_dictionaries:
            blob_id = tuple(starling_dictionary.get("blob_id"))
            if blob_id not in dictionary_id_links:
                continue
            persp = blob_to_perspective[blob_id]
            copy_field_to_starlig = copy_field_dict[blob_id]
            for blob_link in dictionary_id_links[blob_id]:
                #links creation
                le_links = {}
                for num_col in link_field_dict[blob_id]:
                    #if not num_col:
                    #    continue
                    link_numbers = [int(x) for x in perspective_column_dict[blob_id][num_col]]
                    #link_numbers = [int(x) for x in link_field_dict[blob_id]]
                    for link_n in link_numbers:
                        #if not link_n:
                        #    continue
                        # TODO: fix
                        if not link_n:# link_n+1 not in persp_to_lexentry[blob_link]:
                            continue
                        link_lexical_entry = persp_to_lexentry[blob_link][link_n]
                        lexical_entry = persp_to_lexentry[blob_id][link_n]
                        perspective = blob_to_perspective[blob_link]
                        new_ent = create_entity(id=ids,
                            parent_id=[lexical_entry.client_id, lexical_entry.object_id],
                            additional_metadata={"link_perspective_id":[perspective.client_id, perspective.object_id]},
                            field_id=relation_field_id,
                            self_id=None,
                            link_id=[link_lexical_entry.client_id, link_lexical_entry.object_id], #
                            locale_id=2,
                            filename=None,
                            content=None,
                            registry=None,
                            request=None,
                            save_object=True)
                        #all_entities.append(new_ent)
                        le_links[(lexical_entry.client_id, lexical_entry.object_id)] = (link_lexical_entry.client_id, link_lexical_entry.object_id)


                #

                for field_id in copy_field_to_starlig: # copy_field_dict[blob_id]
                    starling_field = copy_field_to_starlig[field_id]

                    # if field doesn`t exist raise error
                    #for copy_field in copy_field_dict[blob_id]:
                        #if not copy_field in copy_field_dict[blob_link]:
                        #    raise ResponseError(message="%s not found in %s dict" % (str(copy_field), blob_link)  )
                        # get field_id entities from csv
                    word_list = perspective_column_dict[blob_id][starling_field]

                    i = 1
                    for word in word_list:
                        # TODO: fix
                        if not i in  persp_to_lexentry[blob_link]:
                            continue
                        lexical_entry = persp_to_lexentry[blob_id][i]
                        if not (lexical_entry.client_id, lexical_entry.object_id) in le_links:
                            i+=1
                            continue
                        link_lexical_entry = le_links[(lexical_entry.client_id, lexical_entry.object_id)]#persp_to_lexentry[blob_link][i+1]
                        new_ent = create_entity(id=ids,
                            parent_id=link_lexical_entry,
                            additional_metadata=None,
                            field_id=field_id,
                            self_id=None,
                            link_id=None, #
                            locale_id=2,
                            filename=None,
                            content=word,
                            registry=None,
                            request=None,
                            save_object=True)
                        #all_entities.append(new_ent)
                        i+=1
