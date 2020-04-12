
# Standard library imports.

import datetime
import json
import logging
import math
import os.path
import pdb
import pickle
import pprint
import random
import signal
import sys
import time
import uuid

# External imports.

import pyramid.paster as paster

from sqlalchemy import Column, column, func, literal_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.expression import Grouping
from sqlalchemy.types import Float, Integer, TIMESTAMP

import transaction

from zope.sqlalchemy import mark_changed

# Project imports.

from lingvodoc.models import (
    Base,
    DBSession,
    ObjectTOC,
)


# Setting up logging, if we are not being run as a script.

if __name__ != '__main__':
    log = logging.getLogger(__name__)


# If we are being run as a script.

if __name__ == '__main__':

    if len(sys.argv) < 2:

        sys.exit(
            'Please specify config file:\n'
            '  python -m lingvodoc.scripts.float_timestamp_test <config_file_path>')

    config_path = sys.argv[1]

    pyramid_env = paster.bootstrap(config_path)
    paster.setup_logging(config_path)

    log = logging.getLogger(__name__)

    # Loading or initializing state.

    if (len(sys.argv) > 2 and
        os.path.exists(sys.argv[2])):

        with open(
            sys.argv[2], 'rb') as state_file:

            (rng, try_count, try_time) = (
                pickle.load(state_file))

    else:

        rng = random.Random()

        try_count = 0
        try_time = 0.0

    # Database stuff.

    table_name = (
        'table_' + str(uuid.uuid4()).replace('-', '_'))

    DBSession.execute('''

        set extra_float_digits to 1;

        create temporary table
        
        {table_name} (
          id integer,
          value_ts timestamp without time zone,
          value_f float8,
          value_j jsonb,
          primary key (id))

        on commit drop;

        '''.format(
            table_name = table_name))

    class Table(Base):

        __tablename__ = table_name

        id = Column(Integer, primary_key = True)
        value_ts = Column(TIMESTAMP)
        value_f = Column(Float)
        value_j = Column(JSONB)

    truncate_sql_str = (
        'truncate table ' + table_name + ';')

    # Initializing iteration.

    run_flag = True

    def sigint_handler(signal, frame):

        global run_flag
        run_flag = False

    signal.signal(
        signal.SIGINT, sigint_handler)

    bits = 53
    N = 2 ** bits
    half = N // 2

    log1m1N = math.log1p(- 2 ** -bits)

    current_time = time.process_time()

    # Iterating until told to stop.

    while run_flag:

        value_list = []

        for i in range(4096):

            value = rng.getrandbits(bits) - half
            try_count += 1

            f = value / 1000000

            d = (
                datetime.datetime.fromtimestamp(
                    f, datetime.timezone.utc))

            # Checking correspondence.

            assert d.timestamp() == f

            s1 = '{:.6f}'.format(f)
            s2 = str(f)
            s3 = json.dumps(f)

            assert float(s1) == f

            assert s1.startswith(s2)
            assert s1[len(s2):] == '0' * (len(s1) - len(s2))
            assert float(s2) == f
            
            assert s1.startswith(s3)
            assert s1[len(s3):] == '0' * (len(s1) - len(s3))
            assert float(s3) == f

            value_list.append({
                'id': i,
                'value_ts': d.replace(tzinfo = None),
                'value_f': f,
                'value_j': [f]})

        # SQLAlchemy / PostgreSQL testing.
        #
        # Started with checking conversions inside PostgreSQL,
        #
        #   (extract(epoch from T.value_ts) = T.value_f and
        #     to_timestamp(T.value_f) at time zone 'UTC' = T.value_ts),
        #
        # found out PostgreSQL's to_timestamp() is sometimes incorrect, see commit's lingvodoc-react issue
        # and <https://www.postgresql.org/message-id/16357-4ed50b3eb9a1a065%40postgresql.org>.

        DBSession.execute(truncate_sql_str)

        DBSession.bulk_insert_mappings(
            Table,
            value_list)

        result = (
                
            DBSession.execute('''

                select

                  T.id,
                  T.value_ts,
                  T.value_f,
                  T.value_j
                    
                from {} T;
                
                '''.format(table_name))

            .fetchall())

        for id, value_ts, value_f, value_j in result:

            value_dict = value_list[id]

            assert value_ts == value_dict['value_ts']
            assert value_f == value_dict['value_f']
            assert value_j == value_dict['value_j']

        # Showing current testing stats.

        previous_time = current_time
        current_time = time.process_time()

        try_time += (
            current_time - previous_time)

        expected = (
            N * (-math.expm1(log1m1N * try_count)))

        log.debug(
            '\n{} tries, {:.3f}s: {:.6f} unique expected, {:.6f} delta'
            '\n  d: {}, f: {:+018.6f}, .6f: {}, str: {}, json: {}'.format(
                try_count,
                try_time,
                expected,
                try_count - expected,
                d.strftime('%a %b %d %H:%M:%S.%f %Z %Y'),
                f,
                repr(s1),
                repr(s2),
                repr(s3)))

        # Additional save state, if required.

        if (not (try_count & 262143) and
            len(sys.argv) > 2):

            with open(
                sys.argv[2], 'wb') as state_file:

                pickle.dump(
                    (rng, try_count, try_time),
                    state_file)

        current_time = time.process_time()

    # Finished testing, saving state if required.

    if len(sys.argv) > 2:

        with open(
            sys.argv[2], 'wb') as state_file:

            pickle.dump(
                (rng, try_count, try_time),
                state_file)

