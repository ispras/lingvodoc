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
cp alembic_base.ini  alembic.ini # set sqlalchemy.url twice to postgresql+psycopg2://postgres@/lingvodoc
python setup.py develop
alembic upgrade head
initialize_lingvodoc_db development.ini
pserve development.ini

```

Installing as server (full-speed) environment for Ubuntu.
---------------

0. Install (if you do not have one) Python 3.4 or later.
1. Install PostgreSQL server 9.6. 
    * Ensure that all your locale settings are UTF-8 in your current bash (run `locale` to see it).
    * Create file `/etc/apt/sources.list.d/pgdg.list` with `deb http://apt.postgresql.org/pub/repos/apt/ xenial-pgdg main`. 
If you are using less recent distro version, replace `xenial` with `trusty` or `precise`. 
    * Get certificate for this repository: `wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | 
                                              sudo apt-key add -; sudo apt-get update`
    * Install PostgreSQL server, dev and contrib: `sudo apt-get install postgresql-9.6 postgresql-server-dev-9.6 postgresql-contrib-9.6`
    * Tune up the settings (optional but recommended):
         + (optionally - just for dev purposes - not recommended) in `/etc/postgresql/9.6/main/pg_hba.conf` - `local   all             postgres                                trust`
         + in `/etc/postgresql/9.6/main/postgresql.conf`:
             * `shared_buffers` - 1/16 of your memory (e.g. for 32GB RAM `shared_buffers = 2048MB`)
             * `temp_buffers = 256MB`
             * `work_mem` - (total RAM/2*cores count)/8 (e.g. for 32GB RAM and 8 logical cores `work_mem = 256MB`)
             * `maintenance_work_mem` = 2*work_mem (e.g. `maintenance_work_mem = 512MB`)
             * `max_stack_depth = 6MB`
             * `max_wal_senders = 10`
             * `effective_cache_size` - 1/8 of total RAM (e.g. 4096MB)
             * `wal_level = replica`
     * Restart postgres: `sudo service postgresql restart`
     * Import the latest database backup (from-scratch creation look in `# from psql` section): `sudo -u posgres psql < lingvodoc.sql`
2. Install Redis: `sudo apt-get install redis-server`.
3. Install compilers, libraries and git: `sudo apt-get install build-essential python3-dev libssl-dev git`
4. Install venv-creator: `sudo apt-get install python3-virtualenv`
5. (optional but recommended) Create separate regular user (without sudo permissions) for Lingvodoc system.       
If you use this step, login as that user for all the other steps.
6. Go to your home dir and create venv: 
`cd ~; mkdir -p environments; python3 -m virtualenv -p python3 ./environments/lingvodoc-server`
7. Activate your virtualenv: `source ./environments/lingvodoc-server/bin/activate`
8. Clone lingvodoc repository and checkout the correct branch: `git clone https://github.com/ispras/lingvodoc`
9. Execute `cd lingvodoc; pip3 install -r server-requirements.txt`
10. Go into lingvodoc dir and make `python setup.py install` or `python setup.py develop` (you should know what you are doing)
11. Copy alembic_base.ini and postgres.ini configs to home directory: `cp ./alembic_base.ini ../ ; cp postgres.ini ../`
12. Tuneup settings in alembic_base.ini:
    * sqlalchemy.url
13. Tuneup settings in postgres.ini:
    * section [server:main] according to your choice. Recommended way to deploy in production mode is to use gunicorn (or uwsgi but it may have some problems)
    ```
    [server:main]
     use = egg:gunicorn#main
     workers = 8
     timeout = 3000
     proc_name = lingvodoc
     bind = unix:/tmp/lingvodoc.sock
     ``` 
     (note: you should install gunicorn to use that config; it's not present in requirements since pserve/waitress works well too)
     (note2: if you are using that way, you will need wsgi-frontend [nginx for example])
    * section [app:main] 
      - `secret = 'your random string'`
      - `sqlalchemy.url` according to database name, postgres port etc. 
    * loggers (to your choice)
    * section [app:accounts] for your administrator user (needed for building from scratch)
    * section [backend:storage]. WARNING: do not forget to change `prefix`
      - in case of plain disk usage:
      ```
      [backend:storage]
      type = disk
      path = /home/lingvodoc/objects/
      prefix = http://lingvodoc.ispras.ru/
      static_route = objects/
      ```
      - in case of Openstack Swift usage (just for example; you must know what you are doing if you use it):
      ```
      [backend:storage]
      authurl = http://10.10.10.121:5000/v2.0
      store = http://adelaide.intra.ispras.ru/horizon/project/containers
      user = admin
      key = tester
      auth_version = 2.0
      tenant_name = admin
      ```
14. Run lingvodoc: `pserve --daemon ./postgres.ini start`
15.(optionally) To run a celery worker you need to run `celery worker -A lingvodoc.queue.celery` from lingvodoc root.
    * Enable the celery — open your celery.ini file and set the value of celery to "true".
             
Installing as desktop (user) environment for Ubuntu
---------------
(Will be reported later)


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
