import json
import re

from uniparser_erzya import ErzyaAnalyzer
from uniparser_meadow_mari import MeadowMariAnalyzer
from uniparser_udmurt import UdmurtAnalyzer
from uniparser_moksha import MokshaAnalyzer
from uniparser_komi_zyrian import KomiZyrianAnalyzer
from nltk.tokenize import RegexpTokenizer
import csv
import os
import tempfile
import bs4
import requests

# Extracts a text from a document as a html string with headers (return value 1) and without headers (return value 2) using dedoc module


def dedoc_extract(file, dedoc_url):

    files = {'file': open(file, 'rb')}
    data = {'return_html': True}
    r = requests.post(url=dedoc_url, files=files, data=data)
    dedoc_output = re.sub(r"(<sub>.*?</sub>)", "", r.content.decode('utf-8'))
    content_for_parsing = re.sub(r"(<.*?>)|nbsp", " ", dedoc_output)

    return dedoc_output, content_for_parsing


"""
This is the main parsing function with all parameters
Some of these parameters may be added further

def analyze_wordlist(freqListFile, paradigmFile, lexFile, lexRulesFile,
            derivFile, conversionFile, cliticFile, delAnaFile,
            parsedFile, unparsedFile, errorFile,
            xmlOutput=True, verboseGrammar=False, parserVerbosity=0,
            freqListSeparator='\t', glossing=True,
            parsingMethod='fst', partialCompile=True,
            minFlexLen=4, maxCompileTime=60)
"""

def insert_parser_results(parser_output, dedoc_output):
    content_for_html = dedoc_output

    # Build a dictionary with parsing results for each word
    def extract_parsed(parsed_filename):
        html = open(parsed_filename, "r")
        soup = bs4.BeautifulSoup(html, 'html.parser')
        parsed_dict = dict()
        for w in soup.find_all('w'):
            word = w.contents[-1]
            parsed_dict[word] = list()
            for child in w.children:
                if type(child) == bs4.element.Tag and child.name == "ana":
                    tag_with_attributes = child
                    new_res = dict()
                    for attr in tag_with_attributes.attrs:
                        new_res[attr] = tag_with_attributes[attr]
                    parsed_dict[word].append(new_res)
        return parsed_dict

    parsed_dict = extract_parsed(parser_output)

    """
    Generate a wrap into tags for a word:
    span tag with class unverified is used for background colour filling for parsed words;
    span tags with class result inside of previous span are used for saving the results data for further
    front-end processing
    """
    span_id_counter = 0

    def generate_html_wrap(elem):
        if elem.lower() in parsed_dict.keys():
            elem_case_as_in_parsed_dict = elem.lower()
        elif elem.capitalize() in parsed_dict.keys():
            elem_case_as_in_parsed_dict = elem.capitalize()
        elif elem.upper() in parsed_dict.keys():
            elem_case_as_in_parsed_dict = elem.upper()
        else:
            return elem
        nonlocal span_id_counter
        span_id_counter += 1
        wrap = "<span class=\"unverified\"" + " id=" + str(span_id_counter) + ">"
        for res in parsed_dict[elem_case_as_in_parsed_dict]:
            span_id_counter += 1
            parsed_data = ((json.dumps(res, ensure_ascii=False)).encode('utf8')).decode()
            wrap += "<span class=\"result\"" + " id=" + str(span_id_counter) + ">" + parsed_data + "</span>"
        wrap += elem + "</span>"
        return wrap

    # Construct a sorted list of all matches in the document avoiding processing single match multiple times
    def is_complex(elem):
        return elem.find("-") != -1 or elem.find(" ") != -1

    matches_indices = list()
    matches = list()
    for i in range(0, 2):
        for elem in parsed_dict.keys():
            if (i == 0 and not is_complex(elem)) or (i == 1 and is_complex(elem)):
                continue
            matches_for_elem = list(re.finditer(r"\b{}\b".format(elem), content_for_html)) + \
                               list(re.finditer(r"\b{}\b".format(elem.capitalize()), content_for_html)) + \
                               list(re.finditer(r"\b{}\b".format(elem.upper()), content_for_html))

            def check_indices(match):
                for pair in matches_indices:
                    if match.regs[0][0] >= pair[0] and match.regs[0][1] <= pair[1]:
                        return False
                return True

            for match in matches_for_elem:
                if check_indices(match):
                    new_element = dict()
                    new_element['begin'] = match.regs[0][0]
                    new_element['end'] = match.regs[0][1]
                    new_element['elem'] = content_for_html[new_element['begin']:new_element['end']]
                    matches.append(new_element)

                    matches_indices.append((new_element['begin'], new_element['end']))

    matches = sorted(matches, key=lambda k: k['begin'])

    # Construct the result by step-by-step concatenation of content before match and matched elem tag wrap
    previous_wrap_end = 0
    result = "<body>"
    if len(matches) > 0:
        for match in matches:
            wrap = generate_html_wrap(match['elem'])
            result += content_for_html[previous_wrap_end:match['begin']]
            previous_wrap_end = match['end']
            result += wrap
    result += content_for_html[previous_wrap_end:]

    return result

def timarkh_uniparser(content_file, dedoc_url, lang):
    # Save dedoc module output for further result composing
    dedoc_output, content_for_parsing = dedoc_extract(content_file, dedoc_url)

    # Build the content for parsing by formatting the dedoc's output
    # Build a csv file with frequences of each word in the input document to pass it to the parsing function
    tokenizer = RegexpTokenizer(r'(?!\w+(?:-\w+)+)\w+|\w+(?:-\w+)+')
    freq_dict = dict()
    for word in tokenizer.tokenize(content_for_parsing):
        lowered = word.lower()
        if lowered not in freq_dict.keys():
            freq_dict[lowered] = 1
        else:
            freq_dict[lowered] += 1
        if lowered.find("-") != -1:
            parts = lowered.split("-")
            for part in parts:
                if part not in freq_dict.keys():
                    freq_dict[part] = 1
                else:
                    freq_dict[part] += 1

    csv_file_id, csv_filename = tempfile.mkstemp()
    csv_file = open(csv_filename, 'w+', newline='')
    writer = csv.writer(csv_file, delimiter='\t')
    for key in sorted(freq_dict, key=freq_dict.get, reverse=True):
        writer.writerow([key] + [freq_dict[key]])
    csv_file.close()

    # Call the parsing function and save its results into temporary files
    parsed_file_id, parsed_filename = tempfile.mkstemp()
    unparsed_file_id, unparsed_filename = tempfile.mkstemp()
    open(parsed_filename, 'w').close()
    open(unparsed_filename, 'w').close()

    if lang == 'udm':
        udmurt = UdmurtAnalyzer(mode='strict')
        udmurt.analyze_wordlist(freqListFile=csv_filename, parsedFile=parsed_filename, unparsedFile=unparsed_filename)
    if lang == 'erzya':
        erzya = ErzyaAnalyzer(mode='strict')
        erzya.analyze_wordlist(freqListFile=csv_filename, parsedFile=parsed_filename, unparsedFile=unparsed_filename)
    if lang == 'moksha':
        moksha = MokshaAnalyzer(mode='strict')
        moksha.analyze_wordlist(freqListFile=csv_filename, parsedFile=parsed_filename, unparsedFile=unparsed_filename)
    if lang == 'komi_zyryan':
        komi_zyrian = KomiZyrianAnalyzer(mode='strict')
        komi_zyrian.analyze_wordlist(freqListFile=csv_filename, parsedFile=parsed_filename, unparsedFile=unparsed_filename)
    if lang == 'meadow_mari':
        meadow_mari = MeadowMariAnalyzer(mode='strict')
        meadow_mari.analyze_wordlist(freqListFile=csv_filename, parsedFile=parsed_filename, unparsedFile=unparsed_filename)

    result = insert_parser_results(parsed_filename, dedoc_output)

    # Remove all temporary files
    os.remove(csv_filename)
    os.remove(parsed_filename)
    os.remove(unparsed_filename)

    return result

def apertium_parser(content_file, dedoc_url, apertium_path, lang):
    def reformat(biltrans_filename, morph_filename):

        skip_list = ["guio", "cm", "sent", "lpar", "rpar", "lquot", "rquot"]

        biltrans_file = open(biltrans_filename, "r", encoding="UTF-8")
        morph_file = open(morph_filename, "r", encoding="UTF-8")

        biltrans = biltrans_file.read()
        morph = morph_file.read()

        biltrans_elements = re.findall(r"\^(.+?)\$", biltrans)
        morph_elements = re.findall(r"\^(.+?)\$", morph)
        parsed = ""
        unparsed = ""
        unparsed_set = set()

        def is_conform(lex_1, lex_2):
            if lex_1.lower().find(lex_2.lower()) == -1 and lex_2.lower().find(lex_1.lower()) == -1:
                return False
            else:
                return True

        def biltrans_lex(i):
            return biltrans_elements[i][0: biltrans_elements[i].find("<")].lower()

        def gr(elem):
            gr_list = list()
            for match in re.findall(r"<(\w+)>", elem.split("/")[0]):
                gr_list.append(match)
            return gr_list

        def add_gr(gr_list):
            to_add = " gr=\""
            gr_list = gr(biltrans_elements[i])
            if gr_list:
                k = 0
                N = len(gr_list)
                for gr_elem in gr_list:
                    if k == 0:
                        to_add += gr_elem.upper()
                        if N > 1:
                            to_add += ","
                    elif k < N - 1:
                        to_add += gr_elem + ","
                    else:
                        to_add += gr_elem
                    k += 1
            to_add += "\""
            return to_add

        def trans(elem):
            trans_list = list()
            for match in re.findall(r"/(\w+)<", biltrans_elements[i]):
                if match not in trans_list:
                    trans_list.append(match)
            return trans_list

        def add_variant(lex, gr, trans, parts = " parts=\"\"", gloss = " gloss=\"\""):
            return "<ana " + lex + gr + parts + gloss + trans + " ></ana>"

        i = -1
        for morph_element in morph_elements:
            i += 1

            if len(morph_element) == 0:
                continue

            if morph_element.find("*") != -1:
                unparsed_set.add(re.findall(r"\*(\w+)$", morph_element)[0])
                continue

            continue_flag = False
            for skip_elem in skip_list:
                if morph_element.find(skip_elem) != -1:
                    continue_flag = True
                    break
            if continue_flag:
                continue

            new = ""
            new += "<w>"

            morph_slash_split_list = morph_element.split("/")
            orig = morph_slash_split_list[0]
            lex = morph_slash_split_list[1][:morph_slash_split_list[1].find("<")]

            offset = 0
            match_found = True
            while not is_conform(lex, biltrans_lex(i+offset)):
                if offset > 2:
                    match_found = False
                    break
                offset += 1
            if not match_found:
                continue
            i += offset

            new_lex = "lex=" + "\"" + biltrans_lex(i).lower() + "\""
            new_gr = add_gr(gr(biltrans_elements[i]))
            trans_list = trans(biltrans_elements[i])

            if not trans_list and new_gr == " gr=\"\"":
                continue

            if trans_list:
                for trans_elem in trans_list:
                    new += add_variant(new_lex, new_gr, " trans_ru=\"" + trans_elem.lower() + "\"")
            else:
                new += add_variant(new_lex, new_gr, " trans_ru=\"\"")

            new += orig.lower()
            new += "</w>"
            new += "\n"

            parsed += new

            for element in unparsed_set:
                unparsed += element + "\n"

        biltrans_file.close()
        morph_file.close()

        return parsed, unparsed

    dedoc_output, content_for_parsing = dedoc_extract(content_file, dedoc_url)

    biltrans_file_id, biltrans_filename = tempfile.mkstemp()
    morph_file_id, morph_filename = tempfile.mkstemp()

    s1 = 0
    s2 = 0
    if lang == 'tat':
        s1 = os.system("echo \"" + content_for_parsing + "\" | apertium -d " + apertium_path + "/apertium-tat-rus tat-rus-biltrans >> " +  biltrans_filename)
        s2 = os.system("echo \"" + content_for_parsing + "\" | apertium -d " + apertium_path + "/apertium-tat-rus tat-rus-morph >> " +  morph_filename)

    if lang == 'kaz':
        s1 = os.system("echo \"" + content_for_parsing + "\" | apertium -d " + apertium_path + "/apertium-kaz-rus kaz-rus-biltrans >> " + biltrans_filename)
        s2 = os.system("echo \"" + content_for_parsing + "\" | apertium -d " + apertium_path + "/apertium-kaz-rus kaz-rus-morph >> " + morph_filename)

    if s1 != 0 or s2 != 0:
        raise ValueError("An error occured during Apertium parser running")

    parser_results = reformat(biltrans_filename, morph_filename)[0]
    os.remove(biltrans_filename)
    os.remove(morph_filename)

    output_file_id, output_filename = tempfile.mkstemp()
    output_file = open(output_filename, "w", encoding="UTF-8")
    output_file.write(parser_results)
    output_file.close()

    to_return = insert_parser_results(output_filename, dedoc_output)
    os.remove(output_filename)

    return to_return

def timarkh_udm(content_file, dedoc_url):
    return timarkh_uniparser(content_file, dedoc_url, 'udm')

def timarkh_erzya(content_file, dedoc_url):
    return timarkh_uniparser(content_file, dedoc_url, 'erzya')

def timarkh_moksha(content_file, dedoc_url):
    return timarkh_uniparser(content_file, dedoc_url, 'moksha')

def timarkh_komi_zyryan(content_file, dedoc_url):
    return timarkh_uniparser(content_file, dedoc_url, 'komi_zyryan')

def timarkh_meadow_mari(content_file, dedoc_url):
    return timarkh_uniparser(content_file, dedoc_url, 'meadow_mari')

def apertium_tat_rus(content_file, dedoc_url, apertium_path):
    return apertium_parser(content_file, dedoc_url, apertium_path, 'tat')

def apertium_kaz_rus(content_file, dedoc_url, apertium_path):
    return apertium_parser(content_file, dedoc_url, apertium_path, 'kaz')
