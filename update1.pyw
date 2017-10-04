import os
from time import sleep
from subprocess import Popen
from subprocess import PIPE
import requests
import shutil
from zipfile import ZipFile
import traceback
from glob import glob
import sys
from PyQt5.QtWidgets import (
    QWidget,
    QPushButton,
    QLabel,
    QApplication,
    QMessageBox,
    QProgressBar
)
import hashlib
from PyQt5.QtCore import QEventLoop, QObject, pyqtSlot, pyqtSignal, QThread
from PyQt5 import QtCore

DETACHED_PROCESS = 8
cur_path = os.path.abspath(os.path.dirname(__file__))
updater_path = cur_path + "\\updater"

PG_DATA = "%s\\PostgreSQLPortable_9.6.1\\Data\\data" % cur_path


def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def folder_md5(fname):
    hash_md5 = hashlib.md5()
    for filename in glob(fname + '/*'):
        if os.path.isfile(filename):
            with open(filename, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
    return hash_md5.hexdigest()


class Worker(QObject):

    sig_done = pyqtSignal(int)  # worker id: emitted at end of work()
    sig_msg = pyqtSignal(str)
    sig_progress = pyqtSignal(int)
    sig_err = pyqtSignal(str, str)

    def __init__(self, connection_string, tag, file_type='source', adapter='https://'):
        super().__init__()
        self.connection_string = connection_string
        self.tag = tag
        self.file_type = file_type
        self.adapter = adapter

    @pyqtSlot()
    def work(self):
        status_code = -1
        redownload = True
        reunzip = True
        try:

            file_type_hash_path = "%s\\%s_hash_%s" % (updater_path, self.file_type, self.tag)
            file_type_path = "%s\\%s_%s.zip" % (updater_path, self.file_type, self.tag)
            new_file_type_hash_path = "%s\\new_%s_hash" % (updater_path, self.file_type)
            new_file_type = '%s\\new_%s' % (updater_path, self.file_type)

            if os.path.exists(file_type_hash_path) and os.path.exists(file_type_path):
                with open(file_type_hash_path, 'r') as file_type_hash:
                    if md5(file_type_path) == file_type_hash.read():
                        redownload = False

            if not redownload and os.path.exists(new_file_type_hash_path) and os.path.exists(new_file_type):
                with open(new_file_type_hash_path, 'r') as file_type_hash:
                    if folder_md5(new_file_type) == file_type_hash.read():
                        reunzip = False

            if redownload:
                # self.sig_err.emit('title', 'dirty source')
                connection_string = self.connection_string
                session = requests.Session()
                session.headers.update({'Connection': 'Keep-Alive'})
                adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
                session.mount(self.adapter, adapter)

                file = requests.get(connection_string, stream=True)

                if file.status_code != 200:
                    self.sig_err.emit(
                        "No internet connection",
                        "Couldn\'t connect to github:\n\ncheck your internet connection"
                    )
                    status_code = -1
                    return
                status_code = 200
                dump = file.raw

                # self.sig_progress.emit(30)
                if os.path.exists(file_type_path):
                    os.remove(file_type_path)
                with open(file_type_path, 'wb') as file_type:
                    shutil.copyfileobj(dump, file_type)

                # urllib.urlretrieve(url, file_type_path)

                with open(file_type_hash_path, 'w') as file_type_hash:
                    file_type_hash.write(md5(file_type_path))
            else:
                status_code = 200
            if reunzip:
                # self.sig_err.emit('title', 'dirty zip')
                # sys.exit(-1)
                with ZipFile(file_type_path) as myzip:
                    folder = myzip.namelist()[0]
                    if myzip.testzip():
                        self.sig_err.emit(
                            "Try again",
                            "source archive is broken"
                        )
                        status_code = -1
                        return
                    myzip.extractall(path=updater_path)
                if os.path.exists(new_file_type):
                    shutil.rmtree(new_file_type)
                folder = updater_path + "\\" + folder.split('/')[0]
                # self.sig_progress.emit(50)
                new_file_type = updater_path + "\\new_%s" % self.file_type

                # remove(new_file_type)
                os.rename(folder, new_file_type)
                if os.path.exists(new_file_type_hash_path):
                    os.remove(new_file_type_hash_path)
                with open(new_file_type_hash_path, 'w') as file_type_hash:
                    file_type_hash.write(folder_md5(new_file_type))

                for path in glob("%s\\%s_*.zip" % (updater_path, self.file_type)):
                    if path != file_type_path:
                        os.remove(path)
                for path in glob("%s\\%s_hash_*" % (updater_path, self.file_type)):
                    if path != file_type_hash_path:
                        os.remove(path)
            # self.sig_msg.emit("Updating in progress. Sources Downloaded. Upgrading pip.")
            # self.sig_progress.emit(55)

        except OSError as e:
            status_code = -1
            self.sig_err.emit(
                "Failure",
                "failure:\n\n%s" % e.args[len(e.args) - 1]
            )
            traceback_string = "\n".join(traceback.format_list(traceback.extract_tb(e.__traceback__)))
            self.sig_err.emit(
                "Failure",
                "Please send this message to developers: \n\n %s" % traceback_string
            )
        except Exception as e:
            status_code = -1
            self.sig_err.emit(
                "Failure",
                "failure:\n\n%s" % e.args
            )
            traceback_string = "\n".join(traceback.format_list(traceback.extract_tb(e.__traceback__)))
            self.sig_err.emit(
                "Failure",
                "Please send this message to developers: \n\n %s" % traceback_string
            )
        finally:
            # status_code = -1
            self.sig_done.emit(status_code)
            return

def backup_control(filename):
    if os.path.exists('source\\%s' % filename):
        if os.path.exists(filename):
            shutil.copy2(filename, '%s\\backup_control\\%s' % (updater_path, filename))
        shutil.copy2('source\\%s' % filename, filename)

class Example(QWidget):
    def __init__(self):
        super().__init__()
        self.downloaded = False
        self.canceled = False
        self.status = -1
        self.initUI()

    def initUI(self):

        self.le = QLabel(self)
        self.le.move(20, 25)
        text = ''
        self.le.setText(str(text))
        self.le.resize(self.le.sizeHint())
        self.loop = QEventLoop()

        self.progress = QProgressBar(self)
        self.progress.move(20, 45)
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.reset()
        self.progress.resize(self.progress.sizeHint())

        qbtn = QPushButton('Start update', self)
        qbtn.clicked.connect(self.giant_func)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(20, 70)
        self.qbtn = qbtn

        quitbt = QPushButton('Cancel', self)
        quitbt.clicked.connect(self.quit)
        quitbt.resize(quitbt.sizeHint())
        quitbt.move(100, 70)
        quitbt.setDisabled(True)
        self.quitbt = quitbt

        self.setGeometry(300, 300, 400, 100)
        self.setWindowTitle('Update part 1')
        self.show()

    @pyqtSlot()
    def startWorker(self, connection_string, tag, type='source', adapter='https://'):

        worker = Worker(connection_string, tag, type, adapter)
        thread = QThread()
        worker.moveToThread(thread)
        worker.sig_done.connect(self.setDownloadStatus)
        worker.sig_msg.connect(self.changetext)
        worker.sig_err.connect(self.message)
        thread.started.connect(worker.work)
        thread.start()
        self.thread = thread
        self.worker = worker

    def getDownloaded(self):
        self.loop.processEvents(QEventLoop.AllEvents)
        return self.downloaded

    def setDownloadStatus(self, status):
        self.status = status
        self.setDownloaded()

    def setProgress(self, value):
        self.progress.setValue(value)
        self.loop.processEvents(QEventLoop.AllEvents)

    def setDownloaded(self, downloaded=True):
        self.downloaded = downloaded
        self.loop.processEvents(QEventLoop.AllEvents)

    def getCanceled(self):
        self.loop.processEvents(QEventLoop.AllEvents)
        return self.canceled

    def setCanceled(self, canceled=True):
        self.canceled = canceled
        self.loop.processEvents(QEventLoop.AllEvents)

    def quit(self):
        self.setCanceled()

    def changetext(self, text):
        self.le.setText(text)
        self.le.resize(self.le.sizeHint())
        self.show()
        self.loop.processEvents(QEventLoop.AllEvents)

    def message(self, title, text):
        box = QMessageBox()
        box.move(50, 50)
        QMessageBox.critical(box, title, text, QMessageBox.Ok)

    def workerLoop(self, connection_string, tag, type='source', adapter='https://'):
        self.startWorker(connection_string, tag, type, adapter)
        self.quitbt.setEnabled(True)
        while not self.getDownloaded():
            sleep(0.1)
            if self.getCanceled():
                box = QMessageBox()
                box.move(50, 50)
                reply = QMessageBox.warning(box,
                                            "Cancel",
                                            "Are you sure you want to cancel downloading?",
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    sys.exit(-1)
                else:
                    self.canceled = False
        self.quitbt.setDisabled(True)
        self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
        self.thread.quit()
        self.thread.wait()

        self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
        if self.status != 200:
            return -1
        return 0

    def giant_func(self):
        self.qbtn.setDisabled(True)
        self.loop.processEvents(QEventLoop.AllEvents)
        flags = self.windowFlags()
        self.setWindowFlags(QtCore.Qt.Window
                            | QtCore.Qt.WindowMinimizeButtonHint
                            | QtCore.Qt.WindowMaximizeButtonHint)
        self.changetext("Update in progress. Downloading sources.")
        tag = 500353  # 0
        tag_path = "%s\\tag" % updater_path
        new_tag_path = "%s\\new_tag" % updater_path
        if os.path.exists(tag_path):
            with open(tag_path, 'r') as tag_file:
                try:
                    tag = int(tag_file.read())
                except ValueError as e:
                    pass
        else:
            with open(tag_path, 'w') as tag_file:
                tag_file.write(str(tag))
        postgres_backup = "%s\\postgres_data_backup" % updater_path
        restore_lock = "%s\\restore_fail" % updater_path
        processes = []
        try:
            if os.path.exists(restore_lock):
                if os.path.exists(postgres_backup):
                    restore(PG_DATA, postgres_backup)
                os.remove(restore_lock)
            remove(postgres_backup)
            remove(PG_DATA + "_tmp")
            connection_string = "https://api.github.com/repos/ispras/lingvodoc/releases/latest"
            session = requests.Session()
            session.headers.update({'Connection': 'Keep-Alive'})
            adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
            session.mount('https://', adapter)
            status = session.get(connection_string)  # create worker for this

            if status.status_code != 200:
                self.message(
                    "No internet connection",
                    "Couldn\'t connect to github:\n\ncheck your internet connection"
                )
                return
            self.progress.setValue(10)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
            server = status.json()
            if server['id'] <= tag:
                box = QMessageBox()
                box.move(50, 50)
                self.progress.setValue(100)
                self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
                QMessageBox.information(box, "No update needed", "Already last version", QMessageBox.Ok)
                return
            new_tag = server['id']
            with open(new_tag_path, 'w') as tag_file:
                tag_file.write(str(new_tag))
            self.progress.setValue(10)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)

            connection_string = server['zipball_url']
            assets = server['assets']
            ffmpeg = None
            memcached = None
            for asset in assets:
                if asset['name'] == 'ffmpeg.zip':
                    ffmpeg = asset['browser_download_url']
                if asset['name'] == 'memcached.zip':
                    memcached = asset['browser_download_url']

            # connection_string = "https://codeload.github.com/ispras/lingvodoc/zip/heavy_refactor"  # todo: remove
            # connection_string = "https://codeload.github.com/LukeTapekhin/lingvodoc/zip/heavy_refactor"  # todo: remove
            if self.workerLoop(connection_string, new_tag, 'source', 'https://'):
                return
            self.changetext("Updating in progress. Sources downloaded. Downloading memcached")
            self.progress.setValue(30)

            # memcached = "https://www.dropbox.com/s/j73nstxm8xze17z/memchached.zip?dl=1"  # todo: remove
            if memcached:
                if self.workerLoop(memcached, '123432', 'memcached', 'https://'):
                    return
            self.changetext("Updating in progress. Memcached downloaded. Downloading ffmpeg")
            self.progress.setValue(35)

            # ffmpeg = "https://ffmpeg.zeranoe.com/builds/win32/static/ffmpeg-3.2.4-win32-static.zip"
            if ffmpeg:
                if self.workerLoop(ffmpeg, '3.2.4', 'ffmpeg', 'https://'):
                    return
            self.changetext("Updating in progress. Ffmpeg downloaded. Updating packages")
            self.progress.setValue(50)

            if os.path.exists('ffmpeg'):
                shutil.rmtree('ffmpeg')
            shutil.copytree('%s\\new_ffmpeg' % updater_path, 'ffmpeg')
            if os.path.exists('memcached'):
                shutil.rmtree('memcached')
            shutil.copytree('%s\\new_memcached' % updater_path, 'memcached')
            if os.path.exists('source'):
                shutil.rmtree('source')
            shutil.copytree('%s\\new_source' % updater_path, 'source')

            new_source = cur_path + "\\source"
            pythonw = cur_path + "\\env86\\python-3.4.4\\pythonw.exe"
            setup = new_source + "\\desktop-setup.py"
            requirements = new_source + "\\desktop-requirements.txt"

            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)

            proc = Popen([pythonw, '-m', 'pip', 'install', '-r', os.path.normpath(requirements)], stdout=PIPE,
                         stderr=PIPE)
            streamdata = proc.communicate()[1]
            rc = proc.returncode
            if rc != 0:
                self.message(
                    "Try again",
                    "packages update unsuccessful: %s" % streamdata.decode("utf-8")
                )
                return
            proc.terminate()
            self.changetext("Updating in progress. Packages updated. Setuping")
            self.progress.setValue(60)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)

            if os.path.exists('source/build'):
                remove('source/build')
            proc = Popen([pythonw, setup, 'install'], stdout=PIPE, stderr=PIPE, cwd='%s\\source' % cur_path)
            streamdata = proc.communicate()[1]
            rc = proc.returncode
            if rc != 0:
                self.message(
                    "Try again",
                    "setup unsuccessful: %s" % streamdata.decode("utf-8")
                )
                return
            proc.terminate()
            if os.path.exists('source/build'):
                remove('source/build')
            self.changetext("Updating in progress. Setup complete. Starting database update")
            self.progress.setValue(65)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)

            if not os.path.exists('%s\\backup_control' % updater_path):
                os.makedirs('%s\\backup_control' % updater_path)

            if os.path.exists('%s\\alembic.ini' % new_source):
                backup_control('alembic.ini')

            if os.path.exists('%s\\alembic' % new_source):
                if os.path.exists('%s\\alembic' % new_source):
                    if os.path.exists('alembic'):
                        if os.path.exists('%s\\backup_control\\%s' % (updater_path, 'alembic')):
                            shutil.rmtree('%s\\backup_control\\%s' % (updater_path, 'alembic'))
                        shutil.copytree('alembic', '%s\\backup_control\\%s' % (updater_path, 'alembic'))
                        shutil.rmtree('alembic')
                    shutil.copytree('%s\\%s' % (new_source, 'alembic'), 'alembic')

            proc = Popen([pythonw, "%s\\update2.pyw" % cur_path], creationflags=DETACHED_PROCESS, stdout=PIPE, stderr=PIPE)
            return

        except OSError as e:
            self.message(
                "Failure",
                "failure:\n\n%s" % e.args[len(e.args) - 1]
            )
            traceback_string = "\n".join(traceback.format_list(traceback.extract_tb(e.__traceback__)))
            self.message(
                "Failure",
                "Please send this message to developers: \n\n %s" % traceback_string
            )
        except Exception as e:
            self.message(
                "Failure",
                "failure:\n\n%s" % e.args
            )
            traceback_string = "\n".join(traceback.format_list(traceback.extract_tb(e.__traceback__)))
            self.message(
                "Failure",
                "Please send this message to developers: \n\n %s" % traceback_string
            )
        finally:
            app.quit()
            return


def restore(source, backup):
    shutil.move(source, source + "_tmp")
    shutil.move(backup, source)


def remove(src):
    if os.path.exists(src):
        shutil.rmtree(src)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())

