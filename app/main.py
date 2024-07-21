import asyncio
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from multiprocessing import Process
import websockets
from websockets import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosedOK
from datetime import datetime
import json
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = urlparse(self.path)
        if pr_url.path == '/':
            self.send_html_file('index.html')
        elif pr_url.path == '/message.html':
            self.send_html_file('message.html')
        elif pr_url.path.startswith('/static/'):
            self.send_static_file(pr_url.path[1:])
        else:
            self.send_html_file('error.html', 404)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        parsed_data = parse_qs(post_data.decode('utf-8'))
        username = parsed_data.get('username')[0]
        message = parsed_data.get('message')[0]
        message_data = json.dumps({
            'username': username,
            'message': message
        })
        
        async def send_message():
            uri = "ws://localhost:5000"
            async with websockets.connect(uri) as websocket:
                await websocket.send(message_data)
        
        asyncio.run(send_message())
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Message sent!')

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as fd:
            self.wfile.write(fd.read())

    def send_static_file(self, filename, status=200):
        try:
            with open(filename, 'rb') as file:
                self.send_response(status)
                if filename.endswith('.png'):
                    self.send_header('Content-type', 'image/png')
                elif filename.endswith('.css'):
                    self.send_header('Content-type', 'text/css')
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_html_file('error.html', 404)

def run_http_server():
    server_address = ('', 3000)
    httpd = HTTPServer(server_address, HttpHandler)
    logging.info("HTTP server started on port 3000")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
        logging.info("HTTP server stopped")

class WebSocketServer:
    clients = set()

    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI")
        self.client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        self.db = self.client.message_db
        self.collection = self.db.messages

    async def register(self, ws: WebSocketServerProtocol):
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            await asyncio.wait([client.send(message) for client in self.clients])

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distribute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distribute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            message_data = json.loads(message)
            message_data['date'] = datetime.now().isoformat()
            self.collection.insert_one(message_data)
            await self.send_to_clients(f"{message_data['username']}: {message_data['message']}")

async def run_websocket_server():
    server = WebSocketServer()
    async with websockets.serve(server.ws_handler, '0.0.0.0', 5000):
        logging.info("WebSocket server started on port 5000")
        await asyncio.Future()  # run forever

def start_websocket_server():
    asyncio.run(run_websocket_server())

if __name__ == '__main__':
    http_process = Process(target=run_http_server)
    ws_process = Process(target=start_websocket_server)

    http_process.start()
    ws_process.start()

    http_process.join()
    ws_process.join()
