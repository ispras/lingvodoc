#!/bin/bash
# wait-for-postgres.sh


export PGPASSWORD=password
set -e
host="$1"
shift
cmd="$@"

until psql -h "$host" -U "postgres" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 5
done

>&2 echo "Postgres is up - finished waiting"

