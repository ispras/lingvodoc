import transaction
from flask import jsonify
from sqlalchemy import create_engine

from lingvodoc import DBSession
from lingvodoc.models import Parser, ParserResult, User, Entity

# TODO: add from config
from lingvodoc.utils.creation import create_parser

dbname = "postgresql+psycopg2://lingvodoc:@localhost:15432/lingvodoc"
engine = create_engine(dbname)
DBSession.configure(bind=engine)
ParserResult.__table__.create(engine)
# ParserResult.__table__.create(engine)

