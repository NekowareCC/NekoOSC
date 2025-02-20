# NekoOSC

NekoOSC is a Python-based application that integrates with VRChat's OSC (Open Sound Control) protocol to display real-time media information, including song titles, artists, lyrics, and heart rate data, in a customizable and visually appealing interface. It supports integration with Spotify, Pulsoid (for heart rate monitoring), and various lyric providers like MusixMatch and NetEase.

## Features

- **Real-time Media Display**: Displays the currently playing song's title, artist, duration, and lyrics in VRChat using OSC.
- **Spotify Integration**: Fetches song information and playback status directly from Spotify.
- **Pulsoid Integration**: Displays real-time heart rate data from Pulsoid.
- **Lyrics Support**: Fetches lyrics from MusixMatch or NetEase, with optional Romaji conversion for Japanese lyrics.
- **Animations**: Supports custom animations for visual effects.
- **Configuration**: Easy-to-use configuration for customizing the application's behavior.

## Installation

### Prerequisites

Windows 10+ PC

### Steps

1. **Download the release**:
   You can get the latest release [HERE](https://github.com/NekowareCC/NekoOSC/releases)

2. **Run the Application**:
   Run the downloaded Application


## Configuration

NekoOSC has a "Config" tab to easily edit the configuration in-app.
NekoOSC also uses a `config.json` file located in the `%LOCALAPPDATA%\Nekoware\NekoOSC` directory. The configuration file includes settings for text formatting, Pulsoid, Spotify, and OSC.

### Example `config.json`

```json
{
    "text": {
        "Format": "$title - $artist\n$duration|$totalduration\n$lyrics",
        "Placeholder": "",
        "Idle": "",
        "Invisible": false,
        "Romaji": true,
        "Offset": 0
    },
    "pulsoid": {
        "Enabled": false,
        "Text": "❤️:$hr",
        "Token": ""
    },
    "spotify": {
        "Enabled": false,
        "Client ID": "",
        "Client Secret": "",
        "Redirect URI": ""
    },
    "OSC": {
        "Host": "127.0.0.1",
        "Port": 9000
    },
    "config": {
        "App Lock": "Spotify.exe"
    },
    "lyrics": {
        "NetEase": false
    }
}
```

### Configuration Options

- **Text Formatting**:
  - `Format`: The format string for displaying song information.
  - `Placeholder`: Text to display when no lyrics are available.
  - `Idle`: Text to display when no media is playing.
  - `Invisible`: Whether to make the VRChat chatbox invisible.
  - `Romaji`: Whether to convert Japanese lyrics to Romaji.
  - `Offset`: Time offset for lyrics synchronization.

- **Pulsoid**:
  - `Enabled`: Enable or disable Pulsoid integration.
  - `Text`: Format string for displaying heart rate data.
  - `Token`: Pulsoid API token.

- **Spotify**:
  - `Enabled`: Enable or disable Spotify integration.
  - `Client ID`: Spotify API client ID.
  - `Client Secret`: Spotify API client secret.
  - `Redirect URI`: Spotify API redirect URI.

- **OSC**:
  - `Host`: OSC host IP address.
  - `Port`: OSC port number.

- **App Lock**:
  - `App Lock`: The application to lock media control to (e.g., `Spotify.exe`).

- **Lyrics**:
  - `NetEase`: Whether to use NetEase as a secondary lyrics provider.

## Usage

1. **Start the Application**: Run the application.
2. **Configure Settings**: Open the "CONFIG" tab to configure the application settings.
3. **Start OSC**: Click the "START" button to begin sending media information to VRChat via OSC.
4. **Customize Animations**: Use the "ANIMATIONS" tab to check out animations.

## Troubleshooting

- **Logs**: Logs are stored in `%LOCALAPPDATA%\Nekoware\NekoOSC\nekoosc.log`.
- **Errors**: If the application crashes or behaves unexpectedly, check the logs for error messages.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the GPL-3.0 license. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the GUI framework.
- [Spotipy](https://spotipy.readthedocs.io/) for Spotify integration.
- [Pulsoid](https://pulsoid.net/) for heart rate monitoring.
- [MusixMatch](https://www.musixmatch.com/) and [NetEase](https://music.163.com/) for lyrics.

---

**NekoOSC** is developed with ❤️ by [Lycoris](https://github.com/LycorisWO)@[Nekoware](https://nekoware.cc). For support, questions, or feedback, please open an issue on GitHub.
