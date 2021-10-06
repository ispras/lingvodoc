
# Standard library imports.

import json
import pdb
import pprint
import re
import requests
import xml.etree.ElementTree as ElementTree

format_flag = True

graphql_url = 'http://lingvodoc.ispras.ru/api/graphql'
perspective_url = 'http://lingvodoc.ispras.ru/dictionary/3648/5/perspective/3648/8/view'

entity_query_str = ('''
  query Perspective {
    perspective(id: [3648, 8]) {
      id
      created_at
      lexical_entries(mode: "published") {
        id
        created_at
        entities(mode: "published") {
          id
          created_at
          field_id
          is_subject_for_parsing
          content
        }
      }
    }
  }
''')

parser_result_query_str = ('''
  query Parser_Results {{
    parser_results(entity_id: {}) {{
      id
      created_at
      parser_id
      content
    }}
  }}
''')

# Exporting raw data.

def main_raw():

    result = (

        requests.post(
            graphql_url,
            json = {'query': entity_query_str}))

    print(
        'entity_query: {}'.format(
            result.status_code))

    if result.status_code != 200:
        raise NotImplementedError

    result_json = result.json()

    if 'data' not in result_json:
        raise NotImplementedError

    entity_data = result_json['data']

    # Getting parsing results.

    for lexical_entry in entity_data['perspective']['lexical_entries']:
        for entity in lexical_entry['entities']:

            if not entity['is_subject_for_parsing']:
                continue

            query_str = (
                parser_result_query_str.format(entity['id']))

            result = (

                requests.post(
                    graphql_url,
                    json = {'query': query_str}))

            if result.status_code != 200:
                raise NotImplementedError

            result_json = result.json()

            if 'data' not in result_json:
                raise NotImplementedError

            entity['parser_results'] = (
                result_json['data']['parser_results'])

            print(
                'parser_result_query {}: {}'.format(
                    entity['id'],
                    result.status_code))

    # Saving.

    with open('corpus-raw.json', 'w') as corpus_file:

        json.dump(
            entity_data,
            corpus_file,
            ensure_ascii = False,
            indent = 2)

# Processing paragraph.

def process_paragraph(paragraph_xml):

    item_list = []

    check_list = []
    check_flag = False

    def f(element):
        """
        Recursive element processing.
        """

        nonlocal check_flag

        # Parsing result.

        if element.tag == 'span' or element.tag.endswith('}span'):

            class_list = (
                element.attrib['class'].split())

            text_list = []

            approved_list = []
            other_list = []

            if element.text:
                text_list.append(element.text)

            # Looking through variants.

            for sub_element in element:
                
                if (sub_element.tag != 'span' and
                    not sub_element.tag.endswith('}span')):

                    raise NotImplementedError

                if len(list(sub_element)) > 0:

                    raise NotImplementedError

                sub_class_list = (
                    sub_element.attrib['class'].split())

                if 'result' not in sub_class_list:
                    
                    print(f'sub_class_list: {sub_class_list}')
                    raise NotImplementedError

                ((approved_list if 'approved' in sub_class_list else other_list)
                    .append(json.loads(sub_element.text)))

                if sub_element.tail:
                    text_list.append(sub_element.tail)

            # Saving gathered info.

            result_text = ''.join(text_list)

            if ('verified' not in class_list or
                len(approved_list) != 1):

                check_flag = True
                check_list.append([result_text])

            else:

                check_list.append(result_text)

            item_list.append(
                [result_text, approved_list, other_list])

            if element.tail:
                item_list.append(element.tail)

            return

        # Just the text.

        if element.text:
            item_list.append(element.text)

        for sub_element in element:
            f(sub_element)

        if element.tail:
            item_list.append(element.tail)

    # Processing paragraph HTML.

    f(paragraph_xml)

    # Post-processing by joining strings and removing unnecessary whitespace.

    source_item_list = item_list
    item_list = []

    for item in source_item_list:

        if (isinstance(item, str) and
            item_list and
            isinstance(item_list[-1], str)):

            item_list[-1] += item

        else:

            item_list.append(item)

    if (item_list and
        isinstance(item_list[0], str)):

        item_list[0] = item_list[0].strip()

        if not item_list[0]:
            item_list.pop(0)

    if (item_list and
        isinstance(item_list[-1], str)):

        item_list[-1] = item_list[-1].strip()

        if not item_list[-1]:
            item_list.pop(-1)

    return item_list, check_list, check_flag

# Exporting processed data.

def main_processed():

    result = (

        requests.post(
            graphql_url,
            json = {'query': entity_query_str}))

    print(
        'entity_query: {}'.format(
            result.status_code))

    if result.status_code != 200:
        raise NotImplementedError

    result_json = result.json()

    if 'data' not in result_json:
        raise NotImplementedError

    entity_data = result_json['data']

    # Getting all parsing results.

    parser_result_list = []
    token_count = 0

    for lexical_entry in entity_data['perspective']['lexical_entries']:

        comment_str = None

        for entity in lexical_entry['entities']:

            if entity['field_id'] == [674, 5]:

                comment_str = entity['content']
                continue

            elif not entity['is_subject_for_parsing']:

                continue

            # Getting parsing result data.

            query_str = (
                parser_result_query_str.format(entity['id']))

            result = (

                requests.post(
                    graphql_url,
                    json = {'query': query_str}))

            print(
                'parser_result_query {}: {}'.format(
                    entity['id'],
                    result.status_code))

            if result.status_code != 200:
                raise NotImplementedError

            result_json = result.json()

            if 'data' not in result_json:
                raise NotImplementedError

            print(f'comment_str: {repr(comment_str)}')

            # Processing parsing results for this source.

            for parser_result_index, parser_result in (
                enumerate(result_json['data']['parser_results'])):

                with open(f'content_{parser_result_index:02d}.html', 'w') as content_file:
                    content_file.write(parser_result['content'])

                paragraph_list = []

                root = ElementTree.fromstring(parser_result['content'])

                # Processing each paragraph.

                for paragraph_index, paragraph_xml in (
                    enumerate(root.iter('{http://www.w3.org/1999/xhtml}p'))):

                    paragraph_item_list, check_list, check_flag = (
                        process_paragraph(paragraph_xml))

                    if not paragraph_item_list:
                        continue

                    if check_flag:
                        print(check_list)

                    paragraph_text = (

                        ''.join(
                            item if isinstance(item, str) else item[0]
                            for item in paragraph_item_list))

                    # Requested info.

                    if format_flag:

                        token_list = []
                        variant_list = []

                        for item in paragraph_item_list:

                            # Text part which is not a parsed token.

                            if isinstance(item, str):

                                token_str = re.sub(r'\s+', '', item)

                                if token_str:

                                    token_list.append({'token': token_str})
                                    variant_list.append({'token': token_str})

                            # Parsed token with variants.

                            else:

                                token_str = item[0]

                                approved_list = [
                                    dict(variant_dict, token = token_str)
                                    for variant_dict in item[1]]

                                other_list = [
                                    dict(variant_dict, token = token_str)
                                    for variant_dict in item[2]]

                                token_list.append(
                                    approved_list[0] if approved_list else other_list[0])

                                variant_list.append(
                                    approved_list + other_list)

                                token_count += 1

                        paragraph_dict = {
                            'index': paragraph_index,
                            'text': paragraph_text,
                            'tokens': token_list,
                            'variants': variant_list}

                    # All info.

                    else:

                        approved_list = [
                            item[:2]
                            for item in paragraph_item_list
                            if not isinstance(item, str)]

                        variant_list = [
                            item
                            for item in paragraph_item_list
                            if not isinstance(item, str)]

                        paragraph_dict = {
                            'index': paragraph_index,
                            'text': paragraph_text,
                            'source': paragraph_item_list,
                            'tokens': approved_list,
                            'variants': variant_list}

                    paragraph_list.append(paragraph_dict)

                # Ok, got another parser result.

                parser_result_dict = {
                    'index': parser_result_index,
                    'id': parser_result['id'],
                    'title': comment_str,
                    'paragraphs': paragraph_list}

                parser_result_list.append(parser_result_dict)

    # Saving.

    with open('corpus.json', 'w') as corpus_file:

        json.dump(
            parser_result_list,
            corpus_file,
            ensure_ascii = False,
            indent = 2)

    print(f'token_count: {token_count}')

# If we are being run as a script.
#
# python -m lingvodoc.scripts.export_parser_result

if __name__ == '__main__':

    main_processed()

