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

        path = os.path.join(NB_DIR, assignment, '{}_{}.ipynb'.format(
            uid, datetime.now().strftime("%Y%m%d%H%M%S")))

        with open(path, 'w') as f:
            json.dump(notebook, f)

        await nb_queue.put(path)
        # print('Queued', path)

        self.write('Submission for {} received at {}'.format(
            assignment, datetime.now()))
        self.finish()

    def validate(self, request):
        pass

    def write_error(self, status_code, **kwargs):
        self.write('Submission failed.')
        self.finish()


# async def grade():
#     async for nb in nb_queue:
#         print('Grading', nb)
#         await sleep(2)
#         nb_queue.task_done()

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = Application([
        (r"/submit", SubmissionHandler),
    ])
    server = HTTPServer(app)
    server.listen(8888)
    #IOLoop.current().spawn_callback(grade)
    IOLoop.current().start()
