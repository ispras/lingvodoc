
import os

from setuptools import setup, find_packages

from setuptools.command.develop import develop
from setuptools.command.install import install


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.md')) as f:
    CHANGES = f.read()


class React_Interface_Mixin(object):
    """
    Adds ability to set up React-based interface to setuptools commands.
    """

    def initialize_options(self):
        """
        Initializes standard setuptools' command options and a React interface option.
        """

        super().initialize_options()
        self.react_interface = None

    def setup_react_interface(self, lingvodoc_dir):
        """
        Sets up React-based interface by copying its distribution files to appropriate locations.
        """

        self.announce('Installing React-based interface')

        interface_dir = os.path.expanduser(self.react_interface)

        index_from_path = os.path.join(interface_dir, 'index.html')

        index_to_path = os.path.join(lingvodoc_dir,
            'views', 'v2', 'templates', 'new_interface.pt')

        if os.path.exists(index_to_path):
            os.remove(index_to_path)

        self.copy_file(index_from_path, index_to_path)

        assets_dir = os.path.join(interface_dir, 'assets')

        self.copy_tree(assets_dir, os.path.join(
            lingvodoc_dir, 'assets'))


class develop_with_interface(React_Interface_Mixin, develop):
    """
    Extends 'develop' setup.py command with ability to develop React-based interface.
    """

    user_options = develop.user_options + [
        ('react-interface=', None, 'path to React-based interface distribution')]

    def run(self):
        """
        Runs development installation, sets up React-based interface if required.
        """

        develop.run(self)

        if self.react_interface is not None:

            self.setup_react_interface(
                os.path.join(self.egg_path, 'lingvodoc'))


class install_with_interface(React_Interface_Mixin, install):
    """
    Extends 'install' setup.py command with ability to install React-based interface.
    """

    user_options = install.user_options + [
        ('react-interface=', None, 'path to React-based interface distribution')]

    def run(self):
        """
        Performs installation, then installs React-based interface if required.
        """

        install.run(self)

        if self.react_interface is not None:

            self.setup_react_interface(
                os.path.join(self.install_lib, 'lingvodoc'))


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
      cmdclass={
          'develop': develop_with_interface,
          'install': install_with_interface},
      )

