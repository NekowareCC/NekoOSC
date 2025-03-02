import requests
import json
import urllib
import asyncio
import os


class TokenError(Exception):
    def __init__(self, message="Token not found"):
        self.message = message
        super().__init__(self.message)


class Song:
    REQUIRED_FIELDS = ["artist", "title"]

    def __init__(self, info, uri=""):
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in info]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # self.album = info["album"]
        self.artist = info["artist"]
        self.title = info["title"]
        self.duration = info["duration"]
        self.uri = uri

        # self.track_spotify_id = info["uri"]

    def to_dict(self):
        if self.uri:
            return {
                # "album": self.album,
                "q_artist": self.artist,
                "q_track": self.title,
                # "track_spotify_id": self.track_spotify_id,
                # "duration": self.duration
            }
        else:
            return {
                # "album": self.album,
                "q_artist": self.artist,
                "q_track": self.title,
                "track_spotify_id": self.uri
                # "track_spotify_id": self.track_spotify_id,
                # "duration": self.duration
            }


class MusixMatch:
    def __init__(self):
        appdata_path = os.getenv('LOCALAPPDATA')
        self.nekooscpath = os.path.join(appdata_path, 'Nekoware', 'MusixMatch')
        self.setup()
        self.token = ""
        self.gettoken()
        self.headers = {
            "authority": "apic-desktop.musixmatch.com",
            "cookie": "x-mxm-token-guid=",
        }

    def setup(self):
        if not os.path.exists(self.nekooscpath):
            os.makedirs(self.nekooscpath)
            with open(f"{self.nekooscpath}\\token.json", "w") as f:
                f.write('{"token": ""}')
                f.close()
        else:
            try:
                with open(f"{self.nekooscpath}\\token.json", "r") as f:
                    try:
                        js = json.loads(f.read())
                    except:
                        os.remove(f"{self.nekooscpath}\\token.json")
                        MusixMatch().setup()
                    f.close()
                if not js["token"]:
                    os.remove(f"{self.nekooscpath}\\token.json")
                    MusixMatch().setup()
            except FileNotFoundError:
                with open(f"{self.nekooscpath}\\token.json", "w") as f:
                    f.write('{"token": ""}')
                    f.close()

    def gettoken(self):
        with open(f"{self.nekooscpath}\\token.json", "r") as f:
            js = json.loads(f.read())
            f.close()
        if js["token"] != "":
            self.token = js["token"]
        else:
            url = "https://apic-desktop.musixmatch.com/ws/1.1/token.get?app_id=web-desktop-app-v1.0"
            tokenrequest = requests.get(url)
            try:
                if tokenrequest.status_code == 200 and tokenrequest.json()["message"]["body"]["user_token"]:
                    token = tokenrequest.json()["message"]["body"]["user_token"]
                    self.token = token
                    js["token"] = token
                    with open(f"{self.nekooscpath}\\token.json", "w") as f:
                        f.write(json.dumps(js))
                        f.close()
                else:
                    raise TokenError("Could not get the token from the MusixMatch API.")
            except KeyError:
                raise TokenError("Could not get the token from the MusixMatch API.")

    async def findLyrics(self, info: Song):
        base_url = (
            "https://apic-desktop.musixmatch.com/ws/1.1/macro.subtitles.get?format=json"
            "&namespace=lyrics_richsynched&subtitle_format=mxm&app_id=web-desktop-app-v1.0&"
        )
        song = info.to_dict()
        song["usertoken"] = self.token
        query_string = "&".join(f"{key}={urllib.parse.quote_plus(str(value))}" for key, value in song.items())
        request_url = base_url + query_string

        response = requests.get(request_url, headers=self.headers)
        body = response.json()
        body = body["message"]["body"]["macro_calls"]

        # Check if track information exists and has a valid status code
        track_info = body.get("matcher.track.get", {}).get("message", {})
        if track_info.get("header", {}).get("status_code") != 200:
            return {
                "error": f"Requested error: {track_info.get('header', {}).get('mode', 'unknown mode')} | {track_info.get('header', {}).get('status_code')}"
            }

        # Check if track.lyrics.get has a body and handle if it's a list
        lyrics_body = body.get("track.lyrics.get", {}).get("message", {}).get("body", {})
        if isinstance(lyrics_body, dict) and lyrics_body.get("lyrics", {}).get("restricted"):
            return {
                "error": "Unfortunately we're not authorized to show these lyrics."
            }

        # Handle synced lyrics
        synced_lyrics = self.getSynced(body)
        if synced_lyrics:
            return synced_lyrics

        return {"error": "No synced lyrics found."}

    def getSynced(self, body):
        meta = body.get("matcher.track.get", {}).get("message", {}).get("body")
        if not meta:
            return None

        has_synced = meta.get("track", {}).get("has_subtitles")
        is_instrumental = meta.get("track", {}).get("instrumental")

        if is_instrumental:
            return [{"text": "♪ Instrumental ♪", "startTime": "0000"}]

        if has_synced:
            subtitle = (
                body.get("track.subtitles.get", {})
                .get("message", {})
                .get("body", {})
                .get("subtitle_list", [{}])[0]
                .get("subtitle")
            )
            if not subtitle:
                return None

            return [
                {"text": line.get("text", "♪"), "startTime": line["time"]["total"] * 1000}
                for line in json.loads(subtitle["subtitle_body"])
            ]

        return None
