import xlrd

from lingvodoc.models import (
    DBSession,
    UserBlobs
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
        "lng": float(sheet.cell_value(rowx=0, colx=1).split(", ")[0]),
        "lat": float(sheet.cell_value(rowx=0, colx=1).split(", ")[1])
        }
    d['date'] = sheet.cell_value(rowx=0, colx=2)
    d['questions'] = dict()
    for rx in range(1, sheet.nrows):
        if sheet.cell_value(rowx=rx, colx=1):
            d['questions'][sheet.cell_value(rowx=rx, colx=0)] = sheet.cell_value(rowx=rx, colx=1)
            answers.add(sheet.cell_value(rowx=rx, colx=1))
            questions.add(sheet.cell_value(rowx=rx, colx=0))
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
    lst = []
    all_questions = set()
    all_answers = set()
    for i in socioblobs:
        try:
            socio, questions, answers = parse_socio(i.real_storage_path)
            all_questions.update(questions)
            all_answers.update(answers)
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