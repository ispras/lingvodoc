__author__ = 'alexander'

from lingvodoc.queue.celery import QUEUED_TASKS


class QueueClient:

    @classmethod
    def update_progress(cls, task_id, percent):
        """
        Update progress bar for a task
        :param task_id: id of the task
        :param percent: progress value
        """
        QUEUED_TASKS.progress_store.set(task_id, percent)

    @classmethod
    def generate_task_id(cls, client_id):
        """
        Generates unique task id for a client
        :param client_id: Client for whom to generate a value.
        :return: task id of string
        """
        return QUEUED_TASKS.progress_store.generate_task_id(client_id)

    @classmethod
    def add_task(cls, user, task_key, async_task):
        """
        Adds a task to store. If you run a task and want to watch it - add it here!
        :param user: the user whom this task belongs to
        :param task_key: task id
        :param async_task: the async task object. Usually it is `celery.result.AsyncResult`
        """
        QUEUED_TASKS.set(user, task_key, async_task)

    @classmethod
    def get_tasks_info(cls, user):
        """
        Get a status of user's tasks
        :param user:
        :return: a dictionary of tasks
        """
        # Pass False if you don't want your tasks to be deleted from Redis when they're finished.
        return QUEUED_TASKS.get(user, False)
