import re

from udmparser.analyzer.analyze import analyze
from nltk.tokenize import RegexpTokenizer
import csv
import os
import tempfile
import bs4

"""
from dedoc.manager import dedoc_manager
from dedoc.api.api_utils import json2html


def dedoc_extract(file):
    manager = dedoc_manager.DedocManager()
    parameters = dict()
    document_tree = manager.parse_file(file, parameters=parameters)
    response = json2html(text="", paragraph=document_tree.content.structure,
                                 tables=document_tree.content.tables,
                                 tabs=0)
    return response
"""

"""
def analyze(freqListFile, paradigmFile, lexFile, lexRulesFile,
            derivFile, conversionFile, cliticFile, delAnaFile,
            parsedFile, unparsedFile, errorFile,
            xmlOutput=True, verboseGrammar=False, parserVerbosity=0,
            freqListSeparator='\t', glossing=True,
            parsingMethod='fst', partialCompile=True,
            minFlexLen=4, maxCompileTime=60)
"""

def timarkh_udm(content):

    def extract_parsed(file):
        html = open(file, "r")
        soup = bs4.BeautifulSoup(html, 'html.parser')
        parsed_dict = dict()
        for w in soup.find_all('w'):
            word = w.contents[-1]
            parsed_dict[word] = dict()
            tag_with_attributes = next(w.children)
            for attr in tag_with_attributes.attrs:
                parsed_dict[word][attr] = tag_with_attributes[attr]
        return parsed_dict

    def extract_unparsed(file):
        f = open(file, "r")
        l = list()
        for word in f.read().split("\n"):
            l.append(word)
        return l

    span_id_counter = 1

    content_original = (content + '.')[:-1]
    content = content.replace('\n', '')
    tokenizer = RegexpTokenizer(r'\w+')
    freq_dict = dict()
    for word in tokenizer.tokenize(content):
        if word not in freq_dict.keys():
            freq_dict[word] = 1
        else:
            freq_dict[word] += 1

    csv_file_id, csv_filename = tempfile.mkstemp()
    csv_file = open(csv_filename, 'w+', newline='')
    writer = csv.writer(csv_file, delimiter='\t')
    for key in sorted(freq_dict, key=freq_dict.get, reverse=True):
        writer.writerow([key] + [freq_dict[key]])
    print(csv_file)
    csv_file.close()

    parsed_file_id, parsed_filename = tempfile.mkstemp()
    unparsed_file_id, unparsed_filename = tempfile.mkstemp()
    open(parsed_filename, 'w').close()
    open(unparsed_filename, 'w').close()

    analyze(freqListFile=csv_filename, parsedFile=parsed_filename, unparsedFile=unparsed_filename)

    parsed_dict = extract_parsed(parsed_filename)
    #unparsed_list = extract_unparsed(unparsed_filename)

    html = ""
    html += ("<!DOCTYPE html> "
              "<html>"
                "<head>"
                    "<meta charset=\"utf-8\">"
                    "<title></title>")
    html += ("<style>"
                "SPAN.verified {"
                    "background-color: green;"
                    "}"
                "SPAN.unverified {"
                    "background-color: red;"
                    "}"
                "SPAN.result {"
                    "display: None;"
                    "}"
              "</style>")
    html += ("</head>")
    html += ("<body>")
    html += ("<p>")

    replace_wrap_dict = dict()
    for elem in parsed_dict.keys():
        parsed_data = ""
        for key in parsed_dict[elem]:
            parsed_data += ("\'" + key + "\'" + ": " + "\'" + parsed_dict[elem][key] + "\'" + ", ")
        if len(parsed_data) >= 2 and parsed_data[-2] == ',':
            parsed_data = parsed_data[:-2] + "."
        replace_str = ("<span class=\"unverified\"" + " id=" + str(span_id_counter) + ">" +
                  elem + "<span class=\"result\"" + " id=" + str(span_id_counter+1) + ">" + parsed_data +
                  "</span>" + "</span>")
        span_id_counter += 2
        replace_wrap_dict["1eFtB0rDEr" + elem + "R1Gh4B0RERr"] = replace_str
        content_original = re.sub(r"\b{}\b".format(elem),
                                  "1eFtB0rDEr" + elem + "R1Gh4B0RERr", content_original)

    for key in replace_wrap_dict.keys():
        content_original = re.sub(r"\b{}\b".format(key),
                                  replace_wrap_dict[key], content_original)

    html += content_original.replace("\n", "<br>")
    html += ("</p>")
    html += ("</body>"
              "</html>")
    #file = open("/home/andriy/out.html", "w")
    #soup = bs4.BeautifulSoup(html, 'html.parser')
    #file.write(soup.prettify())
    return html

#f = open("/home/andriy/lingvodoc/udmurtian-text.txt", "r")
#out = open("/home/andriy/lingvodoc/out.html", "w")
#print(timarkh_udm(f.read()), file=out)



