from lxml import objectify
from collections import defaultdict


if __name__ == '__main__':
    f = open('/Users/al/Movies/corpus.xml', 'r')
    corpus_xml = f.read()
    f.close()

    root = objectify.fromstring(corpus_xml)

    corpus = dict()
    corpus['corpus_id'] = 1
    corpus['corpus_client_id'] = 1
    corpus['texts'] = []

    text_id = 1
    client_id = 1

    for element in root['interlinear-text']:
        text = dict()
        text['client_id'] = client_id
        text['text_id'] = text_id
        text_id += 1
        text['text_titles'] = [{"lang": "ru", "content": element['item']}]


        print("asd")


