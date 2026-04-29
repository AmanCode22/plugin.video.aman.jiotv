# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote, urlparse
import xbmc

CHUNK_SIZE = 65536

class JioTVProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 30
    
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self._handle()

    def do_HEAD(self):
        self._handle(send_body=False)

    def _handle(self, send_body=True):
        try:
            target_url = unquote(self.path.lstrip("/"))
            
            req = urllib.request.Request(target_url)
            for k, v in self.headers.items():
                if k.lower() not in ("host", "connection"):
                    req.add_header(k, v)
            
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content = resp.read() if send_body else b""
                    
                    if target_url.endswith(".m3u8") or ".m3u8" in target_url:
                        content = self._rewrite_manifest(content, target_url)
                        if target_url.endswith(".m3u8"):
                            self.server._store_base(target_url)
                    
                    self.send_response(resp.getcode())
                    for k, v in resp.headers.items():
                        kl = k.lower()
                        if kl not in ("transfer-encoding", "connection", "content-length"):
                            self.send_header(k, v)
                    if send_body:
                        self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    if send_body:
                        self.wfile.write(content)
                        
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    self._handle_expired(target_url, send_body)
                else:
                    self.send_error(e.code, str(e.reason))
                    
        except Exception as e:
            xbmc.log("[JioTV Proxy] Error: " + str(e), xbmc.LOGERROR)
            self.send_error(500, str(e))

    def _rewrite_manifest(self, content, base_url):
        try:
            text = content.decode("utf-8")
            lines = text.split("\n")
            result = []
            
            base_parsed = urlparse(base_url)
            base_path = base_parsed.path.rsplit("/", 1)[0] + "/"
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    result.append(line)
                    continue
                
                if line_stripped.startswith("http"):
                    full_url = line_stripped
                else:
                    full_url = base_parsed.scheme + "://" + base_parsed.netloc + base_path + line_stripped
                
                proxy_url = self.server.proxy_base + quote(full_url, safe="")
                result.append(proxy_url)
            
            return "\n".join(result).encode("utf-8")
        except Exception as e:
            xbmc.log("[JioTV Proxy] Rewrite error: " + str(e), xbmc.LOGERROR)
            return content

    def _handle_expired(self, original_url, send_body):
        try:
            from resources.lib.utils import getLivePlayUrl, getCatchupUrl, jio_playheaders, _extract_cookie
            
            info = self.server.playback_info
            if not info:
                self.send_error(403, "No playback info")
                return
            
            channel_id = info.get("channel_id")
            if not channel_id:
                self.send_error(403, "No channel ID")
                return
            
            try:
                if info.get("is_catchup"):
                    fresh_master = getCatchupUrl(
                        channel_id,
                        info.get("srno"),
                        info.get("begin"),
                        info.get("end"),
                        info.get("showtime")
                    )
                else:
                    fresh_master = getLivePlayUrl(channel_id)
            except Exception as e:
                xbmc.log("[JioTV Proxy] Fetch error: " + str(e), xbmc.LOGERROR)
                self.send_error(403, "Fetch failed")
                return
            
            if not fresh_master:
                self.send_error(403, "Empty URL")
                return
            
            self.server._store_master(fresh_master)
            
            if self._is_master(original_url):
                cookie = _extract_cookie(fresh_master)
                headers = jio_playheaders(cookie, channel_id, info.get("srno", "250623144006"))
                req = urllib.request.Request(fresh_master)
                for k, v in headers.items():
                    req.add_header(k, str(v))
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content = resp.read()
                    content = self._rewrite_manifest(content, fresh_master)
                    self._send_content(content, resp.getcode(), send_body)
                return
            
            if self._is_variant(original_url):
                orig_file = original_url.split("/")[-1].split("?")[0]
                cookie = _extract_cookie(fresh_master)
                headers = jio_playheaders(cookie, channel_id, info.get("srno", "250623144006"))
                req = urllib.request.Request(fresh_master)
                for k, v in headers.items():
                    req.add_header(k, str(v))
                with urllib.request.urlopen(req, timeout=30) as resp:
                    master_content = resp.read().decode("utf-8")
                
                fresh_variant = self._find_variant(master_content, fresh_master, orig_file)
                if not fresh_variant:
                    self.send_error(403, "Variant not found")
                    return
                
                self.server._store_base(fresh_variant)
                
                req = urllib.request.Request(fresh_variant)
                for k, v in headers.items():
                    req.add_header(k, str(v))
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content = resp.read()
                    content = self._rewrite_manifest(content, fresh_variant)
                    self._send_content(content, resp.getcode(), send_body)
                return
            
            cookie = _extract_cookie(fresh_master)
            headers = jio_playheaders(cookie, channel_id, info.get("srno", "250623144006"))
            
            req = urllib.request.Request(fresh_master)
            for k, v in headers.items():
                req.add_header(k, str(v))
            with urllib.request.urlopen(req, timeout=30) as resp:
                master_content = resp.read().decode("utf-8")
            
            orig_file = original_url.split("/")[-1].split("?")[0]
            fresh_variant = self._find_variant(master_content, fresh_master, orig_file)
            
            if not fresh_variant:
                self.send_error(403, "Variant not found")
                return
            
            fresh_base = fresh_variant.rsplit("/", 1)[0] + "/"
            fresh_segment = fresh_base + orig_file
            
            req = urllib.request.Request(fresh_segment)
            for k, v in headers.items():
                req.add_header(k, str(v))
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read()
                self._send_content(content, resp.getcode(), send_body)
                
        except Exception as e:
            xbmc.log("[JioTV Proxy] Expired error: " + str(e), xbmc.LOGERROR)
            self.send_error(403, "Refresh failed")

    def _is_master(self, url):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8")
            return "#EXT-X-STREAM-INF" in content
        except:
            return False

    def _is_variant(self, url):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8")
            return "#EXTINF" in content and "#EXT-X-STREAM-INF" not in content
        except:
            return False

    def _find_variant(self, master_content, master_url, orig_file):
        try:
            lines = master_content.split("\n")
            base_parsed = urlparse(master_url)
            base_path = base_parsed.path.rsplit("/", 1)[0] + "/"
            
            for i, line in enumerate(lines):
                if "#EXT-X-STREAM-INF" in line:
                    if i + 1 < len(lines):
                        variant = lines[i + 1].strip()
                        if variant.startswith("http"):
                            full = variant
                        else:
                            full = base_parsed.scheme + "://" + base_parsed.netloc + base_path + variant
                        return full
        except:
            pass
        return None

    def _send_content(self, content, code, send_body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        if send_body:
            self.wfile.write(content)


class JioTVProxyServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.proxy_base = None
        self.playback_info = None
        self._master_url = None
        self._base_url = None
        self._lock = threading.Lock()
    
    def _store_master(self, url):
        with self._lock:
            self._master_url = url
    
    def _store_base(self, url):
        with self._lock:
            self._base_url = url


_proxy_server = None
_proxy_port = None
_proxy_lock = threading.Lock()

def start_hls_proxy():
    global _proxy_server, _proxy_port
    with _proxy_lock:
        if _proxy_server is None:
            server = JioTVProxyServer(("127.0.0.1", 0), JioTVProxyHandler)
            port = server.server_address[1]
            server.proxy_base = "http://127.0.0.1:" + str(port) + "/"
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            _proxy_server = server
            _proxy_port = port
            xbmc.log("[JioTV Proxy] Started on port " + str(port), xbmc.LOGINFO)
    return _proxy_server, _proxy_port

def set_playback_info(info):
    global _proxy_server
    if _proxy_server:
        _proxy_server.playback_info = info

def get_hls_proxy_port():
    return _proxy_port
