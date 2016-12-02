__author__ = 'alexander'
from multiprocess import Process

class MockResult:
    """
    This class is used when Celery is disabled. This class implements all used methods of
    Celery's AsyncResult class
    """

    def __init__(self, result):
        self.result = result

    def ready(self):
        return True

    def get(self, *args, **kwargs):
        return self.result


class MockApp:
    """
    This class is used when Celery is disabled. The class mocks Celery class. Provides a `task`
    decorator for wrapping tasks. The wrapped method becomes an object of the class MockTask which
    method `delay` executes provided function as soon as the method is called.
    """

    def task(self, func):
        class MockTask:

            def delay(self, *args, **kwargs):
                # return MockResult(Process(target=func, args=args, kwargs=kwargs))
                p = Process(target=func, args=args, kwargs=kwargs) #MockResult()
                p.start()
                return True#MockResult(func(*args, **kwargs))

        return MockTask()
