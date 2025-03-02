import asyncio
import re
from urllib.parse import quote

import aiohttp
import pykakasi

kks = pykakasi.kakasi()


class NetEase:
    def __init__(self):
        self.request_header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:93.0) Gecko/20100101 Firefox/93.0",
        }
        self.credit_info_regex = re.compile(
            r"(作?词|作?曲|编曲|监制|翻唱|和声|和音|吉他|贝斯|提琴|合声|缩混|后期|录音|混音)", re.IGNORECASE)

    async def find_lyrics(self, song, lyric_format=False):
        search_url = "https://music.xianqiao.wang/neteaseapiv2/search?limit=10&type=1&keywords="
        lyric_url = "https://music.xianqiao.wang/neteaseapiv2/lyric?id="

        final_url = search_url + quote(f"{song.title} {song.artist}")
        async with aiohttp.ClientSession() as session:
            async with session.get(final_url, headers=self.request_header) as response:
                if response.status != 200:
                    return {"error": f"HTTP error {response.status}"}
                search_results = await response.json()
        items = search_results.get("result", {}).get("songs", [])
        if not items:
            return {"error": "Cannot find track"}

        item_id = items[0]["id"]
        async with aiohttp.ClientSession() as session:
            async with session.get(lyric_url + str(item_id), headers=self.request_header) as response:
                if response.status != 200:
                    return {"error": f"HTTP error {response.status}"}
                lyrics_data = await response.json()
        return self._get_filtered_lyrics(lyrics_data, lyric_format)

    def _get_filtered_lyrics(self, list_data, lyric_format):
        if lyric_format:
            romaji_lyrics = list_data.get("romalrc", {}).get("lyric", "").strip()
            if romaji_lyrics:
                return self._parse_lyrics(romaji_lyrics)

        raw_lyrics = list_data.get("lrc", {}).get("lyric", "").strip()
        if not raw_lyrics:
            return {"error": "No lyrics found"}

        return self._parse_lyrics(raw_lyrics)

    def _parse_lyrics(self, raw_lyrics):
        lyrics_list = []

        for line in raw_lyrics.split("\n"):
            if self.credit_info_regex.search(line):
                continue

            match = re.match(r"\[(\d+):(\d+)\.?(\d*)]\s*(.*)", line)
            if not match:
                continue

            minutes, seconds, milliseconds, text = match.groups()
            milliseconds = int(milliseconds.ljust(3, "0")) if milliseconds else 0
            start_time = (int(minutes) * 60 + int(seconds)) * 1000 + milliseconds

            lyrics_list.append({"text": text, "startTime": start_time})

        return lyrics_list if lyrics_list else {"error": "No lyrics found"}


class Song:
    def __init__(self, artist, title):
        self.artist = artist
        self.title = title


async def main():
    provider = NetEase()
    song = Song("The Weeknd", "Timeless (feat. Playboy Carti)")

    lyrics = await provider.find_lyrics(song, lyric_format=False)

    if isinstance(lyrics, list):
        for lyric in lyrics:
            print((lyric["text"]))
    else:
        print(lyrics["error"])


if __name__ == "__main__":
    asyncio.run(main())
