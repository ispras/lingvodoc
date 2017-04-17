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
    """
    Must derive from QObject in order to emit signals, connect slots to other signals, and operate in a QThread.
    """

    sig_done = pyqtSignal(int)  # worker id: emitted at end of work()
    sig_err = pyqtSignal(str, str)

    def __init__(self, connection_string, adapter='https://'):
        super().__init__()
        self.connection_string = connection_string
        self.adapter = adapter

    @pyqtSlot()
    def work(self):
        """
        Pretend this worker method does work that takes a long time. During this time, the thread's
        event loop is blocked, except if the application's processEvents() is called: this gives every
        thread (incl. main) a chance to process events, which in this sample means processing signals
        received from GUI (such as abort).
        """
        status_code = -1
        redownload = True
        reunzip = True
        try:

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
            with open('updater\\tmp.zip', 'wb') as file_type:
                shutil.copyfileobj(dump, file_type)

            with ZipFile('updater\\tmp.zip') as myzip:
                if myzip.testzip():
                    self.sig_err.emit(
                        "Try again",
                        "source archive is broken"
                    )
                    status_code = -1
                    return
                myzip.extractall()

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
    if os.path.exists('new_source\\%s' % filename):
        if os.path.exists(filename):
            shutil.copy2(filename, 'backup_control\\%s' % filename)
        shutil.copy2('new_source\\%s' % filename, filename)

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

        qbtn = QPushButton('Download updater', self)
        qbtn.clicked.connect(self.giant_func)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(20, 70)
        self.qbtn = qbtn

        quitbt = QPushButton('Cancel', self)
        quitbt.clicked.connect(self.quit)
        quitbt.resize(quitbt.sizeHint())
        quitbt.move(150, 70)
        quitbt.setDisabled(True)
        self.quitbt = quitbt

        self.setGeometry(300, 300, 400, 100)
        self.setWindowTitle('Update Downloader')
        self.show()

    @pyqtSlot()
    def startWorker(self, connection_string, adapter='https://'):
        worker = Worker(connection_string, adapter)
        thread = QThread()
        worker.moveToThread(thread)
        worker.sig_done.connect(self.setDownloadStatus)
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

    def workerLoop(self, connection_string, adapter='https://'):
        self.startWorker(connection_string, adapter)
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
        if not os.path.exists('updater'):
            os.mkdir('updater')
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
        processes = []
        try:
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
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
            server = status.json()
            if server['id'] <= tag:
                box = QMessageBox()
                box.move(50, 50)
                self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
                QMessageBox.information(box, "No update needed", "Already last version", QMessageBox.Ok)
                return
            assets = server['assets']
            new_update = None

            for asset in assets:
                if asset['name'] == 'update.zip':
                    new_update = asset['browser_download_url']

            if not new_update:
                self.message(
                    "No updater found",
                    "Release contains no updater"
                )
                return

            # new_update = 'https://www.dropbox.com/s/6stohg7cxcawi9c/update.zip?dl=1'
            if os.path.exists('update1.pyw'):
                os.remove('update1.pyw')
            if os.path.exists('update2.pyw'):
                os.remove('update2.pyw')
            if self.workerLoop(new_update, 'https://'):
                return

            self.changetext("Updating in progress. New updater downloaded. Running updater")

            pythonw = cur_path + "\\env86\\python-3.4.4\\pythonw.exe"
            proc = Popen([pythonw, "%s\\update1.pyw" % cur_path], creationflags=DETACHED_PROCESS, stdout=PIPE, stderr=PIPE)

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

