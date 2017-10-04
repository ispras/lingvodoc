import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.md')) as f:
    CHANGES = f.read()

requires = [
    'pyramid',
    ]

setup(name='lingvodoc',
      version='2.1.1',
      description='lingvodoc',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='Oleg Borisenko',
      author_email='al@somestuff.ru',
      url='https://lingvodoc.ispras.ru/',
      keywords='web wsgi bfg pylons pyramid sqlalchemy',
      packages=find_packages(exclude=['tests']),
      include_package_data=True,
      zip_safe=False,
      test_suite='lingvodoc',
      install_requires=requires,
      entry_points="""\
      [paste.app_factory]
      main = lingvodoc:main
      [console_scripts]
      initialize_lingvodoc_db = lingvodoc.scripts.initializedb:main
      """,
      )
