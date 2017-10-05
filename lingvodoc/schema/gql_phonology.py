import graphene

from lingvodoc.utils.phonology import phonology

class PerformPhonology(graphene.Mutation):
    class Arguments:
        perspective_id = graphene.List(graphene.Int)
        limit = graphene.Int()
        limit_exception = graphene.Int()
        limit_no_vowel = graphene.Int()
        limit_result = graphene.Int()
        group_by_description = graphene.Boolean()
        only_first_translation = graphene.Boolean()
        vowel_selection = graphene.String()
        maybe_tier_list = graphene.Boolean()
        maybe_tier_set = graphene.Boolean()
        synchronous = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        perspective_cid, perspective_oid = args.get('perspective_id')
        limit = args.get('limit')
        limit_exception = args.get('limit_exception')
        limit_no_vowel = args.get('limit_no_vowel')
        limit_result = args.get('limit_result')
        group_by_description = args.get('group_by_description')
        only_first_translation = args.get('only_first_translation')
        vowel_selection = args.get('vowel_selection')
        maybe_tier_list = args.get('maybe_tier_list')
        maybe_tier_set = args.get('maybe_tier_set')
        synchronous = args.get('synchronous')

        locale_id = info.context.get('locale_id')
        request = info.context.get('request')
        phonology(request, group_by_description, only_first_translation, perspective_cid, perspective_oid,
                  synchronous, vowel_selection, maybe_tier_list, maybe_tier_set, limit,
                  limit_exception, limit_no_vowel, limit_result, locale_id)

        return PerformPhonology(triumph=True)