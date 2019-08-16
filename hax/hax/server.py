from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import json
from hax.types import Fid


class KVHandler(BaseHTTPRequestHandler):
    def __init__(self, req, client_addr, server):
        super().__init__(req, client_addr, server)
        self.server = server

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        s = json.dumps({'message': 'I am alive'})
        self.wfile.write(s.encode('utf-8'))

    def do_HEAD(self):
        self._set_headers()

    def do_POST(self):
        self._set_headers()
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        logging.debug('POST request received: {}'.format(post_data))

        ha_states = self.to_ha_states(self.parse_request(post_data))
        logging.info('HA states: {}'.format(ha_states))
        # TODO instead of this call something to m0d must be done
        self.server.halink.broadcast_ha_states(ha_states)

    @staticmethod
    def parse_request(raw_data):
        try:
            return json.loads(raw_data.decode('utf-8'))
        except json.JSONDecodeError:
            logging.warn('Invalid JSON object received')

    @staticmethod
    def to_ha_states(data):
        """Converts a dictionary, obtained from JSON data, into a list of
        HA states.

        Format of an HA state: {'fid': <service fid>, 'status': <state>},
        where <state> is either 'online' or 'offline'.
        """
        if not data:
            return []

        def get_status(checks):
            ok = all(x.get('Status') == 'passing' for x in checks)
            return 'online' if ok else 'offline'

        result = []
        for t in data:
            result.append({
                'fid': Fid.parse(t['Service']['ID']),
                'status': get_status(t['Checks'])
            })
        return result


def run_server(thread_to_wait=None,
               server_class=HTTPServer,
               port=8080,
               halink=None):
    port = 8080
    server_address = ('', port)
    httpd = server_class(server_address, KVHandler)
    httpd.halink = halink

    logging.info('Starting HTTP server...')
    try:
        httpd.serve_forever()
    finally:
        if thread_to_wait is not None:
            thread_to_wait.is_stopped = True
            thread_to_wait.join()
        logging.info('The http server has stopped')
