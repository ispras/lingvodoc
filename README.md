LingvoDoc project
==================

This project is dedicated to natural languages and dialects documentation. It's the continuation of Dialeqt project
(which was written in C++/QT5/Pure SQL).
LingvoDoc is intended to provide natural language documentation service as Web-service and provides REST API and
ajax-based client application.


Dependencies
---------------

- pyramid (framework)

- sqlalchemy (ORM)

- RDBMS compatible with sqlalchemy


Running the project for development
---------------

- Create virtual python environment for Python (3.3+ recommended; 2.7+ should work too but is not tested)

- Declare env variable for your virtual environment: export VENV=<path to your virtual environment>

- cd <directory containing this file>

- launch every command from this directory

- create database

- create development.ini from production.ini. You must set at least sqlalchemy.url pointing to
  created database

- create alembic.ini from alembic_base.ini. Again, you must set at least sqlalchemy.url pointing to
  created database
  
- pip install -r requirements.txt

- $VENV/bin/python setup.py develop

- alembic upgrade head

- $VENV/bin/initialize_lingvodoc_db development.ini

- $VENV/bin/pserve development.ini

Example for PostgreSQL:

```
# from psql:
drop database lingvodoc; -- drop old database, if exists
create database lingvodoc with owner postgres encoding 'UTF8' LC_COLLATE = 'ru_RU.UTF-8' LC_CTYPE = 'ru_RU.UTF-8' template template0;
# from shell, with activated venv:
pip install -r requirements.txt
# cp production.ini development.ini 
# set sqlalchemy.url to postgresql+psycopg2://postgres@/lingvodoc in development.ini
# TODO [app:accounts] add section to development.int?
# cp alembic_base.ini  alembic.ini # set sqlalchemy.url twice to postgresql+psycopg2://postgres@/lingvodoc
# python setup.py develop
# alembic upgrade head
# initialize_lingvodoc_db development.ini
# pserve development.ini

```

API documentation
---------------

/client_id
/version
/channel
/sync
/words
/word
/paradigms
/paradigm
/dictionaries
/dictionary (contains words, paradigms, corpus set etc)
/authors
/sound
/markup
