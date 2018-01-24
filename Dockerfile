FROM ubuntu:trusty
ADD . /api
WORKDIR /api
RUN apt-get update && apt-get install -y python3.4-dev python3.4 python3-setuptools libssl-dev libffi-dev wget build-essential xz-utils bzip2 tar
RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
	wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
	sudo apt-key add - && \ 
	apt-get update && \
	apt-get install -y postgresql-server-dev-10
RUN easy_install3 pip==9.0.1 && pip3 install -r server-requirements.txt && pip3 install alembic gunicorn 
