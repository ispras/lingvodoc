
import glob
import os
import shutil

from setuptools import setup, find_packages
from setuptools.command.install import install


here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.md')) as f:
    CHANGES = f.read()


#
# Extenstion of 'install' setup.py command performed along the lines of
# http://stackoverflow.com/a/1321345/2016856.
#
# See also setup.py of https://github.com/eliben/pycparser.
#


def install_desktop_files(source_dir, lib_dir):
    """
    Install additional files for desktop version, see webui/deploy-desktop.sh.
    """

    webui_dir = os.path.join(source_dir, 'webui')
    install_dir = os.path.join(lib_dir, 'lingvodoc')

    def copy(from_path, to_path):
        shutil.copy(from_path, to_path)
        print('shutil.copy({0}, {1})'.format(repr(from_path), repr(to_path)))

    def copytree(from_path, to_path):

        if os.path.exists(to_path):
            shutil.rmtree(to_path)
            print('shutil.rmtree({0})'.format(repr(to_path)))

        shutil.copytree(from_path, to_path)
        print('shutil.copytree({0}, {1})'.format(repr(from_path), repr(to_path)))

    # cp artifacts/desktop/js/* ../lingvodoc/static/js/

    artifacts_desktop_dir = os.path.join(webui_dir, 'artifacts', 'desktop')
    install_js_dir = os.path.join(install_dir, 'static', 'js')

    for path in glob.glob(os.path.join(artifacts_desktop_dir, 'js', '*')):
        copy(path, install_js_dir)

    # cp desktop/src/templates/main.pt ../lingvodoc/views/v2/templates/main.pt

    copy(
        os.path.join(webui_dir, 'desktop', 'src', 'templates', 'main.pt'),
        os.path.join(install_dir, 'views', 'v2', 'templates', 'main.pt'))

    # cp artifacts/desktop/templates/*.html ../lingvodoc/static/templates/

    templates_dir = os.path.join(artifacts_desktop_dir, 'templates')
    install_templates_dir = os.path.join(install_dir, 'static', 'templates')

    for path in glob.glob(os.path.join(templates_dir, '*.html')):
        copy(path, install_templates_dir)

    # cp -r artifacts/desktop/templates/modal/ ../lingvodoc/static/templates/
    # cp -r artifacts/desktop/templates/include/ ../lingvodoc/static/templates/

    for name in ['modal', 'include']:

        copytree(
            os.path.join(templates_dir, name),
            os.path.join(install_templates_dir, name))

    # cp shared/src/css/*.css ../lingvodoc/static/css/

    install_css_dir = os.path.join(install_dir, 'static', 'css')

    for path in glob.glob(os.path.join(webui_dir, 'shared', 'src', 'css', '*.css')):
        copy(path, os.path.join(install_css_dir))

    # cp shared/src/images/* ../lingvodoc/static/images/

    install_images_dir = os.path.join(install_dir, 'static', 'images')

    for path in glob.glob(os.path.join(webui_dir, 'shared', 'src', 'images', '*')):
        copy(path, os.path.join(install_images_dir))


class install_desktop(install):
    """
    Extends 'install' setup.py command by additional installation of desktop version files.
    """

    def run(self):
        install.run(self)

        self.execute(
            install_desktop_files,
            (here, self.install_lib,),
            msg = 'Installing additional desktop version files')


requires = [
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
      cmdclass={'install': install_desktop},
      )
