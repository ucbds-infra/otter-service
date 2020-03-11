import os
import json
import logging
import traceback
import tornado.options
import queries
from datetime import datetime
from tornado.httpserver import HTTPServer
from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop
from tornado.queues import Queue
from tornado.gen import sleep


nb_queue = Queue()
NB_DIR = os.environ.get('NOTEBOOK_DIR')


class SubmissionHandler(RequestHandler):
    def initialize(self):
        self.session = queries.TornadoSession(queries.uri(host='localhost', port=5432, dbname='otter_db', user='admin', password=None))


    async def post(self):
        request = tornado.escape.json_decode(self.request.body)
        notebook = request['nb']
        await self.submit(notebook)
        self.write('Submission received.')
        self.finish()


    async def validate(self, notebook):
        assert all(key in notebook for key in ['metadata', 'nbformat', 'nbformat_minor', 'cells']), 'invalid notebook'
        assignment_id = notebook['metadata']['assignment_id']
        # timeout
        # verify api key
        results = await self.session.query("SELECT * FROM assignments WHERE assignment_id=%s LIMIT 1", [assignment_id])
        assert results, 'assignment_id {} not found'.format(assignment_id)
        assignment = results.as_dict()
        results.free()
        
        return (assignment['class_id'], assignment_id, assignment['assignment_name'])


    async def submit(self, notebook):
        class_id, assignment_id, assignment_name = await self.validate(notebook)

        results = await self.session.query("SELECT nextval(pg_get_serial_sequence('submissions', 'submission_id')) as id")
        submission_id = results.as_dict()['id']
        results.free()

        dir_path = os.path.join(NB_DIR,
                                'submissions',
                                'class-{}'.format(class_id),
                                'assignment-{}'.format(assignment_id),
                                'submission-{}'.format(submission_id))
        file_path = os.path.join(dir_path, '{}.ipynb'.format(assignment_name))

        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        with open(file_path, 'w') as f:
            json.dump(notebook, f)

        results = await self.session.query("INSERT INTO submissions (submission_id, assignment_id, file_path, timestamp) VALUES (%s, %s, %s, %s)",
                                            [submission_id, assignment_id, file_path, datetime.now()])
        assert results, 'submission failed'
        results.free()

        await nb_queue.put(file_path)
        print('Queued', file_path)


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
