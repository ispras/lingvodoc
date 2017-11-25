
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
    Organization as dbOrganization
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

fake_starling =  {
	"starling_dictionaries": [
		{
            "translation_atoms":[{"locale_id":2, "content":"DICT uzbek"}],
			"parent_id": [
				1,
				205
			],
			"translation_gist_id": [
				1,
				159
			],
			"perspective_atoms": [{"locale_id":2, "content":"uzbek"}],
			"field_map": [
				{
					"starling_name": "PROTO",
					"starling_type": 1,
					"field_id": [
						66,
						6
					]
				}
			],
			"add_etymology": 1,
			"blob_id": [1197,
     10]
		},
		{
            "translation_atoms":[{"locale_id":2, "content":"DICT NE uzbek"}],
			"parent_id": [
				840,
				6
			],
			"translation_gist_id": [
				1,
				26
			],
			"perspective_atoms": [{"locale_id":2, "content":"ne uzbek"}],
			"field_map": [
				{
					"starling_name": "PROTO",
					"starling_type": 1,
					"field_id": [
						66,
						6
					]
				}
			],
			"add_etymology": 1,
			"blob_id": [ 1197,
     11]
		}
	]
}

class StarlingCsvParser:
    def __init__(self):
        pass

#create_gists_with_atoms
def convert(info, starling_dictionaries):
    #starling_dictionaries=fake_starling
    ids = [info.context["client_id"], None]
    locale_id = info.context.get('locale_id')

    persp_fake_ids = dict()
    # getting all values
    for starling_dictionary in starling_dictionaries:

        atoms_to_create = starling_dictionary.get("translation_atoms")
        translation_gist_id = starling_dictionary.get("translation_gist_id")
        dictionary_translation_gist_id = create_gists_with_atoms(atoms_to_create, translation_gist_id, ids)
        parent_id = starling_dictionary.get("parent_id")

        dbdictionary_obj = create_dbdictionary(id=ids,
                                               parent_id=parent_id,
                                               translation_gist_id=dictionary_translation_gist_id)
        atoms_to_create = starling_dictionary.get("perspective_atoms")
        persp_translation_gist_id = starling_dictionary.get("translation_gist_id")
        persp_translation_gist_id = create_gists_with_atoms(atoms_to_create, persp_translation_gist_id, ids)
        dictionary_id = [dbdictionary_obj.client_id, dbdictionary_obj.object_id]
        new_persp = create_perspective(id=ids,
                                parent_id=dictionary_id,  # TODO: use all object attrs
                                translation_gist_id=persp_translation_gist_id
                                )
        perspective_id = [new_persp.client_id, new_persp.object_id]
        fields = starling_dictionary.get("field_map")
        position_counter = 1
        for field in fields:
            starling_name = field.get("starling_name")
            starling_type = field.get("starling_type")
            field_id = field.get("field_id")
            if starling_type == 1:

                persp_to_field = create_dictionary_persp_to_field(id=ids,
                                 parent_id=perspective_id,
                                 field_id=field_id,
                                 upper_level=None,
                                 link_id=None,
                                 position=position_counter
                                 )
                position_counter += 1
            elif starling_type == 2:
                pass
            elif starling_type == 3:
                pass


#     starling_name = graphene.String(required=True)
#     starling_type = graphene.Int(required=True)
#     field_id = LingvodocID(required=True)
#     fake_id = graphene.String()
#     link_fake_id = graphene.String()
#
# class StarlingDictionary(graphene.InputObjectType):
#     blob_id = LingvodocID()
#     parent_id = LingvodocID(required=True)
#     dictionary_gist_id = LingvodocID()
#     dictionary_atoms = graphene.List(ObjectVal)
#     translation_gist_id = LingvodocID()
#     translation_atoms = graphene.List(ObjectVal)
#     field_map = graphene.List(StarlingField, required=True)
#     add_etymology = graphene.Boolean(required=True)