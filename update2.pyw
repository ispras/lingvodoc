import os
from time import sleep
from sys import executable
from subprocess import Popen
from subprocess import PIPE
from subprocess import call
from subprocess import STARTUPINFO
from subprocess import STARTF_USESHOWWINDOW
from alembic import command
from alembic.config import Config
import ctypes
import requests
import shutil
from zipfile import ZipFile
from alembic.util.exc import CommandError
import traceback
import sys
from PyQt5.QtWidgets import (QWidget, QPushButton, QLineEdit, QLabel,
                             QInputDialog, QApplication, QMessageBox, QProgressBar)

from PyQt5.QtCore import QCoreApplication, QEventLoop
from PyQt5 import QtCore


class CommonException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


DETACHED_PROCESS = 8

DELAY = 2
CUR_PATH = os.path.abspath(os.path.dirname(__file__))
updater_path = CUR_PATH + "\\updater"
PG_DATA = "%s\\PostgreSQLPortable_9.6.1\\Data\\data" % CUR_PATH
PG_CTL = "%s\\PostgreSQLPortable_9.6.1\\App\\PgSQL\\bin\\pg_ctl.exe" % CUR_PATH
CHROME_PATH = "%s\\ChromiumPortable\\App\\Chromium\\32\\chrome.exe" % CUR_PATH
LINGVODOC_PATH = "%s\\PostgreSQLPortable_9.6.1\\lingvodoc.py" % CUR_PATH
PG_RESTORE = False


def get_env():
    venv = os.environ.copy()
    venv["PATH"] = "%s\\PostgreSQLPortable_9.6.1\\App\\PgSQL\\bin;%s" % (CUR_PATH, venv["PATH"])
    venv["PGDATA"] = "%s\\PostgreSQLPortable_9.6.1\\Data\\data" % CUR_PATH
    venv["PGDATABASE"] = "postgres"
    venv["PGUSER"] = "postgres"
    venv["PGPORT"] = "5439"
    venv["PGLOCALEDIR"] = "%s\\PostgreSQLPortable_9.6.1\\App\PgSQL\\share\\locale" % CUR_PATH
    return venv


def kill_em_all(processes):
    proc = Popen([PG_CTL, "-D", PG_DATA, "stop"])
    proc.wait()
    for process in processes:
        process.terminate()


def running(processname):
    SW_HIDE = 0
    info = STARTUPINFO()
    info.dwFlags = STARTF_USESHOWWINDOW
    info.wShowWindow = SW_HIDE
    task_call = 'TASKLIST', '/FI', 'imagename eq %s' % processname
    task_out = str(Popen(task_call, stdout=PIPE, startupinfo=info).communicate())
    return processname in task_out


def restore(source, backup):
    shutil.move(source, source + "_tmp")
    shutil.move(backup, source)


def remove(src):
    if os.path.exists(src):
        shutil.rmtree(src)


def backup_control(filename):
    if os.path.exists('source\\%s' % filename):
        shutil.copy2(filename, '%s\\backup_control\\%s' % (updater_path, filename))
        shutil.copy2('source\\%s' % filename, filename)


class Example(QWidget):
    def __init__(self):
        super().__init__()

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
        self.progress.setValue(65)

        qbtn = QPushButton('Start update', self)
        # qbtn.clicked.connect(self.giant_func)
        qbtn.resize(qbtn.sizeHint())
        qbtn.move(20, 70)
        qbtn.setDisabled(True)

        quitbt = QPushButton('Cancel', self)
        # quitbt.clicked.connect(self.quit)
        quitbt.resize(quitbt.sizeHint())
        quitbt.move(100, 70)
        quitbt.setDisabled(True)

        self.setGeometry(300, 300, 400, 100)
        self.setWindowTitle('Update part 2')
        self.show()

    def changetext(self, text):
        self.le.setText(text)
        self.le.resize(self.le.sizeHint())
        self.show()
        self.loop.processEvents(QEventLoop.AllEvents)

    def message(self, title, text):
        box = QMessageBox()
        box.move(50, 50)
        QMessageBox.critical(box, title, text, QMessageBox.Ok)

    def giant_func(self):
        flags = self.windowFlags()
        self.setWindowFlags(QtCore.Qt.Window
                            | QtCore.Qt.WindowMinimizeButtonHint
                            | QtCore.Qt.WindowMaximizeButtonHint)
        self.changetext("Update in progress. Database updating")
        tag = 5003530
        pg_restore = False
        alembic_config = CUR_PATH + "\\alembic.ini"
        SW_HIDE = 0
        info = STARTUPINFO()
        info.dwFlags = STARTF_USESHOWWINDOW
        info.wShowWindow = SW_HIDE
        postgres_backup = "%s\\postgres_data_backup" % updater_path
        restore_lock = "%s\\restore_fail" % updater_path
        restore_fail = False
        processes = []
        try:
            # if os.path.exists(restore_lock):
            #     restore_fail = True
            # if restore_fail and os.path.exists(postgres_backup):
            #     restore(PG_DATA, postgres_backup)
            #     os.remove(restore_lock)
            # remove(postgres_backup)
            # remove(PG_DATA + "_tmp")
            shutil.copytree(PG_DATA, postgres_backup)
            self.progress.setValue(70)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
            if running("postgres.exe"):
                self.message("Failure", "Cannot update:\n\nPostgres already running, turn off Lingvodoc"
                                        "(or standalone Postgres) for updating")
                return
            proc = Popen(["%s\\PostgreSQLPortable_9.6.1\\App\\PgSQL\\bin\\postgres.exe" % CUR_PATH, "-D", PG_DATA],
                         startupinfo=info)
            processes.append(proc)
            self.progress.setValue(75)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)
            tag_path = "%s\\new_tag" % updater_path
            if os.path.exists(tag_path):
                with open(tag_path, 'r') as tag_file:
                    try:
                        tag = int(tag_file.read())
                    except ValueError as e:
                        raise CommonException('incorrect tag format')
            else:
                raise CommonException('no new_tag file')
            self.progress.setValue(80)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)

            try:
                sleep(5)
                alembic_cfg = Config(alembic_config)
                command.upgrade(alembic_cfg, "head")
            except Exception as e:
                self.message("Failure", "Database upgrade failure:\n\n%s" % e.args)
                traceback_string = "\n".join(traceback.format_list(traceback.extract_tb(e.__traceback__)))
                self.message(
                    "Failure",
                    "Please send this message to developers: \n\n %s" % traceback_string
                )
                if type(e) != CommandError:
                    pg_restore = True
                return
            self.progress.setValue(95)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)

            old_ini = "%s\\lingvodoc_desktop.ini" % CUR_PATH
            tmp_ini = '%s\\tmp.ini' % CUR_PATH

            if os.path.exists(tmp_ini):
                os.remove(tmp_ini)
            with open(tmp_ini, 'w') as new_file:
                with open(old_ini, 'r') as file:
                    for line in file:
                        if '[cache:dogpile]' not in line:
                            new_file.write(line)
                        else:
                            new_file.write(line)
                            break
                    new_text = "expiration_time = 36000\nbackend = dogpile.cache.memcached\n" \
                               "\n[cache:dogpile:args]\nurl = localhost:11211\ndistributed_lock = True\n"
                    new_file.write(new_text)
                    pass

            os.remove(old_ini)
            os.rename(tmp_ini, old_ini)
            if os.path.exists(tmp_ini):
                os.remove(tmp_ini)

            box = QMessageBox()
            box.move(50, 50)

            with open("%s\\tag" % updater_path, 'w') as tag_file:
                tag_file.write(str(tag))
            os.remove(tag_path)
            box = QMessageBox()
            box.move(50, 50)
            self.progress.setValue(100)
            self.loop.processEvents(QEventLoop.ExcludeUserInputEvents)

            QMessageBox.information(box, "Success", "Updated successfully", QMessageBox.Ok)

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
            kill_em_all(processes)
            # pg_restore = True
            if pg_restore:
                with open(restore_lock, 'w') as lock_file:
                    lock_file.write('fail')
                restore(PG_DATA, postgres_backup)
                os.remove(restore_lock)
            app.quit()
            return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = Example()
    ex.giant_func()
    # sys.exit(app.exec_())
