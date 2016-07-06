__author__ = 'alexander'

from lingvodoc.queue.mock_result import MockResult


class MockApp:
    """
    This class is used when Celery is disabled. This class implements necessary interface for executing
    tasks with `task` method.
    """

    def task(self, func):
        class MockTask:

            def delay(self, *args, **kwargs):
                return MockResult(func(*args, **kwargs))

        return MockTask()
