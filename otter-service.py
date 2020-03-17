import os
import json
import yaml
import jwt
import logging
import traceback
import tornado.options
import queries
from datetime import datetime
from tornado.httpserver import HTTPServer
from tornado.web import Application, RequestHandler
from tornado.auth import GoogleOAuth2Mixin
from tornado.ioloop import IOLoop
from tornado.queues import Queue
from tornado.gen import sleep

nb_queue = Queue()

class GoogleOAuth2LoginHandler(RequestHandler, GoogleOAuth2Mixin):
    async def get(self):
        if not self.get_argument('code', False):
            return self.authorize_redirect(
                redirect_uri=self.settings['auth_redirect_uri'],
                client_id=self.settings['google_oauth']['key'],
                scope=['email', 'profile'],
                response_type='code',
                extra_params={'approval_prompt': 'auto'}
            )
        else:
            resp = await self.get_authenticated_user(
                redirect_uri=self.settings['auth_redirect_uri'],
                code=self.get_argument('code')
            )
            api_key = resp['access_token']
            email = jwt.decode(resp['id_token'], verify=False)['email']
            results = await self.db.query("""
                                          INSERT INTO users (api_key, email) VALUES (%s, %s)
                                          ON CONFLICT (email) DO UPDATE SET api_key = EXCLUDED.api_key
                                          """,
                                          [api_key, email])
            results.free()

            self.write(api_key)
            self.finish()

    @property
    def db(self):
        return self.application.db


class SubmissionHandler(RequestHandler):
    async def post(self):
        request = tornado.escape.json_decode(self.request.body)
        assert 'nb' in request.keys()
        assert 'api_key' in request.keys()
        notebook = request['nb']
        api_key = request['api_key']

        try:
            await self.submit(notebook, api_key)
            self.write('Submission received.')
            self.finish()
        except:
            return


    async def validate(self, notebook, api_key):
        # authenticate user with api_key
        results = await self.db.query("SELECT user_id FROM users WHERE api_key=%s LIMIT 1", [api_key])
        user_id = results.as_dict()['user_id'] if len(results) > 0 else None
        results.free()
        assert user_id, 'invalid api key'

        # rate limit one submission every 2 minutes
        results = await self.db.query("SELECT timestamp FROM submissions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 1", [2])
        last_submitted = results.as_dict()['timestamp'] if len(results) > 0 else None
        results.free()

        if last_submitted:
            delta = datetime.utcnow() - last_submitted
            rate_limit = 120
            if delta.seconds < rate_limit:
                self.write_error(429, message='Please wait {} second(s) before re-submitting.'.format(rate_limit - delta.seconds))
                return


        # check valid Jupyter notebook
        assert all(key in notebook for key in ['metadata', 'nbformat', 'nbformat_minor', 'cells']), 'invalid notebook'
        assignment_id = notebook['metadata']['assignment_id']
        
        results = await self.db.query("SELECT * FROM assignments WHERE assignment_id=%s LIMIT 1", [assignment_id])
        assert results, 'assignment_id {} not found'.format(assignment_id)
        assignment = results.as_dict()
        results.free()

        return (user_id, assignment['class_id'], assignment_id, assignment['assignment_name'])


    async def submit(self, notebook, api_key):
        user_id, class_id, assignment_id, assignment_name = await self.validate(notebook, api_key)

        # fetch next submission id
        results = await self.db.query("SELECT nextval(pg_get_serial_sequence('submissions', 'submission_id')) as id")
        submission_id = results.as_dict()['id']
        results.free()

        # save notebook to disk
        dir_path = os.path.join(self.settings['notebook_dir'],
                                'submissions',
                                'class-{}'.format(class_id),
                                'assignment-{}'.format(assignment_id),
                                'submission-{}'.format(submission_id))
        file_path = os.path.join(dir_path, '{}.ipynb'.format(assignment_name))
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(file_path, 'w') as f:
            json.dump(notebook, f)
        
        # store submission to database
        results = await self.db.query("INSERT INTO submissions (submission_id, assignment_id, user_id, file_path, timestamp) VALUES (%s, %s, %s, %s, %s)",
                                            [submission_id, assignment_id, user_id, file_path, datetime.utcnow()])
        assert results, 'submission failed'
        results.free()

        # queue user for grading
        # TODO: don't queue if user already queued
        await nb_queue.put(user_id)
        print('queued user {}'.format(user_id))

    @property
    def db(self):
        return self.application.db

    def write_error(self, status_code, **kwargs):
        if 'message' in kwargs:
            self.write(kwargs['message'])
        else:
            self.write('Submission failed.')
        self.finish()


async def grade():
    async for nb in nb_queue:
        print('Grading', nb)
        await sleep(2)
        nb_queue.task_done()


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/submit", SubmissionHandler),
            (r"/google_auth", GoogleOAuth2LoginHandler)
        ]
        with open("conf.yml") as f:
            config = yaml.safe_load(f)
        settings = dict(
            google_oauth={
                'key': config['google_auth_key'],
                'secret': config['google_auth_secret'],
            },
            notebook_dir = config['notebook_dir'],
            auth_redirect_uri = config['auth_redirect_uri']
        )
        tornado.web.Application.__init__(self, handlers, **settings)
        # Initialize database session
        self.db = queries.TornadoSession(queries.uri(
            host=config['db_host'],
            port=config['db_port'],
            dbname='otter_db',
            user=config['db_user'],
            password=config['db_pass'])
        )


if __name__ == "__main__":
    tornado.options.parse_command_line()
    server = HTTPServer(Application())
    server.listen(8888)
    IOLoop.current().spawn_callback(grade)
    IOLoop.current().start()
