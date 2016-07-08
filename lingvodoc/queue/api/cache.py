__author__ = 'alexander'


# TODO: It has to be an abstract class in the future. Read `abc — Abstract Base Classes`
class ITaskCache:

    def get(self, user, remove_finished):
        """
        Gets a dictionary of tasks for the user
        :param user: User whose tasks we're looking for
        :param remove_finished: If True then all finished tasks will be deleted from the store and
        its IDs will be removed from the user's list of tasks.
        :return: a dictionary of tasks {'Task ID (hash)': {'Finished': (True/False), 'Percent': int}}.
        If there is no tasks then the return value is an empty dict.
        """
        raise NotImplementedError

    def set(self, user, task_key, async_task):
        """
        Put a task object in cache
        :param user: User which ran the task
        :param task_key: any unique value representing the task
        :param async_task: object representing async task. Usually it's `celery.result.AsyncResult`
        """
        raise NotImplementedError
