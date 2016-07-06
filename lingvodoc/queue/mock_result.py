__author__ = 'alexander'


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
