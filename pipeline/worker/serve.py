"""Tiny read-only file server for the GPU box: lets the orchestrator (or a browser) fetch
status.log and final.mp4. CORS is open so a browser tab can pull the video directly."""
import functools
import http.server
import sys


class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path):  # no directory listings; you need the token path
        self.send_error(404)


port, root = int(sys.argv[1]), sys.argv[2]
http.server.ThreadingHTTPServer(("0.0.0.0", port), functools.partial(H, directory=root)).serve_forever()
