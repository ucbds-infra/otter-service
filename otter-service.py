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
from sqlalchemy import create_engine  
from sqlalchemy import Column, String  
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.types import JSON
from sqlalchemy.types import TIMESTAMP
from models import *
from grade import *

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

class Submission(base):
    __tablename__ = 'submissions'

    submission_id = Column(String, primary_key=True) 
    assignment_id = Column(String) 
    file_path = Column(String)
    timestamp = Column(TIMESTAMP)
    score = Column(JSON)

async def grade():
    base = declarative_base()
    async for nb in nb_queue:
        print('Grading', nb)
        await sleep(2)
        CLIENT = docker.from_env()
        assignment_id = None # TODO: get assignment id for nb
        assert os.path.isfile("conf.yml"), "conf.yml does not exist"
        with open("conf.yml") as f:
            config = yaml.safe_load(f)
        assignment_info = [a for a in config["assignments"] if a["assignment_id"] == assignment_id][0]
        grade_assignment(assignment_info["tests_path"], nb, TODO, image=TODO, reqs=TODO)
        nb_queue.task_done()

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/submit", SubmissionHandler),
        ]
        settings = dict(
            cookie_secret="some_long_secret_and_other_settins"
        )
        tornado.web.Application.__init__(self, handlers, **settings)
        # Have one global connection.
        db_string = "postgres://admin:donotusethispassword@aws-us-east-1-portal.19.dblayer.com:15813/compose"
        engine = create_engine(db_string)
        self.db = scoped_session(sessionmaker(bind=engine))

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = Application()
    server = HTTPServer(app)
    server.listen(8888)
    #IOLoop.current().spawn_callback(grade)
    IOLoop.current().start()