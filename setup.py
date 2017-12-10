
import os

from setuptools import setup, find_packages
from setuptools.command.install import install


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.md')) as f:
    CHANGES = f.read()


class install_with_interface(install):
    """
    Extends 'install' setup.py command with ability to install React-based interface.
    """

    user_options = install.user_options + [
        ('react-interface=', None, 'path to React-based interface distribution')]

    def initialize_options(self):
        install.initialize_options(self)
        self.react_interface = None

    def run(self):
        install.run(self)

        # If we have been given a path to the React-based interface, we install it too.

        if self.react_interface is not None:
            self.announce('Installing React-based interface')

            interface_dir = self.react_interface
            self.ensure_dirname('react_interface')

            install_dir = os.path.join(self.install_lib, 'lingvodoc')

            index_path = os.path.join(interface_dir, 'index.html')
            main_pt_path = os.path.join(
                install_dir, 'views', 'v2', 'templates', 'main.pt')

            if os.path.exists(main_pt_path):
                os.remove(main_pt_path)

            self.copy_file(index_path, main_pt_path)

            assets_dir = os.path.join(interface_dir, 'assets')

            self.copy_tree(assets_dir, os.path.join(
                install_dir, 'assets'))


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
      packages=find_packages(exclude=['tests', 'tests.*']),
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
      cmdclass={'install': install_with_interface},
      )

