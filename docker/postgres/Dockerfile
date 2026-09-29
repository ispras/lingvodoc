FROM postgres:13.2

RUN localedef -i ru_RU -c -f UTF-8 -A /usr/share/locale/locale.alias ru_RU.UTF-8
RUN mkdir -p /var/lib/postgresql-static/data
ENV PGDATA /var/lib/postgresql-static/data