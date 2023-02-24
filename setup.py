
import os
import os.path

import textwrap

import git

from setuptools import setup, find_packages

from setuptools.command.develop import develop
from setuptools.command.install import install

from lingvodoc import (
    get_git_version,
    get_uniparser_version)


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.md')) as f:
    CHANGES = f.read()


class React_Interface_Mixin(object):
    """
    Adds ability to set up React-based interface to setuptools commands.
    """

    user_options = [
        ('react-interface=', None, 'path to React-based interface distribution')]

    def initialize_options(self):
        """
        Initializes standard setuptools' command options and a React interface option.
        """

        super().initialize_options()
        self.react_interface = None

    def run(self):
        """
        Sets up React-based interface if required.
        """

        super().run()

        if self.react_interface is not None:

            self.setup_react_interface(

                os.path.join(
                    getattr(self, self.__react_path_attr__),
                    'lingvodoc'))

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


class Version_Mixin(object):
    """
    Tries to determine version from the Git repository state and pip installation state.
    """

    version_py_template = textwrap.dedent(
    
        '''\

        # This file is overwritten on setup.
        #
        # Please do not modify it and ignore its changes in version control.

        __version__ = {}

        uniparser_version_dict = {}

        ''')

    def run(self):
        """
        Tries to determine version info from the Git repository and pip installation state, saves it to
        'lingvodoc/version.py' if required.
        """

        version_str = (
            get_git_version(here))

        version_uniparser_dict = (
            get_uniparser_version())

        if (version_str is not None or
            version_uniparser_dict is not None):

            with open(
                os.path.join(here, 'lingvodoc', 'version.py'), 'w',
                encoding = 'utf-8') as version_py_file:

                version_py_file.write(
                    self.version_py_template.format(
                        repr(version_str),
                        repr(version_uniparser_dict)))

        # Continuing with setup.

        super().run()


class develop_with_interface(
    React_Interface_Mixin,
    develop):
    """
    Extends 'develop' setup.py command with ability to develop React-based interface.
    """

    __react_path_attr__ = 'egg_path'

    user_options = (
        develop.user_options +
        React_Interface_Mixin.user_options)


class install_with_interface(
    React_Interface_Mixin,
    Version_Mixin,
    install):
    """
    Extends 'install' setup.py command with ability to install React-based interface and update version from
    the Git repository state.
    """

    __react_path_attr__ = 'install_lib'

    user_options = (
        install.user_options +
        React_Interface_Mixin.user_options)


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

