#!/usr/bin/python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------

import itertools
import json
import pdb
import xml.etree.ElementTree as ElementTree
import simplejson
import requests

#-----------------------------------------------------------------------

class Corpus(object):

    def __init__(self):
        self.text_count = 0
        session = requests.Session()
        r = session.post('http://ldbeta.at.ispras.ru/login', data={'login': 'demo', 'password': 'demopass'})
        self.session = session

    def parse_document(self, document):
        text_list = []

        for text in document:
            text_list.append(self.parse_text(text))

        return {'corpus_id': 1, 'corpus_client_id': 1, 'texts': text_list}

    def parse_text(self, text):

        title_list = []
        comment_list = []
        paragraph_list = []

        for element in text:

            if element.tag == 'item' and element.get('type') == 'title':
                title_list.append({
                    'lang': element.get('lang'),
                    'content': element.text.encode('utf8')})

            elif element.tag == 'item' and element.get('type') == 'comment':
                comment_list.append({
                    'lang': element.get('lang'),
                    'content': element.text.encode('utf8')})

            elif element.tag == 'paragraphs':

                for e in element:
                    if e.tag == 'paragraph':
                        paragraph_list.append(self.parse_paragraph(e))

        self.text_count += 1

        return {
            'text_id': self.text_count,
            'client_id': 1,
            'text_titles': title_list,
            'text_comments': comment_list,
            'paragraphs': paragraph_list}

    def parse_paragraph(self, paragraph):

        phrase_list = []

        for element in paragraph:
            if element.tag == 'phrases':

                for e in element:
                    if e.tag == 'word':
                        phrase_list.append(self.parse_phrase(e))

        return {'phrases': phrase_list}

    def parse_phrase(self, phrase):

        word_list = []
        translation_list = []

        for element in phrase:

            if element.tag == 'words':
                for e in element:

                    if e.tag == 'word':
                        word_list.append(self.parse_word(e))

            elif (element.tag == 'item' and
                          element.get('type') == 'gls' and
                          element.text != None):

                translation_list.append({
                    'type': 'lingvodoc_metaparadigm_translation',
                    'lang': element.get('lang'),
                    'content': element.text.encode('utf8')})

        return {'words': word_list, 'translations': translation_list}

    def parse_word(self, word):

        item_list = []
        for element in word:

            if element.tag != 'item' or element.text == None:
                continue

            type = element.get('type')

            url = None
            if type == 'gls':
                type = 'lingvodoc_metaword'
                url = self.session.get('http://ldbeta.at.ispras.ru/dictionaries/find_by_translation',
                                       params={'translation': element.text})

            if url:
                item_list.append({
                    'type': type,
                    'lang': element.get('lang'),
                    'content': element.text.encode('utf8'),
                    'url': simplejson.loads(url.text)['url']})
            else:
                item_list.append({
                    'type': type,
                    'lang': element.get('lang'),
                    'content': element.text.encode('utf8')})

        return {'items': item_list}

#-----------------------------------------------------------------------

if __name__ == '__main__':
    element_tree = ElementTree.parse('corpus.xml')

    with open('corpus.json', 'w') as corpus_file:
        simplejson.dump(
            Corpus().parse_document(element_tree.getroot()),
            corpus_file,
            ensure_ascii=False, separators=(',', ':'), sort_keys = False)

#-----------------------------------------------------------------------
