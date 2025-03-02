import asyncio
import time
import logging
import webbrowser

import requests
import websockets
import json
import urllib.parse
import os
import sys
import threading
from aiohttp import web
import aiohttp
import ctypes


class PulsoidConnector:
    def __init__(self, logging=False):
        self.access_token = None
        self.websocket = None
        self.heart_rate = None
        self.listeners = []
        self.pulsoidpath = os.path.join(os.getenv('LOCALAPPDATA'), 'Nekoware', 'Pulsoid')
        self.auth_file_path = os.path.join(self.pulsoidpath, "auth.json")
        self.logging = logging

    def _log(self, message, level=logging.INFO):
        if self.logging:
            logging.log(level, message)

    async def _load_access_token(self):
        try:
            with open(self.auth_file_path, "r") as f:
                auth_data = json.load(f)
                self.access_token = auth_data.get("access_token")
            self._log("Access token loaded from file.")
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            self._log("Auth file not found or corrupted. Starting authorization process.")
            return False

    async def _save_access_token(self):
        os.makedirs(self.pulsoidpath, exist_ok=True)
        with open(self.auth_file_path, "w") as f:
            json.dump({"access_token": self.access_token}, f)
        self._log("Access token saved to file.")

    def return_access_token(self):
        if os.path.exists(self.auth_file_path):
            try:
                with open(self.auth_file_path, "r") as f:
                    auth_data = json.load(f)
                    token = auth_data.get("access_token")
                    if token:
                        return token
                    else:
                        self._log("Access token is empty in config file")
                        return None
            except json.JSONDecodeError:
                self._log("Config file is corrupted.")
                return None
        else:
            self._log("Config file not found.")
            return None

    def get_latest_heart_rate(self, max_time=0):
        """Retrieves the latest heart rate from the Pulsoid HTTP API, considering a maximum time threshold.

        Args:
            self: (object) Reference to the class instance.
            max_time: (int, optional) The maximum age of the heart rate in seconds. Defaults to 0 (no limit).

        Returns:
            The latest heart rate (int) if successful and within the time limit, None otherwise.
        """
        url = "https://dev.pulsoid.net/api/v1/data/heart_rate/latest?response_mode=json"
        headers = {
            "Authorization": f"Bearer {self.return_access_token()}"
        }

        try:
            with requests.Session() as session:
                response = session.get(url, headers=headers)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if "data" in data and "heart_rate" in data["data"]:
                        measured_at = data.get("measured_at", 0)
                        if measured_at == 0 or int(measured_at) / 1000 >= time.time() - max_time:
                            return data["data"]["heart_rate"]
                        else:
                            self._log("Heart rate data is too old (outside max_time threshold).")
                            return 0
                    else:
                        self._log("Invalid response format. Heart rate not found.")
                        return 0
                except json.JSONDecodeError:
                    self._log("Error decoding JSON response.")
                    return 0
            else:
                self._log(f"HTTP request failed with status code: {response.status_code}")
                return 0
        except requests.exceptions.RequestException as e:
            self._log(f"A client error occurred: {e}")
            return 0
        except Exception as e:
            self._log(f"An unexpected error occurred: {e}")
            return 0

    async def connect(self):
        if not self.access_token:
            self._log("Access token not available. Cannot connect.")
            return False
        self.websocket_uri = f"wss://dev.pulsoid.net/api/v1/data/real_time?access_token={self.access_token}"
        try:
            self.websocket = await websockets.connect(self.websocket_uri)
            self._log("Connected to Pulsoid WebSocket")
        except websockets.exceptions.ConnectionClosedError as e:
            self._log(f"Connection Closed Error: {e}")
            return False
        except Exception as e:
            self._log(f"Error connecting to WebSocket: {e}")
            return False
        return True

    async def receive_data(self):
        if not self.websocket:
            self._log("Websocket not connected.")
            return
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    if "data" in data and "heart_rate" in data["data"]:
                        self.heart_rate = data["data"]["heart_rate"]
                        self._notify_listeners()
                except json.JSONDecodeError:
                    self._log(f"Received invalid JSON: {message}")
        except websockets.exceptions.ConnectionClosedError:
            self._log("Connection closed by server.")
            return

    def add_listener(self, listener):
        self.listeners.append(listener)

    def remove_listener(self, listener):
        if listener in self.listeners:
            self.listeners.remove(listener)

    def _notify_listeners(self):
        for listener in self.listeners:
            if self.heart_rate is not None:
                listener(self.heart_rate)

    def _extract_access_token(self, full_url):
        try:
            parsed_url = urllib.parse.urlparse(full_url)
            query_params = urllib.parse.parse_qs(parsed_url.fragment)
            return query_params.get("access_token", [None])[0]
        except Exception as e:
            self._log(f"Error parsing redirect URI: {e}")
            return None

    async def run(self):
        while True:
            if self.access_token:
                if await self.connect():
                    await self.receive_data()
            self._log("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

    async def _start_webserver(self, port=9630):
        async def handle_redirect(request):
            return web.Response(text=redirect_html, content_type='text/html')

        async def process_fragment(request):
            data = await request.post()
            fragment = data.get('fragment')
            if fragment:
                self.access_token = self._extract_access_token("#" + fragment)
                if self.access_token:
                    await self._save_access_token()
                    self._log("Access token received!")
                    return web.Response(text="Authorization successful! You can close this window.")
                else:
                    return web.Response(text="Error: Could not extract access token.", status=400)
            else:
                return web.Response(text="Error: Fragment not received.", status=400)

        app = web.Application()
        app['pulsoid_client'] = self
        app.add_routes([web.get('/', handle_redirect),
                        web.post('/process_fragment', process_fragment)])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', port)
        await site.start()
        self._log(f"Temporary webserver started on http://127.0.0.1:{port}")
        return runner

    async def start_pulsoid(self):
        if await self._load_access_token():
            self._log("Starting Pulsoid connection with saved token...", level=logging.DEBUG)
        else:
            def show_authorization_message():
                MB_YESNO = 0x04
                IDYES = 6
                result = ctypes.windll.user32.MessageBoxW(0,
                                                          "Please authorize Pulsoid in your browser. Click Yes to proceed.",
                                                          "Pulsoid Authorization", MB_YESNO)
                return result == IDYES

            if show_authorization_message():
                self._log("User clicked Yes. Starting authorization process.", logging.INFO)
                runner = await self._start_webserver()
                webbrowser.open(
                    "https://pulsoid.net/oauth2/authorize?response_type=token&client_id=0ffcef8f-ef50-4393-ae7b-a91bbfc1c9df&redirect_uri=http://127.0.0.1:9630&scope=data:heart_rate:read&state=384c70b7-f672-45a7-beda-c0bd35fc9214")
                while self.access_token is None:
                    await asyncio.sleep(1)
                await runner.cleanup()
                self._log("Webserver stopped.", logging.DEBUG)
                self._log("Starting Pulsoid connection...", logging.DEBUG)
            else:
                self._log("User declined authorization.", logging.INFO)
                return

    async def start_websocket(self):
        await self.run()


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath("..")
    return os.path.join(base_path, relative_path)


redirect_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Redirect Handling</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #121212;
            color: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            text-align: center;
        }
        .container {
            background: #1e1e1e;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
            max-width: 400px;
        }
        .message {
            font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="container">
        <p class="message" id="status">Processing authorization...</p>
    </div>
    <script>
        function sendFragment() {
            const fragment = window.location.hash.substring(1);
            const statusElement = document.getElementById('status');
            if (fragment) {
                fetch('/process_fragment', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: 'fragment=' + encodeURIComponent(fragment)
                })
                .then(response => response.text())
                .then(message => {
                    statusElement.textContent = message;
                })
                .catch(error => {
                    console.error('Error sending fragment:', error);
                    statusElement.textContent = 'Error processing authorization.';
                });
            } else {
                statusElement.textContent = "No fragment found";
            }
        }
        window.onload = sendFragment;
    </script>
</body>
</html>
"""


async def run_pulsoid_async(pulsoid_connector):
    await pulsoid_connector.start_pulsoid()


def run_pulsoid_in_thread(pulsoid_connector):
    asyncio.run(run_pulsoid_async(pulsoid_connector))


async def main():
    pulsoid_connector = PulsoidConnector()
    await pulsoid_connector.start_pulsoid()
    while True:
        print(pulsoid_connector.get_latest_heart_rate(max_time=5))
        await asyncio.sleep(1)
    # def handle_heart_rate(hr):
    #     self._log(f"Main Thread: Heart Rate: {hr}")
    #
    # pulsoid_connector.add_listener(handle_heart_rate)
    #
    # pulsoid_thread = threading.Thread(target=run_pulsoid_in_thread, args=(pulsoid_connector,), daemon=True)
    # pulsoid_thread.start()
    #
    # # Keep the main thread running (example)
    # try:
    #     while True:
    #         await asyncio.sleep(1)
    # except KeyboardInterrupt:
    #     self._log("Exiting...")


if __name__ == "__main__":
    asyncio.run(main())
