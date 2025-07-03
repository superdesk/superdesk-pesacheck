import unittest
import flask


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.app = flask.Flask(__name__)
        self.app.config.update(
            {
                "URN_DOMAIN": "pesacheck.com",
            }
        )
        self.app.app_context().push()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()
