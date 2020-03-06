import os
import json
import logging
import traceback
import tornado.options
from datetime import datetime
from tornado.httpserver import HTTPServer
from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop
from tornado.queues import Queue
from tornado.gen import sleep

nb_queue = Queue()
NB_DIR = os.environ.get('NOTEBOOK_DIR')

class SubmissionHandler(RequestHandler):
    async def post(self):
        request = tornado.escape.json_decode(self.request.body)
        notebook = request['nb']
        assignment = request['assignment']
        uid = request['user_id']

        self.validate(request)

        class_id = 0
        assignment_id = 0
        submission_id = 0
        file_name = ''

        path = os.path.join(NB_DIR,
                            'submissions',
                            'class-{}'.format(class_id),
                            'assignment-{}'.format(assignment_id),
                            'submission-{}'.format(submission_id),
                            file_name)

        with open(path, 'w') as f:
            json.dump(notebook, f)

        await nb_queue.put(path)
        print('Queued', path)

        self.write('Submission for {} received at {}'.format(assignment, datetime.now()))
        self.finish()

    def validate(self, request):
        assert all(key in request['nb'] for key in ['metadata', 'nbformat', 'nbformat_minor', 'cells']), 'invalid notebook'
        # timeout
        # verify api key
        # verify assignment

    def write_error(self, status_code, **kwargs):
        self.write('Submission failed.')
        self.finish()


async def grade():
    async for nb in nb_queue:
        print('Grading', nb)
        await sleep(2)
        nb_queue.task_done()

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = Application([
        (r"/submit", SubmissionHandler),
    ])
    server = HTTPServer(app)
    server.listen(8888)
    IOLoop.current().spawn_callback(grade)
    IOLoop.current().start()
