
from pdb import set_trace as A

cases = ['prs',  # present tense – настоящее время
         'fut',  # future – будущее время
         'pst',  # past tense - прошедшее время
         '1pst',  # первое прошедшее время (очевидное)
         '2pst',  # второе прошедшее время (неочевидное)
         'inf',  # infinitive - инфинитив
         'imp',  # imperative – повелительное наклонение
         'cond',  # conditional – условное наклонение
         'sbjv',  # сослагательное наклонение
         'caus',  # causative – каузатив (понудительный залог)
         'refl',  # reflexive – возвратный
         'impers',  # impersonal – безличный (глагол)
         'iter',  # iterative – многократный (повторяющийся)
         'opt',  # optative (желательное наклонение)
         ]


def sentence_instance_gen(token_list):

    adv_ind = []
    # find all the positions of adverbs
    for t_index, t in enumerate(token_list):
        if len(t) > 1 and 'gr' in t:

            grammar = (
                t['gr'].lower()
                .replace(' ', '')
                .split(',')
            )

            if 'adv' in grammar:
                adv_ind.append(t_index)

    # find verbs for each position of adverbs
    for n, ind in enumerate(adv_ind):

        lex = token_list[ind].get('lex').strip().lower()
        prev_adv = adv_ind[n - 1] + 1 if n > 0 else 0
        next_adv = adv_ind[n + 1] if n + 1 < len(adv_ind) - 1 else len(token_list) - 1

        # iterate for all the verbs within +/- 5 words from the adverb
        for r in range(max(prev_adv, ind - 5), min(next_adv, ind + 5) + 1):

            # if no gross information
            if len(token_list[r]) <= 1 or 'gr' not in token_list[r]:
                continue

            indent = ind - r

            gram = (
                token_list[r]['gr'].lower()
                .replace(' ', '')
                .split(',')
            )

            if ('v' not in gram and
                'vblex' not in gram and
                'vbser' not in gram or
                'ptcp' in gram or
                'соnv' in gram):

                continue

            try:
                cs = [cas for cas in cases if cas in gram]
            except IndexError:
                continue

            yield lex, cs, indent, ind, r
