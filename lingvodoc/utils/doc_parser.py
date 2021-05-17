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

# Extracts html string with headers using dedoc module


def dedoc_extract(file, dedoc_url):

    files = {'file': open(file, 'rb')}
    data = {'return_html': True}
    r = requests.post(url=dedoc_url, files=files, data=data)

    return r.content.decode('utf-8')


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

# Parses an odt file with udmurtian text, returns an html string with parsed words wrapped into tags

def timarkh_uniparser(content_file, dedoc_url, lang):
    # Save dedoc module output for further result composing
    # Exclude sub tag with content as have no need in it
    dedoc_output = dedoc_extract(content_file, dedoc_url)
    dedoc_output = re.sub(r"(<sub>.*?</sub>)", "", dedoc_output)

    # Build the content for parsing by formatting the dedoc's output
    # Build a csv file with frequences of each word in the input document to pass it to the parsing function
    content_for_parsing = re.sub(r"(<.*?>)|nbsp", " ", dedoc_output)
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
        matches_indices = list()
        matches = list()
        for i in range(0,2):
            for elem in parsed_dict.keys():
                if (i == 0 and elem.find("-") == -1) or (i == 1 and elem.find("-") != -1):
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

    result = insert_parser_results(parsed_filename, dedoc_output)

    # Remove all temporary files
    os.remove(csv_filename)
    os.remove(parsed_filename)
    os.remove(unparsed_filename)

    return result


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




