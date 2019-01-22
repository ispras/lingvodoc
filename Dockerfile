FROM ubuntu:16.04
RUN apt-get update && apt-get install -y locales
RUN locale-gen en_US.UTF-8
ENV LANG='en_US.UTF-8' LANGUAGE='en_US:en' LC_ALL='en_US.UTF-8'
ADD . /api
WORKDIR /api
RUN apt-get update && apt-get install -y python3.5-dev python3.5 python3-setuptools libssl-dev libffi-dev wget build-essential xz-utils bzip2 tar unzip
RUN wget https://github.com/ispras/lingvodoc-ext-oslon/archive/master.zip -O /tmp/master.zip && unzip /tmp/master.zip -d /tmp/  && g++ -O2 -fPIC -shared -Wl,-soname,liboslon.so -Wno-write-strings -o /usr/lib/ldconfig /tmp/lingvodoc-ext-oslon-master/analysis.cpp
RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ xenial-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
	wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
	apt-key add - && \ 
	apt-get update && \
	apt-get install -y postgresql-server-dev-10 postgresql-client-10
RUN easy_install3 pip==9.0.1 && pip3 install --upgrade setuptools && pip3 install -r server-requirements.txt && pip3 install alembic gunicorn 
