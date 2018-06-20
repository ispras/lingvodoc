## Docker-compose
==============

This folder contains docker-compose scripts that make possible to bring up lingvodoc
with near-production settings. There are two version provided:

### Simple lingvodoc
--------------

This mode acts like lingvodoc at lingvodoc.ispras.ru . To use it you should:

- put `.sql` file with lingvodoc database dump (from any site -- even a proxy one) into the folder dbdump. The dump should be made like this: ```pg_dump -U lingvodoc --clean --if-exists lingvodoc | xz -5 > /home/lingvodoc/backups/lingvodoc-`date "+%Y-%m-%d.%H-%M"`.sql.xz```

- unpack `lingvodoc-react` release into frontend folder.

So the needed files for this mode to work are the following:
```
-- dbdump
   |__ lingvodoc-2018-06-19.16-51.sql

-- docker-compose.yml

-- docker.ini

-- frontend
   |__ dist
       |__ assets
       |__ index.html

-- locale_env.sh

-- nginx

-- sock
```
To run this mode you should have recent docker and docker-compose installed.

After any update of lingvodoc or lingvodoc-react you should do the following:

- `docker-compose build`

- `docker-compose up`

You simple lingvodoc will be available at http://localhost:80/

### Complex lingvodoc with bundled proxy
--------------

This mode simulates simple lingvodoc with proxy-version associated to it. To use it you should:

- put `.sql` file with lingvodoc database dump (from any site -- even a proxy one) into the$

- unpack `lingvodoc-react` release into frontend folder

- unpack `lingvodoc-react proxy` release into frontend-proxy folder. NOTE: proxy release 
really differs from simple lingvodoc-react release.

So the needed files for this mode to work are the following:
```
-- dbdump
   |__ lingvodoc-2018-06-19.16-51.sql

-- docker-compose-proxy.yml

-- docker-alembic.ini

-- docker.ini

-- docker-proxy.ini

-- frontend
   |__ dist
       |__ assets
       |__ index.html

-- frontend-proxy
   |__ dist
       |__ assets
       |__ index.html

-- locale_env.sh

-- nginx

-- sock 

-- sock-proxy
```
To run this mode you should have recent docker and docker-compose installed.

After any update of lingvodoc or lingvodoc-react you should do the following:

- `docker-compose -f docker-compose-proxy.yml build`

- `docker-compose -f docker-compose-proxy.yml up`

In this mode you have two lingvodocs running simultaneously. The main one acts like 
lingvodoc.ispras.ru and resides at http://localhost:1080. The second one (proxy) acts
like lingvodoc.tsu.ru or any desktop version installation. This version listens
http://localhost:2080 .
To get the second version actually running, you must log in as an existing user
at http://localhost:2080 and wait the initialization to finish afterwards (15-20 mins).
