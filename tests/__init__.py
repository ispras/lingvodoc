#
#                        How tests are organized and how they should work
#
# Tests should be run with pytest, with current configuration (see tox.ini file) it is enough to run
# '$VENV/bin/py.test' from the lingvodoc's root directory.
#
# We have tests from the previous version, and we should ultimately have functional tests for each REST API
# request (see lingvodoc/__init__.py file for supported APIs).
#
# Each REST API functional test should clearly identify API it tests, e.g. by mentioning its name in a
# comment.
#
# Tests from the previous version that are not yet modified to work with the current one are marked with
# pytest's skip markers (see http://doc.pytest.org/en/latest/skipping.html). Until all tests from the
# previous version are converted, before creating a new API test please check if there is an unconverted
# test of this API from the previous version, and, if indeed there is, convert it instead of creating a new
# one.
#

"""
Various tests for the Lingvodoc's Python source code.
"""

