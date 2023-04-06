
__authors__ = [
    'Mikhail Sokov',
    'Ivan Beloborodov']

import ast
import json
import sys
from textwrap import indent

#list_of_input_jsons = {'1':'UdmurtskyTexts.json','2':'KomiTexts.json'}
#list_of_input_jsons = {'1':'KomiTexts.json'}
list_of_input_jsons = {'1':'Komi_data.json','2':'Udmurtsky_data.json', '3':'Erzyansky_data.json', '4':'Mokshansky_data.json'}

def verbs_case_str(arx_data, lang, verb_list):

    s_ends = {'.', '!',  '?', '...', '?!', '...»'}
    s2=0

    id_sentence_dict = {
        sentence['id']: sentence
        for sentence in arx_data['sentence_list']}

    for instance in arx_data['instance_list']:

        item = id_sentence_dict[instance['sentence_id']]
        id = item['id']

        case_str = instance['case_str']

        sentence_exmp = ''
        sentence_exmp_arr = {}
        verb_descr = {}
        record_added = 0
        item3_i = 1
        trans_ru=''
        lex=instance['verb_lex']
        
        for item3 in item['tokens']:
            
            if item3_i == 1 or len(item3)==1 or item3['token'] in s_ends:
                sentence_exmp = sentence_exmp + item3['token']
            else:
                sentence_exmp = sentence_exmp + ' ' + item3['token'] 
                
            item3_i=item3_i+1
            if len(item3)>1:
                if (instance['verb_lex']==item3['lex']):
                    trans_ru = item3['trans_ru']
                    
                    if len(verb_list) == 0:
                        s2 = 1
                        #verb_descr = {}
                        verb_descr = lex, case_str
                        sentence_exmp_arr = {}                                 
                        verb_list[trans_ru] = {lang:{verb_descr:{s2:sentence_exmp_arr}}}
                        record_added = 1
                        
                    else: 
                        record_exist=0
                        if trans_ru in verb_list:
                            verb_descr_temp = {}
                            if lang in verb_list[trans_ru]:
                                verb_descr_temp0 = verb_list[trans_ru]
                                #new_k0={}
                                #for new_k0 in verb_descr_temp0.keys():
                                    #if new_k0 == lang:                                             
                                verb_descr_temp = verb_list[trans_ru][lang]
                                verb_descr = lex, case_str
                                if verb_descr in verb_descr_temp.keys():
                                    record_exist=1
                                if record_exist==0:
                                    s2=1                                          
                                    verb_descr_full = {}                                                    
                                    verb_descr = lex, case_str                                                   
                                    sentence_exmp_arr = {}       
                                    verb_descr_full = {verb_descr:{s2:sentence_exmp_arr}}
                                    verb_list[trans_ru][lang].update(verb_descr_full)
                                    record_added = 1
                            else:
                                s2 = 1
                                verb_descr = lex, case_str
                                sentence_exmp_arr = {}
                                verb_descr_full = {lang:{verb_descr:{s2:sentence_exmp_arr}}}                                 
                                verb_list[trans_ru].update(verb_descr_full)
                                record_added = 1
                        if (record_added == 0)&(record_exist==0):
                            s2 = 1
                            verb_descr = lex, case_str
                            sentence_exmp_arr = {}                                 
                            verb_list[trans_ru] = {lang:{verb_descr:{s2:sentence_exmp_arr}}}
                            record_added = 1
        
        sentence_recorded=0
        verb_descr = lex, case_str
        verb_list_lang_temp = verb_list[trans_ru][lang][verb_descr]
        for new_k in verb_list_lang_temp.items():
            if new_k[1] == sentence_exmp:
                sentence_recorded=1
        if sentence_recorded == 0:
            ss2 = len (verb_list[trans_ru][lang][verb_descr])
            if verb_list[trans_ru][lang][verb_descr][ss2] != {}:
                ss2=ss2+1                 
            sentence_exmp_arr[ss2] = sentence_exmp
            verb_list[trans_ru][lang][verb_descr][ss2] = sentence_exmp_arr[ss2]
                    
    return verb_list

if __name__ == '__main__':

    if len(sys.argv) > 1:
        list_of_input_jsons = ast.literal_eval(sys.argv[1])

    verb_list_final = {}
    for key0 in list_of_input_jsons.keys():
        with open(list_of_input_jsons[key0], 'r', encoding='utf-8') as arx_file:
            arx_data_temp = json.load(arx_file)
            verb_list_final = verbs_case_str(arx_data_temp, list_of_input_jsons[key0], verb_list_final)

    show_main_menu = 1

    while show_main_menu == 1:
        mode_selection = input('Please select: 1: Print out the complete database; 2: Print out the verbs + case_str; 3: Search for the verb; 4: Exit ')
        if mode_selection == '1' or mode_selection == '2':
            for key in verb_list_final.keys():
                print("Verb:",key)
                verb_descr_temp = verb_list_final[key]
                for key1 in verb_descr_temp.keys():
                    print("         Language:",key1)
                    #print(" Translation:",verb_descr_temp['Trans'])
                    
                    verb_descr_temp_case = verb_descr_temp[key1]
                    for key2 in verb_descr_temp_case.keys():
                        verb_descr_temp2 = verb_descr_temp_case[key2]
                        print("                 Case_Str:",key2)
                        #print("                         ",key2,"Verb&CaseStr:",verb_descr_temp2['case_str'])
                        if mode_selection == '1':
                            for key3 in verb_descr_temp2.keys():
                                print("                      Sentence exmp ", key3, ":", verb_descr_temp2[key3])
                        
                            
                    print()
                print()
                print()
                
        else:
            if mode_selection=='3':
                search_menu = 1
                while search_menu == 1:
                    search_word = input('Please specify the verb or 4 to exit: ')
                    if search_word == '4':
                        search_menu = 0
                    else:
                        if search_word in verb_list_final:
                            output_option_selection = input('Show the sample sentences? 1 - Yes, 2 - No: ')
                            verb_descr_temp = {}
                            print("Verb:",search_word)
                            verb_descr_temp = verb_list_final[search_word]
                            for key1 in verb_descr_temp.keys():
                                print("         Language:",key1)
                                #print(" Translation:",verb_descr_temp['Trans'])
                                
                                verb_descr_temp_case = verb_descr_temp[key1]
                                for key2 in verb_descr_temp_case.keys():
                                    verb_descr_temp2 = verb_descr_temp_case[key2]
                                    print("                 Case_Str:",key2)
                                    
                                    if output_option_selection == '1':
                                        for key3 in verb_descr_temp2.keys():
                                            print("                      Sentence exmp ", key3, ":", verb_descr_temp2[key3])
                                        
                                print()
                        else:
                            print('No examples found')

            if mode_selection=='4':
                show_main_menu = 0

