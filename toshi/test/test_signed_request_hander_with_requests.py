import asyncio
import unittest
import requests
import time
import os

import toshi.web
import tornado.web
import tornado.ioloop
import tornado.httpserver

import threading

from toshi.ethereum.utils import private_key_to_address
from toshi.test.utils import get_unused_port
from toshi.request import sign_request

from toshi.test.test_signed_request_handler import SimpleHandler
from toshi.handlers import TOSHI_TIMESTAMP_HEADER, TOSHI_SIGNATURE_HEADER, TOSHI_ID_ADDRESS_HEADER

TEST_PRIVATE_KEY = "0xe8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
TEST_ADDRESS = "0x056db290f8ba3250ca64a45d16284d04bc6f5fbf"

class ToshiAuth(requests.auth.AuthBase):

    def __init__(self, signing_key):
        self.address = private_key_to_address(signing_key)
        self.signing_key = signing_key

    def __call__(self, r):

        method = r.method
        path = "/{}".format(r.url.split('/', 3)[-1])
        body = r.body

        timestamp = int(time.time())

        signature = sign_request(self.signing_key, method, path, timestamp, body)

        r.headers[TOSHI_ID_ADDRESS_HEADER] = self.address
        r.headers[TOSHI_SIGNATURE_HEADER] = signature
        r.headers[TOSHI_TIMESTAMP_HEADER] = str(timestamp)

        return r

class TornadoServer(threading.Thread):

    def __init__(self, port):
        super().__init__()

        self.port = port

        self.aioloop = asyncio.new_event_loop()
        self.application = toshi.web.Application([
            ("^/?$", SimpleHandler)
        ])
        self._server = tornado.httpserver.HTTPServer(self.application)

    def run(self):
        asyncio.set_event_loop(self.aioloop)
        self.ioloop = tornado.ioloop.IOLoop.current()
        self._server.listen(self.port, '127.0.0.1')
        self.ioloop.start()

    def stop(self):
        self.ioloop.add_callback(self.ioloop.stop)
        self.join()

class TestRequestsClient(unittest.TestCase):

    def get_url(self, path):
        return "http://localhost:{}{}".format(self.server_address[1], path)

    def setUp(self):
        self.server_address = ('', get_unused_port())

        self.httpd_thread = TornadoServer(self.server_address[1])
        self.httpd_thread.start()

    def tearDown(self):
        self.httpd_thread.stop()

    def test_requests_file_upload(self):

        # generate random 2048 byte "file"
        filedata = os.urandom(2048)

        resp = requests.post(self.get_url("/"), files=[("file", ("test.bin", filedata, 'application/octet-stream'))],
                             auth=ToshiAuth(TEST_PRIVATE_KEY))

        self.assertEqual(resp.status_code, 204)
