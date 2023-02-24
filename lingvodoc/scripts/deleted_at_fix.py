
# Standard library imports.

import datetime
import logging
import pdb
import pprint
import sys
import time

# External imports.

import pyramid.paster as paster

from sqlalchemy import column, func, literal_column
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql.expression import Grouping

import transaction

from zope.sqlalchemy import mark_changed

# Project imports.

from lingvodoc.models import (
    DBSession,
    ObjectTOC,
)


# Setting up logging, if we are not being run as a script.

if __name__ != '__main__':
    log = logging.getLogger(__name__)


def fix_standard():
    """
    Fixed 'deleted_at' fields using standard SQLAlchemy ORM, reports all encountered values of time shift
    errors.
    """

    # Going through metadata with 'deleted_at' data and fixing it.

    filter_query = (

        DBSession
        .query(ObjectTOC)
        .filter(

            DBSession
            .query()
            .select_from(func.jsonb_each(ObjectTOC.additional_metadata))
            .filter(column('value').op('?')('deleted_at'))
            .exists()))

    object_toc_count = 0
    deleted_at_delta_set = set()

    start_time = time.time()

    for object_toc in filter_query.yield_per(256):

        # Wrong value:
        #
        #   deleted_at = int(datetime.datetime.utcnow().timestamp())
        #
        # Fixed value:
        #
        #   int(datetime.datetime
        #     .fromtimestamp(deleted_at)
        #     .replace(tzinfo = datetime.timezone.utc)
        #     .timestamp())
        #
        # See docs at https://docs.python.org/3.6/library/datetime.html.

        for key, value in object_toc.additional_metadata.items():

            deleted_at_wrong = value['deleted_at']

            deleted_at_fixed = int(

                datetime.datetime
                  .fromtimestamp(deleted_at_wrong)
                  .replace(tzinfo = datetime.timezone.utc)
                  .timestamp())

            value['deleted_at_wrong'] = deleted_at_wrong
            value['deleted_at'] = deleted_at_fixed

            flag_modified(object_toc, 'additional_metadata')

            # Saving fix difference info, showing modification.

            deleted_at_delta = (
                deleted_at_fixed - deleted_at_wrong)

            deleted_at_delta_set.add(
                deleted_at_delta)

            log.debug(
                '\nObjectTOC {}/{} [{}], \'{}\': '
                '\'deleted_at_wrong\': {}, \'deleted_at\': {}, {:+d}'.format(
                    object_toc.client_id,
                    object_toc.object_id,
                    object_toc_count,
                    key,
                    deleted_at_wrong,
                    deleted_at_fixed,
                    deleted_at_delta))

        # Processed another ObjectTOC recotd.

        object_toc_count += 1

    # Showing processing info.

    transaction.commit()

    elapsed_time = (
        time.time() - start_time)

    log.debug(
        '\nobject_toc_count: {}'
        '\ndeleted_at_delta_set ({}): {}'
        '\nelapsed_time: {:.3f}s'.format(
            object_toc_count,
            len(deleted_at_delta_set),
            deleted_at_delta_set,
            elapsed_time))


# If we are being run as a script.

if __name__ == '__main__':

    if len(sys.argv) < 2:

        sys.exit(
            'Please specify config file:\n'
            '  python -m lingvodoc.scripts.deleted_at_fix <config_file_path>')

    config_path = sys.argv[1]

    pyramid_env = paster.bootstrap(config_path)
    paster.setup_logging(config_path)

    log = logging.getLogger(__name__)

    # Checking if the fix was already applied.
    #
    #   select exists (
    #
    #     select 1
    #     from ObjectTOC
    #     where exists(
    #    
    #       select 1
    #       from jsonb_each(additional_metadata)
    #       where value ? 'deleted_at_wrong'));
    #

    filter_query = (

        DBSession
        .query(ObjectTOC)
        .filter(

            DBSession
            .query()
            .select_from(func.jsonb_each(ObjectTOC.additional_metadata))
            .filter(column('value').op('?')('deleted_at_wrong'))
            .exists()))

    already = (

        DBSession
        .query(filter_query.exists())
        .scalar())

    if already:

        sys.exit(
            'ObjectTOC has metadata with \'deleted_at_wrong\' keys, '
            'assuming fix already applied, '
            'doing nothig.')

    # We can do simple fix, at the same time checking which values of time shift erorrs we have.

    if (len(sys.argv) <= 2 or
        sys.argv[2] == 'standard'):

        fix_standard()

    # Otherwise we perform fix efficiently by making adjustments inside Postgres via SQL.
    #
    # We checked with the 14th Mar 2020 dump that only encountered time shift error is +10800, it depends
    # only on the difference between server timezone and UTC timezone, and server time zone will not change
    # until the moment of fix script launch.
    #
    # So, we can perform fix by just adding 10800 to the 'deleted_at' values.

    elif (
        len(sys.argv) > 2 and
        sys.argv[2] == 'fast'):

        start_time = time.time()

        DBSession.execute('''

            update
              ObjectTOC

            set
              additional_metadata =  (
                  
                select
                  jsonb_object_agg(
                    key,
                    case
                    when value ? 'deleted_at'
                    then value ||
                      jsonb_build_object(
                        'deleted_at_wrong', value -> 'deleted_at',
                        'deleted_at', (value ->> 'deleted_at') :: int + 10800)
                    else value
                    end)

                from
                  jsonb_each(additional_metadata))

            where exists(

              select 1
              from jsonb_each(additional_metadata)
              where value ? 'deleted_at');

            ''')

        mark_changed(DBSession())
        transaction.commit()

        elapsed_time = (
            time.time() - start_time)

        log.debug(
            '\nelapsed_time: {:.3f}s'.format(
                elapsed_time))

    # Unknown command-line argument.

    else:

        log.debug(
            'Unknown command-line argument \'{}\'.'.format(
                sys.argv[2]))

