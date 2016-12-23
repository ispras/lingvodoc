import xlrd

from lingvodoc.models import (
    DBSession,
    UserBlobs,
    DictionaryPerspective
)

from pyramid.response import Response
from pyramid.view import view_config

import logging
log = logging.getLogger(__name__)


def parse_socio(path):
    d = {}
    answers = set()
    questions = set()
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    d['community_name'] = sheet.cell_value(rowx=0, colx=0)
    d['location'] = {
        "lat": float(sheet.cell_value(rowx=0, colx=1).split(", ")[0]),
        "lng": float(sheet.cell_value(rowx=0, colx=1).split(", ")[1])
        }
    d['date'] = sheet.cell_value(rowx=0, colx=2)
    d['questions'] = dict()
    for rx in range(1, sheet.nrows):
        answer = sheet.cell_value(rowx=rx, colx=1).strip()
        if answer:
            question = sheet.cell_value(rowx=rx, colx=0).strip()
            if question:
                question = question if question[-1] != '?' else question[:-1]
                d['questions'][question] = answer
                answers.add(answer)
                questions.add(question)
    d['perspectives'] = []
    return d, questions, answers


def check_socio(path):
    try:
        sheet = xlrd.open_workbook(path).sheet_by_index(0)
    except:
        raise Exception("It seems that your Excel file is not Excel one, too old or has errors.")
    try:
        d = {
            "lng": float(sheet.cell_value(rowx=0, colx=1).split(", ")[0]),
            "lat": float(sheet.cell_value(rowx=0, colx=1).split(", ")[1])
            }
    except:
        raise Exception("File contains wrong location cell: "
                        "it's expected at B1 cell in format similar to 81.512341, 58.716525")
    return True


def sociolinguistics():
    socioblobs = DBSession.query(UserBlobs).filter(UserBlobs.data_type == 'sociolinguistics').all()

    # TODO: need to acknowledge how to make joins like this (the following is *wrong*) :
    # DBSession.query(UserBlobs, DictionaryPerspective
    #   ).filter(UserBlobs.data_type == 'sociolinguistics'
    #   ).join(DictionaryPerspective, DictionaryPerspective.additional_metadata.contains(
    #    {"info":
    #       {"content":
    #           [{"info": {"content": {'object_id': UserBlobs.object_id, 'client_id': UserBlobs.client_id}}}]
    #       }
    #    }
    #   )
    #   ).all()

    lst = []
    all_questions = set()
    all_answers = set()
    for i in socioblobs:
        try:
            socio, questions, answers = parse_socio(i.real_storage_path)
            all_questions.update(questions)
            all_answers.update(answers)
            dependant_perspectives = DBSession.query(DictionaryPerspective
                            ).filter(DictionaryPerspective.additional_metadata.contains(
                                         {"info":
                                              {"content":
                                                   [{"info":
                                                         {"content":
                                                              {'object_id': i.object_id, 'client_id': i.client_id}
                                                          }
                                                     }
                                                    ]
                                               }
                                          }
                                     )
                                     ).all()
            for j in dependant_perspectives:
                socio['perspectives'].append({"client_id": j.client_id, "object_id": j.object_id})
            lst.append(socio)
        except Exception as e:
            log.error(e)
            continue
    return lst, all_questions, all_answers


@view_config(route_name='sociolinguistics', renderer='json', request_method='GET')
def sociolinguistics_list(request):
    return sociolinguistics()[0]


@view_config(route_name='sociolinguistics_questions', renderer='json', request_method='GET')
def sociolinguistics_questions(request):
    return list(sociolinguistics()[1])


@view_config(route_name='sociolinguistics_answers', renderer='json', request_method='GET')
def sociolinguistics_answers(request):
    return list(sociolinguistics()[2])