import os
from time import sleep
from sys import executable
from subprocess import Popen
from subprocess import PIPE
from subprocess import call
from subprocess import STARTUPINFO
from subprocess import STARTF_USESHOWWINDOW
from PyQt5.QtWidgets import QMessageBox, QApplication
import sys
import traceback

DETACHED_PROCESS = 8

DELAY = 2
cur_path = os.path.abspath(os.path.dirname(__file__))
PG_DATA = "%s\\PostgreSQLPortable_9.6.1\\Data\\data" % cur_path
PG_CTL = "%s\\PostgreSQLPortable_9.6.1\\App\\PgSQL\\bin\\pg_ctl.exe" % cur_path
CHROME_PATH = "%s\\ChromiumPortable\\App\\Chromium\\32\\chrome.exe" % cur_path
LINGVODOC_PATH = "%s\\PostgreSQLPortable_9.6.1\\lingvodoc.py" % cur_path

def get_env():
    venv = os.environ.copy()
    venv["PATH"] = "%s\\PostgreSQLPortable_9.6.1\\App\\PgSQL\\bin;%s" % (cur_path, venv["PATH"])
    venv["PGDATA"] = "%s\\PostgreSQLPortable_9.6.1\\Data\\data" % cur_path
    venv["PGDATABASE"] = "postgres"
    venv["PGUSER"] = "postgres"
    venv["PGPORT"] = "5439"
    venv["PGLOCALEDIR"] = "%s\\PostgreSQLPortable_9.6.1\\App\PgSQL\\share\\locale" % cur_path
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


def message(title, text):
    box = QMessageBox()
    box.move(50, 50)
    QMessageBox.critical(box, title, text, QMessageBox.Ok)


def main():
    app = QApplication(sys.argv)
    processes = list()
    try:
        # postgres_backup = "%s\\postgres_data_backup" % cur_path
        restore_lock = "%s\\restore_fail" % cur_path
        restore_fail = False
        processes = []
        if os.path.exists(restore_lock):
            restore_fail = True
        if restore_fail:
            message('Failure', 'Try running update again. If this repeats - contact developers')
            sys.exit(-1)
        python = cur_path + "\\env86\\python-3.4.4\\pythonw.exe"
        pserve = cur_path + "\\env86\\python-3.4.4\\Scripts\\pserve.exe"
        memcached = cur_path + "\\new_memcached\\memcached.exe"
        development = cur_path + "\\lingvodoc_desktop.ini"
        venv = get_env()
        # if not os.path.exists(venv["PGDATA"]):
        # proc_0 = Popen('%s\\PostgreSQLPortable_9.6.1\\App\\PgSQL\\bin\\initdb.exe -U postgres -A trust -E utf8 --locale=C' % cur_path, env=venv, shell=True)
        # proc_0.communicate()
        SW_HIDE = 0
        info = STARTUPINFO()
        info.dwFlags = STARTF_USESHOWWINDOW
        info.wShowWindow = SW_HIDE
        # if not running("postgres.exe"): #, startupinfo=info
        proc_2 = Popen(["%s\\PostgreSQLPortable_9.6.1\\App\\PgSQL\\bin\\postgres.exe" % cur_path, "-D", PG_DATA],
                       startupinfo=info)
        # proc_2.wait()
        # proc_2.terminate()
        sleep(5)
        my_env = os.environ.copy()
        my_env["PATH"] = my_env["PATH"] + ";%s\\new_ffmpeg\\bin" % cur_path
        proc_3 = Popen([python, pserve, development], env=my_env, creationflags=DETACHED_PROCESS)
        sleep(1)
        proc_4 = Popen([memcached], creationflags=DETACHED_PROCESS)
        sleep(1)
        proc_1 = Popen(args=[CHROME_PATH, "http://localhost:6543/"])
        # processes = (proc_1, proc_2, proc_3)  # (proc_1, proc_2, proc_3)
        processes = (proc_1, proc_2, proc_3, proc_4)  # (proc_1, proc_2, proc_3)
        sleep(10)
        while True:
            for process in processes:
                if process.poll() is not None or not running("postgres.exe"):
                    kill_em_all(processes)
                    return
            sleep(DELAY)

    except OSError as e:  # is there need for that?
        message(
            "Failure",
            "failure:\n\n%s" % e.args[len(e.args) - 1]
        )
        traceback_string = "\n".join(traceback.format_list(traceback.extract_tb(e.__traceback__)))
        message(
            "Failure",
            "Please send this message to developers: \n\n %s" % traceback_string
        )
    except Exception as e:
        message(
            "Failure",
            "failure:\n\n%s" % e.args
        )
        traceback_string = "\n".join(traceback.format_list(traceback.extract_tb(e.__traceback__)))
        message(
            "Failure",
            "Please send this message to developers: \n\n %s" % traceback_string
        )
    finally:
        kill_em_all(processes)
        return


if __name__ == "__main__":
    main()
