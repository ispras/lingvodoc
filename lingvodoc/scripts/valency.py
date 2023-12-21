
__authors__ = [
    'Pavel Grashchenkov',
    'Ivan Beloborodov']

from collections import Counter, defaultdict

import copy
import json
import io
import math
import re
import sys

def corpus_to_sentences(corpus_data_list):

    s_ends = {'.', '!',  '?', '...', '?!', '...»'}

    sentence_data_list = []

    for i in copy.deepcopy(corpus_data_list):

        for p in i['paragraphs']:

            sentences = []
            sent = []

            for t_index, t in enumerate(p['tokens']):

                t = {k: v.strip() if isinstance(v, str) else v for k, v in t.items()}

                if t['token'] not in s_ends and t_index < len(p['tokens']) - 1:
                    sent.append(t)

                if (t['token'] in s_ends and t_index > 0 or
                    t['token'] not in s_ends and t_index == len(p['tokens']) - 1):

                    sent.append(t)
                    sentences.append(sent)
                    sent = []

            if len(sentences) > 0:
                p.update({'sentences': sentences})

            p.pop('tokens')
            p.pop('variants')

        sentence_data_list.append(i)

    return sentence_data_list

def corpus_to_arx(
    corpus_data_list,
    verbose_flag = False):

    lex_transl = []
    verbs = []

    for i in corpus_data_list:
        for p in i['paragraphs']:
            for t in p['tokens']:

                if len(t) <= 1:
                    continue

                t = {
                    k.strip() if isinstance(k, str) else k:
                        v.strip() if isinstance(v, str) else v
                    for k, v in t.items()}

                if 'gr' not in t:
                    continue

                grammar = t['gr'].split(',')

                if 'V' not in grammar:
                    continue

                transl = (
                    'I ' + t['trans_ru'] +
                    '; II ' + t['trans_ru2'] if 'trans_ru2' in t else t['trans_ru'])

                lex_transl.append(t['lex'].replace(' ', ''))
                tok_val_list = []
                for g in grammar:
                    if re.match(r'(with_)', g) or g == 'tr':
                        tok_val_list.append(g)
                tok_val_list.sort()
                verbs.append([t['lex'], tok_val_list if tok_val_list else [], transl])

    verbs_counted = {}

    f_dict = dict(Counter(lex_transl))

    for v in verbs:
        if v[0] in f_dict.keys():
            verbs_counted.update({v[0]: [f_dict[v[0]], v[1], v[2]]})
        elif verbose_flag:
            print(repr(v[0]))

    return verbs_counted

def sentence_instance_gen(
    token_list,
    additional_check_flag = True):

    cases = [
        'nom', 'acc', 'dat', 'ins', 'gen', 'abl', 'car', 'egr', 'el', 'ill', 'loc', 'prol', 'term',
        'cns', 'comp', 'com', 'lat', 'sim', 'par', 'ad', 'trans', 'allat', 'ab', 'in']

    lex_skip_set = {
        'какой', 'чисто', 'сё', 'минут'}

    v_ind = []

    for t_index, t in enumerate(token_list):

        if (len(t) > 1 and
           'gr' in t):

            grammar = t['gr'].split(',')

            if 'V' in grammar or 'VBLEX' in grammar or 'VBSER' in grammar:
                v_ind.append(t_index)

    for n, ind in enumerate(v_ind):

        lex = token_list[ind].get('lex')
        prev_v = v_ind[n - 1] + 1 if n > 0 else 0
        next_v = v_ind[n + 1] if n + 1 < len(v_ind) - 1 else len(token_list) - 1

        for r in range(max(prev_v, ind - 5), min(next_v, ind + 5) + 1):

            if (len(token_list[r]) <= 1 or
                'gr' not in token_list[r]):

                continue

            indent = ind - r

            # Two different 'acc0' because the second one is in Cyrillic.

            gram = (
                token_list[r]['gr']
                    .replace(' ', '')
                    .replace('acc0', 'acc')
                    .replace('асс0', 'acc')
                    .replace('sg.nom', 'sg,nom')
                    .split(','))

            if additional_check_flag:

                if not (
                    ('N' in gram or 'PRO' in gram) and
                    len(gram) > 1 and
                    'rel_n' not in gram and
                    'attr' not in gram and
                    'term' not in gram and
                    'adv' not in gram and
                    'app' not in gram and
                    token_list[r].get('lex') not in lex_skip_set):

                    continue

            try:
                cs = [cas for cas in cases if cas in gram][0]
            except IndexError:
                continue

            animacy = (
                'anim' in gram or
                'persn' in gram or
                'famn' in gram or
                'patrn' in gram or
                'supernat' in gram)

            yield lex, cs, indent, ind, r, animacy

def sentences_arx_to_valencies(
    sentence_data_list,
    arx_data_dict):

    verbs = []
    verb_case_dict = defaultdict(dict)

    cases = [
        'nom', 'acc', 'dat', 'ins', 'gen', 'abl', 'car', 'egr', 'el', 'ill', 'loc', 'prol', 'term',
        'cns', 'comp', 'com', 'lat', 'sim', 'par', 'ad', 'trans', 'allat', 'ab', 'in']

    case_template_list = [
        {'case': case, 'anim': 0, '5': 0, '4': 0, '3': 0, '2': 0, '1': 0, '-1': 0, '-2': 0, '-3': 0, '-4': 0, '-5': 0}
        for case in cases]

    for key, value in arx_data_dict.items():

        if key in verb_case_dict:
            raise NotImplementedError

        case_data = []
        case_dict = verb_case_dict[key]

        for case_template in case_template_list:

            case_c = copy.deepcopy(case_template)

            case_data.append(case_c)
            case_dict[case_c['case']] = case_c

        verb_data = {
            'lex': key,
            'trans_ru': value[2],
            'frequency': value[0],
            'cases': case_data}

        verbs.append(verb_data)

    for i in sentence_data_list:
        for p in i['paragraphs']:
            for s in p['sentences']:

                for lex, cs, indent, _, _, animacy in sentence_instance_gen(s):

                    case_dict = verb_case_dict.get(lex)

                    if not case_dict:
                        continue

                    case = case_dict.get(cs)

                    if not case:
                        continue

                    for k in case.keys():
                        if k not in ['case', 'anim'] and int(k) == indent:
                            case[k] += 1
                        elif k == 'anim' and animacy:
                            case[k] += 1

    return verbs

def count_weights(dist, direct, jsonfile_verbs, verb_di_case_stat, add_anim, select_best):

    output_dict = {}
    for verb in jsonfile_verbs:
#       print('VERB: ', verb['lex'], verb['trans_ru'], verb['frequency'])
        cases_ = {}
        for case in verb['cases']:
            k_rate = 0
            n = 0
            for k in case.keys():

                if verb_di_case_stat[case[k]] <= 0:
                    continue

                if k == 'case':
                    m = math.log(verb_di_case_stat['all_cases']/verb_di_case_stat[case[k]], 2)
    #                print('m\t', case[k], m)
                if k not in ['case', 'anim'] and int(k) > 0:
                    k_rate = k_rate + ((case[k])*m/(abs(int(k)) + dist))
                    n = n + case[k]
                elif k not in ['case', 'anim'] and int(k) < 0:
                    k_rate = k_rate + ((case[k])*m/(abs(int(k)) + dist + direct))
                    n = n + case[k]
            if add_anim:
                anim_n = int(case[k])
#                print('N, anim_n', n, anim_n)
                if chisquare([anim_n, n - anim_n])[1] < 0.01 and anim_n > (n - anim_n):
                    cases_.update({case['case']: {'score': k_rate, 'anim': '+'}})
                    print('^ANIMATE^')
                elif chisquare([anim_n, n - anim_n])[1] < 0.01 and anim_n < (n - anim_n):
                    cases_.update({case['case']: {'score': k_rate, 'anim': '-'}})
                elif chisquare([anim_n, n - anim_n])[1] > 0.01:
                    cases_.update({case['case']: {'score': k_rate, 'anim': ''}})
            else:
                cases_.update({case['case']: k_rate})
        
        arg_str = []
        best_score = max(cases_.values())
        if select_best and verb['frequency'] > 10:
            if best_score > 0:
                nom_score = cases_['nom']
                best_arg = list(cases_.keys())[list(cases_.values()).index(best_score)]
                arg_str.append(best_arg) if best_arg != 'nom' else arg_str
                for key, value in cases_.items():
                    if 0.9 < value/best_score < 1.1 and key != 'nom':
                        arg_str.append(key)
                if nom_score != 0 and len(arg_str) == 0:
                    for key, value in cases_.items():
                        if (0.7 < value/nom_score or value > nom_score) and key != 'nom' and value > 20:
                            arg_str.append(key)
            arg_str.remove('gen') if 'gen' in arg_str else arg_str
            arg_str.remove('car') if 'car' in arg_str else arg_str
            val_final = str(set(arg_str)) if len(set(arg_str)) > 0 else ''
            output_dict.update({verb['lex']: {'trans_ru': verb['trans_ru'], 'frequency': verb['frequency'], 'valency': val_final }})
#            print(list(set(arg_str)))
#            print(case['case'], k_rate)
        elif not select_best:
            output_dict.update({verb['lex']: {'trans_ru': verb['trans_ru'], 'frequency': verb['frequency'], 'cases': cases_ }})

    return output_dict

def sentences_valencies_to_result(
    sentence_data_list,
    valence_data_list,
    verbose_flag = False):

    cases = [
        'nom', 'acc', 'dat', 'ins', 'gen', 'abl', 'car', 'egr', 'el', 'ill', 'loc', 'prol', 'term',
        'cns', 'comp', 'com', 'lat', 'sim', 'par', 'ad', 'trans', 'allat', 'ab', 'in']

    case_counter = Counter()

    for i in sentence_data_list:
        for p in i['paragraphs']:
            for s in p['sentences']:
                for t in s:

                    if len(t) <= 1:
                        continue

                    t = {
                        k.strip() if isinstance(k, str) else k:
                            v.strip() if isinstance(v, str) else v
                        for k, v in t.items()}

                    if 'gr' not in t:
                        continue

                    gram = (
                        t['gr']
                            .replace(' ', '')
                            .replace('acc0', 'acc')
                            .replace('асс0', 'acc')
                            .replace('sg.nom', 'sg,nom')
                            .split(','))

                    try:
                        cs = [cas for cas in cases if cas in gram][0]
                    except IndexError:
                        continue

                    case_counter[cs] += 1

    case_counter['all_cases'] = sum(case_counter.values())

    if verbose_flag:
        print(case_counter)

    dist = 0
    direct = 5.4

    return (

        count_weights(
            dist,
            direct,
            valence_data_list,
            case_counter,
            add_anim = False,
            select_best = False))

def main_sentences(args):

    # python3 valency_extr.py sentences corpus.json sentences.json

    corpus_file_path, sentences_file_path = args[:2]

    with open(corpus_file_path, 'r', encoding = 'utf-8') as corpus_file:
        corpus_data = json.load(corpus_file)

    sentence_data = corpus_to_sentences(corpus_data)

    with open(sentences_file_path, 'w', encoding= 'utf-8') as sentences_file:
        json.dump(sentences_data, sentences_file, ensure_ascii = False, indent = 2)

def main_arx(args):

    # python3 valency_extr.py arx corpus.json arx.json

    corpus_file_path, arx_file_path = args[:2]

    with open(corpus_file_path, 'r', encoding = 'utf-8') as corpus_file:
        corpus_data = json.load(corpus_file)

    arx_data = corpus_to_arx(corpus_data, True)

    with open(arx_file_path, 'w', encoding = 'utf-8') as arx_file:
        json.dump(arx_data, arx_file, ensure_ascii = False, indent = 2)

def main_extract(args):

    # python3 valency_extr.py extract sentences.json arx.json valencies.json

    sentence_file_path, arx_file_path, valence_file_path = args[:4]

    with open(sentence_file_path, 'r', encoding = 'utf-8') as sentence_file:
        sentence_data = json.load(sentence_file)

    with open(arx_file_path, 'r', encoding = 'utf-8') as arx_file:
        arx_data = json.load(arx_file)

    valence_data = (
        sentences_arx_to_valencies(sentence_data, arx_data))

    with open(valence_file_path, 'w', encoding = 'utf-8') as valence_file:
        json.dump(valence_data, valence_file, ensure_ascii = False, indent = 2)

def main_probing(args):

    # python3 valency_extr.py probing sentences.json valencies.json result.json

    sentence_file_path, valence_file_path, result_file_path = args[:3]

    with open(sentence_file_path, 'r', encoding = 'utf-8') as sentence_file:
        sentence_data = json.load(sentence_file)

    with open(valence_file_path, 'r', encoding = 'utf-8') as valence_file:
        valence_data = json.load(valence_file)

    result_data = (

        sentences_valencies_to_result(
            sentence_data,
            valence_data,
            verbose_flag = True))

    with open(result_file_path, 'w', encoding = 'utf-8') as result_file:
        json.dump(result_data, result_file, ensure_ascii = False, indent = 2)

if __name__ == '__main__':

    arg_list = sys.argv[1:]

    if len(arg_list) <= 0:

        print('Please specify a command to execute.')

    elif arg_list[0] == 'sentences':

        main_sentences(arg_list[1:])

    elif arg_list[0] == 'arx':

        main_arx(arg_list[1:])

    elif arg_list[0] == 'extract':

        main_extract(arg_list[1:])

    elif arg_list[0] == 'probing':

        main_probing(arg_list[1:])

    else:

        print('Unknown command \'{}\'.'.format(arg_list[0]))

