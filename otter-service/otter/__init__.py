from tornado.httpserver import HTTPServer
from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop


class SubmissionHandler(RequestHandler):
  def post(self):
    self.write("Received Submission")

if __name__ == "__main__":
  app = Application([
    (r"/submit", SubmissionHandler),
  ])
  server = HTTPServer(app)
  server.listen(8888)
  IOLoop.current().start()