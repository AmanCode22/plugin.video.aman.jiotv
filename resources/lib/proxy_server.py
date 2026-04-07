# -*- coding: utf-8 -*-

import socket
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode, quote
import xbmc
from resources.lib.utils import getLivePlayUrl, getCatchupUrl, jio_playheaders


class TokenRefreshProxy(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    timeout = 30

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        original_url = self.path[1:] if self.path.startswith('/') else self.path
        try:
            req = urllib.request.Request(original_url)
            for header, value in self.headers.items():
                if header.lower() not in ('host', 'connection', 'proxy-connection'):
                    req.add_header(header, value)
            response = urllib.request.urlopen(req, timeout=self.timeout)
            self.send_response(response.getcode())
            for header, value in response.headers.items():
                if header.lower() not in ('content-encoding', 'transfer-encoding', 'connection'):
                    self.send_header(header, value)
            self.end_headers()
            self.wfile.write(response.read())
            response.close()
        except urllib.error.HTTPError as e:
            if e.code == 403:
                xbmc.log("[Proxy] 403, refreshing token", xbmc.LOGINFO)
                new_url = self.refresh_stream_url(original_url)
                if new_url:
                    try:
                        req2 = urllib.request.Request(new_url)
                        for header, value in self.headers.items():
                            if header.lower() not in ('host', 'connection', 'proxy-connection'):
                                req2.add_header(header, value)
                        response2 = urllib.request.urlopen(req2, timeout=self.timeout)
                        self.send_response(response2.getcode())
                        for header, value in response2.headers.items():
                            if header.lower() not in ('content-encoding', 'transfer-encoding', 'connection'):
                                self.send_header(header, value)
                        self.end_headers()
                        self.wfile.write(response2.read())
                        response2.close()
                    except Exception:
                        self.send_error(500, "Refresh failed")
                else:
                    self.send_error(403, "Token expired")
            else:
                self.send_error(e.code, str(e))
        except Exception:
            self.send_error(500, "Proxy error")

    def refresh_stream_url(self, old_url):
        parsed = urlparse(old_url)
        qs = parse_qs(parsed.query)
        if 'srno' in qs:
            srno = qs['srno'][0]
            begin = qs['begin'][0]
            end = qs['end'][0]
            showtime = qs['showtime'][0]
            channel_id = qs['channelid'][0]
            new_url = getCatchupUrl(channel_id, srno, begin, end, showtime)
            cookies_part = new_url.split("?")[1]
            if "bpk-tv" in cookies_part:
                cookie = "_" + cookies_part.split("&_")[1]
            elif "/HLS/" in cookies_part:
                cookie = "_" + cookies_part.split("&_")[1]
            else:
                cookie = cookies_part
            headers = jio_playheaders(cookie, channel_id, srno)
            header_str = urlencode(headers, quote_via=quote)
            return new_url + f"|{header_str}&verifypeer=false"
        else:
            channel_id = qs.get('channelid', [None])[0]
            if not channel_id:
                return None
            new_url = getLivePlayUrl(channel_id)
            cookies_part = new_url.split("?")[1]
            if "bpk-tv" in cookies_part:
                cookie = "_" + cookies_part.split("&_")[1]
            elif "/HLS/" in cookies_part:
                cookie = "_" + cookies_part.split("&_")[1]
            else:
                cookie = cookies_part
            headers = jio_playheaders(cookie, channel_id, "250623144006")
            header_str = urlencode(headers, quote_via=quote)
            return new_url + f"|{header_str}&verifypeer=false"


def start_proxy():
    server = HTTPServer(('127.0.0.1', 0), TokenRefreshProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def stop_proxy(server):
    if server:
        server.shutdown()
