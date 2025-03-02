import ctypes
import json
import re
import sys
import time
import traceback
import webbrowser
from datetime import datetime

import pykakasi
import spotipy
from PyQt6.QtCore import QPoint, QSize
from PyQt6.QtGui import (QPixmap, QImage, QPalette, QIcon)
from PyQt6.QtWidgets import (QWidget, QApplication, QPushButton, QMessageBox)
from colorama import init
from pythonosc.udp_client import SimpleUDPClient
from spotipy.oauth2 import SpotifyOAuth
from winrt.windows.foundation import TimeSpan
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager

from utils.lyrics.musixmatch import Song, MusixMatch
from utils.nekowidgets import *
from utils.lyrics.netease import NetEase
from utils.pulsoid import PulsoidConnector

import requests

if not os.path.exists(os.path.join(os.getenv('LOCALAPPDATA'), 'Nekoware', 'NekoOSC')):
    os.makedirs(os.path.join(os.getenv('LOCALAPPDATA'), 'Nekoware', 'NekoOSC'))
init(autoreset=True)

logging.basicConfig(filename=os.path.join(os.getenv('LOCALAPPDATA'), 'Nekoware', 'NekoOSC', 'nekoosc.log'),
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def print_to_console(text, color=None, app=None):
    try:
        if app and hasattr(app.neko_osc_widget, 'console_output') and app.neko_osc_widget.console_output is not None:
            app.neko_osc_widget.console_output.new_text_signal.emit(text, color)
        else:
            print(text)
    except AttributeError:
        return


class Logger:
    @staticmethod
    def log(level, message, raw, color=None):
        logging.log(level, raw)
        print_to_console(message, color)

    @staticmethod
    def info(message):
        Logger.log(logging.INFO, "\n[INFO] " + message, "lightblue", message)

    @staticmethod
    def warning(message):
        Logger.log(logging.WARNING, "\n[WARNING] " + message, "yellow", message)

    @staticmethod
    def error(message):
        Logger.log(logging.ERROR, "\n[ERROR] " + message, "red", message)

    @staticmethod
    def debug(message):
        Logger.log(logging.DEBUG, "\n[DEBUG] " + message, "lightgreen", message)


class VRCClient:
    def __init__(self, ip='127.0.0.1', port=9000):
        """Initialize the client with the provided IP and port."""
        self.ip = ip
        self.port = port
        self.client = SimpleUDPClient(ip, port)

    def send_message(self, message):
        """Send a chat message to VRChat and return True if successful."""
        try:
            self.client.send_message('/chatbox/input', [message, True])
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False


class TimeUtils:
    @staticmethod
    def format_timespan(timespan: TimeSpan):
        """Convert a TimeSpan object to milliseconds."""
        return int(timespan.duration * 0.0001)

    @staticmethod
    def unformat_timespan(timespan: int):
        """Convert milliseconds back to the TimeSpan format."""
        return int(timespan / 0.001)

    @staticmethod
    def time_to_ms(time_str):
        """Convert a time string formatted as minutes:seconds to milliseconds."""
        minutes, seconds = map(int, time_str.split(":"))
        total_seconds = minutes * 60 + seconds
        milliseconds = total_seconds * 1000
        return milliseconds

    @staticmethod
    def seconds_to_m_s(seconds):
        """Convert seconds to a string formatted as minutes:seconds."""
        minutes = int(seconds // 60)
        seconds_remaining = int(seconds % 60)
        return f"{minutes}:{seconds_remaining:02}"


class NekoOSC(QWidget):
    def __init__(self):
        super().__init__()

        self.version = "1.0.0"
        self._get_updates()

        self.format = ""
        self.placeholder = ""
        self.idle = ""
        self.invisible = False
        self.romaji = False
        self.offset = 0

        self.pulsoid_connector = PulsoidConnector()
        self.pulsoid_enabled = False
        self.pulsoid_text = ""

        self.spotify_enabled = False
        self.spotify_client_id = ""
        self.spotify_client_secret = ""
        self.spotify_redirect_uri = ""

        self.osc_host = "127.0.0.1"
        self.osc_port = 9000

        self.osc = VRCClient(self.osc_host, self.osc_port)

        self.app_lock = ""

        self.console_output = None

        self.debug = False
        self._setup_argv()

        self._setup_animations()

        self.netease = False

        self.setWindowTitle("NekoOSC")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.oldPos = None
        self.setMinimumSize(QSize(800, 600))

        if getattr(sys, 'frozen', False):
            application_path = sys._MEIPASS
        else:
            application_path = os.path.dirname(__file__)

        icon_path = os.path.join(application_path, 'logo.ico')
        self.setWindowIcon(QIcon(icon_path))

        self.worker = Worker(self)
        self.worker.start()
        self.worker.signals.data_updated.connect(self.update_data_display)
        self.worker.signals.error.connect(self.handle_error)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data_display_timer)

        self.running = False
        self.mm = MusixMatch()
        self.ne = NetEase()
        self.topmost_enabled = False

        self.nekooscpath = os.path.join(os.getenv('LOCALAPPDATA'), 'Nekoware', 'NekoOSC')

        self.songname = ""
        self.lyrics = ""
        self.lyricnumber = 0
        self.totallyrics = 0
        self.firstrun = True

        self.data = {
            "title": "",
            "artist": "",
            "duration": "",
            "totalduration": "",
            "lyrics": "",
        }

        self.durationlock = False
        self.started = False
        self.is_playing = False
        self.hrformat = self.format + "\n" + self.pulsoid_text

        self.kakasi = pykakasi.kakasi()

        self.tasks = []
        self.ended = True
        self.starttime = 0

        asyncio.run(self._setup_manager())

        self.pt = ""

        self.status_strings = {"lastrun": 0}

        self._setup_config()

        self.initUI()
        self.apply_style()

        self._setup_config()
        self.setup_spotify()

    def _get_updates(self):
        """Check for updates and prompt the user to download the new version."""
        new_version = requests.get("https://nekoware.cc/osc/version").text.strip()
        if new_version != self.version:
            response = QMessageBox.question(self, "Update Available",
                                            f"An update is available for NekoOSC: {new_version}\n Click OK to be taken to the download page or NO to cancel the update.",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if response == QMessageBox.StandardButton.Yes:
                webbrowser.open("https://nekoware.cc/osc/download")
            else:
                return

    def _setup_argv(self):
        """Set up the command line arguments."""
        for arg in sys.argv:
            if arg == "--debug":
                self.debug = True

    def _setup_animations(self):
        path = os.path.join(os.getenv("LOCALAPPDATA", ""), "Nekoware", "NekoOSC", "animations")
        if not os.path.isdir(path):
            os.mkdir(path)
            dl = ["progressbar", "dancing", "notes", "heartrate"]
            for file in dl:
                req = requests.get(f"https://nekoware.cc/osc/files/animations/{file}.xml")
                req.encoding = "utf-8"
                if req.status_code == 200:
                    with open(f"{path}\\{file}.xml", "w", encoding="utf-8") as f:
                        f.write(req.text)
                else:
                    Logger.error(f"Error downloading default animations: {req.status_code}")
        self.animator = NekoAnimator(path)
        self.animations = {}
        for animation in self.animator.animation_list:
            self.animations[animation.name] = animation

    def setup_spotify(self):
        """Set up the Spotify API."""
        try:
            if self.spotify_enabled:
                self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                    client_id=self.spotify_client_id,
                    client_secret=self.spotify_client_secret,
                    redirect_uri=self.spotify_redirect_uri,
                    scope="user-read-playback-state"
                ))
        except spotipy.oauth2.SpotifyOauthError:
            Logger.error("Spotify authentication failed. Please check your credentials in the config.")
            self.spotify_enabled = False

    async def _setup_manager(self):
        """Set up the media manager."""
        self.manager = await MediaManager.request_async()

    async def _refesh_animations(self):
        """Refresh the animations."""
        self.animator.load_animations()

    async def setup_pulsoid(self):
        """Set up the Pulsoid connector."""
        if self.pulsoid_enabled:
            try:
                with open(f"{self.nekooscpath}\\config.json", "r", encoding="utf-8") as f:
                    js = json.load(f)
                    js["pulsoid"]["Token"] = self.pulsoid_connector.return_access_token()
                with open(f"{self.nekooscpath}\\config.json", "w", encoding="utf-8") as f:
                    json.dump(js, f, indent=4, separators=(',', ': '))

                await self.pulsoid_connector.start_pulsoid()
            except Exception as e:
                Logger.error(f"Pulsoid setup error: {str(e)}")

    def initUI(self):
        """Initialize the user interface."""
        self.setWindowTitle("NekoOSC ⋆⭒˚｡⋆")
        self.setMinimumSize(900, 650)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setObjectName("titleBar")

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(15, 0, 15, 0)

        title_label = QLabel("NekoOSC")
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font: bold 18px;
                font-family: ryo-gothic-plusn, sans-serif;
                padding: 0px;
                margin: 0px;
                background-color: #14151c;
                border-radius: 4px;
            }
        """)

        title_bar.setStyleSheet("""

                background-color: #14151c;  /* Darker shade than the base color */
                height: 40px;
                border-radius: 8px 8px 0 0;
            }
        """)

        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        control_layout.addStretch()

        min_btn = QPushButton()
        min_layout = QHBoxLayout()
        min_label = QLabel("⎯")
        min_label.setStyleSheet("""
            color: white;
            font-size: 20px;
            font-weight: bold;
            background-color: #383838;
        """)
        min_layout.addWidget(min_label)
        min_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_btn.setLayout(min_layout)
        min_btn.setFixedSize(25, 25)
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton()
        close_layout = QHBoxLayout()
        close_label = QLabel("X")
        close_label.setStyleSheet("""
            color: white;
            font-size: 8px;
            font-weight: bold;
            background-color: #383838;
        """)
        close_layout.addWidget(close_label)
        close_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_btn.setLayout(close_layout)
        close_btn.setFixedSize(25, 25)
        close_btn.clicked.connect(self.close)

        self.p_btn = QPushButton()
        self.p_layout = QHBoxLayout()
        self.p_label = QLabel("P")
        self.p_label.setStyleSheet(""" 
            color: white;
            font-size: bold 8px;
            font-family: ryo-gothic-plusn, sans-serif;
            background-color: #383838;
        """)
        self.p_layout.addWidget(self.p_label)
        self.p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.p_btn.setLayout(self.p_layout)
        self.p_btn.setFixedSize(25, 25)
        self.p_btn.clicked.connect(self.toggle_topmost)

        self.p_btn.setStyleSheet("""
            QPushButton {
                background-color: #383838;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
            }
        """)

        min_btn.setStyleSheet("""
            QPushButton {
                background-color: #383838;
                border: none;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 5px;
            }
        """)

        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #383838;
                border: none;
            }
            QPushButton:hover {
                background: red;
                border-radius: 5px;
            }
        """)

        control_layout.addWidget(self.p_btn)
        control_layout.addWidget(min_btn)
        control_layout.addWidget(close_btn)

        title_layout.addWidget(title_label)
        title_layout.addLayout(control_layout)

        title_bar.setLayout(title_layout)
        main_layout.addWidget(title_bar)

        content_widget = QWidget()
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        left_panel = QWidget()
        left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        status_card = QWidget()
        status_card.setStyleSheet("""
            background: #1a1a1a;
            border-radius: 8px;
            padding: 0px;
        """)

        status_title = QLabel("SYSTEM STATUS")
        status_title.setStyleSheet("color: #8f00ff; font: bold 12px;")

        self.hostlabel = QLabel("Host: " + self.osc_host)
        self.portlabel = QLabel("Port: " + str(self.osc_port))
        self.connection_status = QLabel("Disconnected")
        self.lastrunlabel = QLabel("Last Update Time: 0")
        self.infolabel = QLabel("""
        Current Formatting Placeholders:

        $title - Song Title
        $artist - Artist Name
        $duration - Current Song Time
        $totalduration - Total Song Time
        $lyrics - Current Lyrics
        $hr - Heartrate

        *animation_name - Plays animation
        """)

        self.connection_status.setStyleSheet("color: #ffffff; font: 12px; font-family: ryo-gothic-plusn, sans-serif;")
        self.hostlabel.setStyleSheet("color: #ffffff; font: 12px;  font-family: ryo-gothic-plusn, sans-serif;")
        self.portlabel.setStyleSheet("color: #ffffff; font: 12px; font-family: ryo-gothic-plusn, sans-serif;")
        self.lastrunlabel.setStyleSheet("color: #ffffff; font: 12px; font-family: ryo-gothic-plusn, sans-serif;")
        self.infolabel.setStyleSheet("color: #ffffff; font: 12px; font-family: ryo-gothic-plusn, sans-serif;")

        v_layout1 = QVBoxLayout()
        v_layout1.addWidget(status_title)
        v_layout1.setSpacing(1)

        v_layout2 = QVBoxLayout()
        v_layout2.addWidget(self.hostlabel)
        v_layout2.addWidget(self.portlabel)
        v_layout2.setSpacing(2)

        v_layout3 = QVBoxLayout()
        v_layout3.addWidget(self.connection_status)
        v_layout3.addWidget(self.lastrunlabel)
        v_layout3.setSpacing(5)
        v_layout3.addWidget(self.infolabel)

        main_v_layout = QVBoxLayout()
        main_v_layout.addLayout(v_layout1)
        main_v_layout.addLayout(v_layout2)
        main_v_layout.addLayout(v_layout3)
        main_v_layout.addStretch()

        status_card.setLayout(main_v_layout)

        self.start_btn = QPushButton("START")
        self.start_btn.setFixedHeight(45)
        self.start_btn.clicked.connect(self.toggle_start)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #8f00ff;
                color: #ffffff;
                border-radius: 6px;
                font-size: 14px;
                padding: 12px;
            }
            QPushButton:hover {
                background-color: #B4A1FF;
            }
        """)

        left_layout.addWidget(status_card)
        left_layout.addWidget(self.start_btn)
        left_panel.setLayout(left_layout)

        right_panel = QTabWidget()
        right_panel.setStyleSheet("""
            QTabWidget::pane {
                border: 0;
                background: #1a1a1a;
            }
            QTabBar::tab {
                background: #2a2a2a;
                color: #ffffff;
                padding: 10px 25px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #8f00ff;
                color: #ffffff;
            }
        """)

        vis_tab = QWidget()
        vis_layout = QVBoxLayout()
        vis_layout.setContentsMargins(10, 10, 10, 10)
        vis_tab.setStyleSheet("background-color: #242424; border: 2px solid #8f00ff;")

        self.chatbox_widget = QWidget()
        self.chatbox_widget.setStyleSheet("""
            QWidget {
                background-color: #485464;
                border: none;
                border-radius: 10px;
                padding: 10px;
            }
        """)

        self.chatbox_widget.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.data_display = QLabel()
        self.data_display.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #ffffff;
                font-size: 15px;
                font-family: ryo-gothic-plusn, sans-serif;
                font-style: normal;
                font-weight: 200;
            }
        """)
        self.data_display.setWordWrap(True)
        self.data_display.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # self.data_display.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        chatbox_layout = QVBoxLayout()
        chatbox_layout.setContentsMargins(0, 0, 0, 0)
        chatbox_layout.addWidget(self.data_display)
        self.chatbox_widget.setLayout(chatbox_layout)

        vis_layout.addWidget(self.chatbox_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        vis_tab.setLayout(vis_layout)

        config_tabs = ConfigTabs(self.nekooscpath, self)

        right_panel.addTab(vis_tab, "VISUALIZER")
        right_panel.addTab(config_tabs, "CONFIG")
        animations_tab = AnimationsTab(self.animator)
        right_panel.addTab(animations_tab, "ANIMATIONS")

        if self.debug:
            debug_tab = QWidget()
            debug_layout = QVBoxLayout()

            self.console_output = ConsoleOutput()
            self.console_output.setStyleSheet("""
                QPlainTextEdit {
                    background: #000000;
                    color: #8f00ff;
                    border: 2px solid #8f00ff;
                    border-radius: 5px;
                    font-family: 'Consolas';
                    font-size: 12px;
                    padding: 10px;
                }
            """)

            debug_layout.addWidget(self.console_output)
            debug_tab.setLayout(debug_layout)
            right_panel.addTab(debug_tab, "LOGS")

        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)
        content_widget.setLayout(content_layout)

        main_layout.addWidget(content_widget)
        self.setLayout(main_layout)

    def apply_style(self):
        """Apply the custom stylesheet."""
        neko_colors = {
            "base": "#1A1B26",
            "text": "#A9B1D6",
            "highlight": "#B4A1FF",
            "accent": "#FF9E9E",
            "secondary": "#73C2A6",
            "surface": "#2A2B3D",
            "border": "#414868"
        }

        self.setStyleSheet(f"""
            /* Base styling */
            QWidget {{
                background-color: {neko_colors["base"]};
                color: {neko_colors["text"]};
                font-family: ryo-gothic-plusn, sans-serif;
                font-size: 13px;
            }}

            /* Title bar */

                background: qlineargradient(x1:0, y1:0, x1:1, y1:0,
                    stop:0 {neko_colors["highlight"]}, 
                    stop:1 {neko_colors["accent"]});
                height: 40px;
                border-radius: 8px 8px 0 0;
            }}

            /* Buttons */
            QPushButton {{
                background-color: {neko_colors["highlight"]};
                color: {neko_colors["base"]};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {neko_colors["accent"]};
            }}
            QPushButton:pressed {{
                background-color: {neko_colors["secondary"]};
            }}

            /* Tabs */
            QTabWidget::pane {{
                border: 1px solid {neko_colors["border"]};
                border-radius: 8px;
                background: {neko_colors["surface"]};
            }}
            QTabBar::tab {{
                background: {neko_colors["base"]};
                color: {neko_colors["text"]};
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid {neko_colors["border"]};
            }}
            QTabBar::tab:selected {{
                background: {neko_colors["surface"]};
                border-bottom: 2px solid {neko_colors["highlight"]};
            }}

            /* Text displays */
            QTextEdit, QPlainTextEdit {{
                background-color: {neko_colors["surface"]};
                border: 1px solid {neko_colors["border"]};
                border-radius: 6px;
                padding: 12px;
                color: {neko_colors["text"]};
                selection-background-color: {neko_colors["highlight"]};
            }}

            /* Input fields */
            QLineEdit {{
                background-color: {neko_colors["surface"]};
                border: 1px solid {neko_colors["border"]};
                border-radius: 6px;
                padding: 8px;
                color: {neko_colors["text"]};
            }}
            QLineEdit:focus {{
                border: 1px solid {neko_colors["highlight"]};
            }}

            /* Group boxes */
            QGroupBox {{
                border: 1px solid {neko_colors["border"]};
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 24px;
                color: {neko_colors["highlight"]};
                font-weight: bold;
            }}

            /* Checkboxes */
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {neko_colors["border"]};
                border-radius: 4px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {neko_colors["highlight"]};
                image: url(:/qss_icons/checkbox_checked.svg);
            }}

            /* Scrollbars */
            QScrollBar:vertical {{
                background: {neko_colors["surface"]};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {neko_colors["highlight"]};
                min-height: 20px;
                border-radius: 6px;
            }}
        """)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(neko_colors["base"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(neko_colors["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(neko_colors["surface"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(neko_colors["base"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(neko_colors["text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(neko_colors["highlight"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(neko_colors["base"]))
        self.setPalette(palette)

    def create_colored_icon(self, pixmap, color):
        """Creates a colored icon from a pixmap."""
        image = pixmap.toImage()
        image.convertToFormat(QImage.Format.Format_ARGB32)
        for x in range(image.width()):
            for y in range(image.height()):
                if image.pixelColor(x, y).alpha() > 0:
                    image.setPixelColor(x, y, color)
        return QIcon(QPixmap.fromImage(image))

    def toggle_topmost(self):
        """Toggle the window's topmost status."""
        self.topmost_enabled = not self.topmost_enabled
        if self.topmost_enabled:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
            self.p_btn.setStyleSheet("""
                QPushButton {
                    background-color: blue;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background: rgba(0, 0, 255, 0.5);
                }
            """)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
            self.p_btn.setStyleSheet("""
                QPushButton {
                    background-color: #383838;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.2);
                }
            """)
        self.show()

    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.oldPos = event.globalPosition().toPoint()
            self.dragging = True

    def mouseMoveEvent(self, event):
        """Handle mouse move events."""
        if self.dragging:
            delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        self.dragging = False

    def _update_vrcclient(self):
        """Update the VRC client with the new host and port."""
        try:
            self.osc = VRCClient(self.osc_host, int(self.osc_port))
            self.hostlabel.setText("Host: " + self.osc_host)
            self.portlabel.setText("Port: " + str(self.osc_port))
        except AttributeError:
            pass

    def toggle_start(self):
        """Toggle the start button."""
        self.running = not self.running
        if self.running:
            self.start_btn.setText("STOP")
            self.worker.start_processing()
            if self.pulsoid_enabled:
                QTimer.singleShot(0, self._deferred_pulsoid_setup)
        else:
            self.start_btn.setText("START")
            self.worker.stop_processing()
            self.data_display.setText("")
            self.osc.send_message("")

    def _deferred_pulsoid_setup(self):
        """Defer pulsoid setup to avoid blocking the main thread."""
        asyncio.run(self.setup_pulsoid())

    def update_data_display_timer(self):
        """Update the data display."""
        self.update_data_display()

    def update_data_display(self):
        """Update the data display with the current song information."""
        if self.idle and not self.is_playing:
            return
        formatted_message = Formatter.format(self)
        wrapped = self.wrap_text(formatted_message, 38)
        if self.invisible:
            wrapped = wrapped[:-1]
        self.data_display.setText(wrapped)

        self.data_display.adjustSize()
        self.chatbox_widget.adjustSize()

    def wrap_text(self, text, max_chars_per_line):
        """Wrap text to fit within the specified number of characters per line."""
        lines = text.splitlines()
        wrapped_lines = []

        for line in lines:
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line + word) + 1 <= max_chars_per_line:
                    current_line += word + " "
                else:
                    wrapped_lines.append(current_line.strip())
                    current_line = word + " "
            wrapped_lines.append(current_line.strip())

        return "\n".join(wrapped_lines)

    def handle_error(self, error_message):
        """Handle errors that occur in the worker thread."""
        logger.error(f"Worker thread error: {error_message}")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_message}")

    def open_config_folder(self):
        """Opens the folder containing the config file."""
        os.startfile(os.path.dirname(os.path.join(self.nekooscpath, "config.json")))

    def _setup_config(self):
        """Set up the configuration file if it doesn't exist or is corrupted."""
        config_path = os.path.join(self.nekooscpath, "config.json")

        with open(os.path.join(os.getenv('LOCALAPPDATA'), 'Nekoware', 'NekoOSC', 'nekoosc.log'), "w") as f:
            f.write("")
            f.close()

        if not os.path.exists(config_path):
            self._create_default_config(config_path)
            self.load_config(config_path)
        else:
            self.load_config(config_path)

    def _create_default_config(self, config_path):
        """Create a default config file."""
        config_data = {
            "text": {
                "Format": "$title - $artist\n$duration*progressbar$totalduration\n$lyrics",
                "Placeholder": "",
                "Idle": "",
                "Invisible": False,
                "Romaji": False,
                "Offset": 0
            },
            "pulsoid": {
                "Enabled": False,
                "Text": "*heartrate:$hr",
                "Token": ""
            },
            "spotify": {
                "Enabled": False,
                "Client ID": "",
                "Client Secret": "",
                "Redirect URI": ""
            },
            "OSC": {
                "Host": "127.0.0.1",
                "Port": 9000
            },
            "config": {
                "App Lock": ""
            },
            "lyrics": {
                "NetEase": False
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)

    def load_config(self, config_path):
        """Load configuration from the config file."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

                self.format = config["text"]["Format"]
                self.placeholder = config["text"]["Placeholder"]
                self.idle = config["text"]["Idle"]
                self.invisible = config["text"]["Invisible"]
                self.romaji = config["text"]["Romaji"]
                self.offset = config["text"]["Offset"]

                self.pulsoid_enabled = config["pulsoid"]["Enabled"]
                self.pulsoid_text = config["pulsoid"]["Text"]
                self.pulsoid_token = config["pulsoid"]["Token"]

                self.spotify_enabled = config["spotify"]["Enabled"]
                self.spotify_client_id = config["spotify"]["Client ID"]
                self.spotify_client_secret = config["spotify"]["Client Secret"]
                self.spotify_redirect_uri = config["spotify"]["Redirect URI"]

                self.osc_host = config["OSC"]["Host"]
                self.osc_port = int(config["OSC"]["Port"])

                self.app_lock = config["config"]["App Lock"]

                self.netease = config["lyrics"]["NetEase"]
            f.close()
            self._update_vrcclient()
        except KeyError as e:
            Logger.error(f"Error loading config: {e}")

            backup_path = config_path + ".bak"
            if os.path.exists(config_path):
                try:
                    if hasattr(os, "replace"):
                        os.replace(config_path, backup_path)
                    else:
                        os.rename(config_path, backup_path)
                    Logger.info(f"Old config backed up to: {backup_path}")
                except OSError as backup_error:
                    Logger.error(f"Error backing up config: {backup_error}")
                    backup_path = None

            message = "An error occurred while loading the configuration file.\n"
            if backup_path:
                message += f"The old configuration has been backed up to: {backup_path}\n"
            message += "A new default configuration will be created."
            MB_OK = 0x00
            MB_ICONWARNING = 0x30
            result = ctypes.windll.user32.MessageBoxW(
                0,
                message,
                "Configuration Error",
                MB_OK | MB_ICONWARNING
            )

            if result == 1:
                try:
                    os.startfile(os.path.dirname(config_path))
                except OSError as open_error:
                    Logger.error(f"Error opening config folder: {open_error}")
            self._create_default_config(config_path)

    async def _get_media_info(self):
        """Retrieve the current media info from the system."""
        try:
            current_session = self.manager.get_current_session()
            if current_session and self.app_lock and current_session.source_app_user_model_id == self.app_lock:
                info = await current_session.try_get_media_properties_async()
                playback = current_session.get_playback_info()
                timeline = current_session.get_timeline_properties()

                timeline_dict = {attr: getattr(timeline, attr) for attr in dir(timeline) if not attr.startswith('_')}
                playback_dict = {attr: getattr(playback, attr) for attr in dir(playback) if not attr.startswith('_')}
                info_dict = {attr: getattr(info, attr) for attr in dir(info) if not attr.startswith('_')}

                maxdur = TimeUtils.seconds_to_m_s(TimeUtils.format_timespan(timeline_dict["end_time"]) // 1000)
                info_dict["duration"] = maxdur
                return info_dict, playback_dict, timeline_dict
            elif current_session:
                info = await current_session.try_get_media_properties_async()
                playback = current_session.get_playback_info()
                timeline = current_session.get_timeline_properties()

                timeline_dict = {attr: getattr(timeline, attr) for attr in dir(timeline) if not attr.startswith('_')}
                playback_dict = {attr: getattr(playback, attr) for attr in dir(playback) if not attr.startswith('_')}
                info_dict = {attr: getattr(info, attr) for attr in dir(info) if not attr.startswith('_')}

                maxdur = TimeUtils.seconds_to_m_s(TimeUtils.format_timespan(timeline_dict["end_time"]) // 1000)
                info_dict["duration"] = maxdur
                return info_dict, playback_dict, timeline_dict
            return None, None, None
        except Exception as e:
            Logger.error(f"Media info error: {str(e)}")
            return None, None, None

    async def _update_song_info(self, song_info, playback_info, timeline_info):
        """Update song and playback information, including lyrics and sync."""
        try:
            position = TimeUtils.format_timespan(timeline_info["position"])
            self.is_playing = playback_info["playback_status"] == 4
            song = Song(song_info)
            if self.songname != song.title:
                self.firstrun = True
                self.duration = 0
                self.totalduration = TimeUtils.time_to_ms(song.duration)
                self.songname = song.title
                self.lyrics = await self.mm.findLyrics(song)
                try:
                    if self.lyrics["error"] or len(self.lyrics) <= 1:
                        if self.netease:
                            Logger.error(f"Lyrics error: {self.lyrics['error']}, trying NetEase.")
                            self.lyrics = await self.ne.find_lyrics(song)
                except TypeError:
                    pass
                Logger.info(f"Fetched lyrics: {self.lyrics}")
                self.lyricnumber = 0
                self.totallyrics = len(self.lyrics) if self.lyrics else 0

            if not self.durationlock:
                self.duration = position // 1000
                self.durationlock = True

            if not self.is_playing:
                self._reset_media_state()
                self._process_stopped_state()

            if self.is_playing:
                self._process_playing_state(position, song)
        except Exception as e:
            Logger.error(f"Update song info error: {str(e)}")

    async def _update_song_info_spotify(self, song_info):
        """Update song and playback information, including lyrics and sync."""
        try:
            current_track = self.sp.current_playback()
            position = current_track['progress_ms'] * 1000
            self.is_playing = current_track['is_playing']
            if current_track:
                track_uri = current_track['item']['uri']
                song = Song(song_info, track_uri)
            else:
                Logger.warning("No track is currently playing.")
                return

            if self.songname != song.title:
                self.firstrun = True
                self.duration = 0
                self.songname = song.title
                self.totalduration = TimeUtils.time_to_ms(song.duration)
                self.lyrics = await self.mm.findLyrics(song)
                try:
                    if self.lyrics["error"] and self.netease:
                        Logger.error(f"Lyrics error: {self.lyrics['error']}, trying NetEase.")
                        self.lyrics = await self.ne.find_lyrics(song, self.romaji)
                except TypeError:
                    pass
                Logger.info(f"Fetched lyrics: {self.lyrics}")
                self.lyricnumber = 0
                self.totallyrics = len(self.lyrics) if self.lyrics else 0

            if not self.durationlock:
                self.duration = position // 1000
                self.durationlock = True

            if not self.is_playing:
                self._reset_media_state()
                self._process_stopped_state()

            if self.is_playing:
                self._process_playing_state(position, song)
        except Exception as e:
            Logger.error(f"Update song (spotify) info error: {str(e)}")

    def _reset_media_state(self):
        """Reset the state when media is paused or stopped."""
        self.started = False
        self.durationlock = False
        Logger.debug("Media state reset.")

    def _process_stopped_state(self):
        if self.pulsoid_enabled:
            heartrate = self.pulsoid_connector.get_latest_heart_rate(max_time=5)
            if heartrate:
                Logger.debug(f"Got heartrate | {heartrate}")
                self.pt = self.pulsoid_text.replace("$hr", str(heartrate))
            else:
                self.pt = ""

    def _process_playing_state(self, position, song):
        """Process the playing state to update song and lyrics info."""
        self.starttime = time.perf_counter()
        formatted_duration = TimeUtils.unformat_timespan(self.duration)
        sync_difference = abs(position - formatted_duration)
        if sync_difference >= 4000:
            logger.warning(
                f"Duration is off by {sync_difference}, resyncing {TimeUtils.unformat_timespan(self.duration)} | {position} ")
            if self.spotify_enabled:
                current_playback = self.sp.current_playback()
                if current_playback and current_playback['is_playing']:
                    current_position_ms = current_playback['progress_ms']
                    current_position_sec = current_position_ms * 0.001
                    self.duration = current_position_sec
                    self.firstrun = True
            else:
                Logger.warning(f"Duration is off by {sync_difference}, resyncing")
                self.duration = position // 1000
                self.firstrun = True

        try:
            if self.lyrics["error"]:
                end_time = time.perf_counter()
                elapsed_time = end_time - self.starttime

                if self.spotify_enabled and self.app_lock:
                    current_duration = self.sp.current_playback()['progress_ms']
                    self.duration = current_duration * 0.001
                else:
                    increment = 1.5 + round(elapsed_time, 2)
                    self.duration += increment
                Logger.debug(f"{position} || {self.duration} || {TimeUtils.unformat_timespan(self.duration)}")
                self.data = {
                    "title": song.title,
                    "artist": song.artist,
                    "duration": TimeUtils.seconds_to_m_s(self.duration),
                    "totalduration": song.duration,
                    "lyrics": self.placeholder,
                }
                if self.pulsoid_enabled:
                    heartrate = self.pulsoid_connector.get_latest_heart_rate(max_time=5)
                    if heartrate:
                        Logger.debug(f"Got heartrate | {heartrate}")
                        self.data["hr"] = heartrate
                Logger.debug(f"_process_playing_state completed in {elapsed_time:.4f} seconds")
                self.lastrunlabel.setText(f"Last Update Time: {datetime.now().strftime('%H:%M:%S')}")
        except TypeError:
            if self.spotify_enabled and self.app_lock:
                self._update_lyrics_spotify(position, song)
            else:
                self._update_lyrics(position, song)

    def _update_lyrics(self, position, song):
        """Update the lyrics based on the current playback position."""
        self.ended = len(self.lyrics)
        end_time = time.perf_counter()
        elapsed_time = end_time - self.starttime
        increment = 1.5 + round(elapsed_time, 2)
        self.duration += increment
        if self.lyricnumber >= self.ended:
            return
        try:
            currentlyrics = self.lyrics[self.lyricnumber]
            starttime = currentlyrics["startTime"]
            if self.firstrun and starttime + int(self.offset) >= TimeUtils.unformat_timespan(self.duration):
                self.data["lyrics"] = self.placeholder
            currentlyrics = self.lyrics[self.lyricnumber]
            starttime = currentlyrics["startTime"]
            Logger.debug(
                f"{starttime} || {position} || {self.duration} || {TimeUtils.unformat_timespan(self.duration)}")
            if self.firstrun and starttime + int(self.offset) <= TimeUtils.unformat_timespan(self.duration):
                self.started = True
                nearest_index = min(
                    range(len(self.lyrics)),
                    key=lambda i: abs(int(self.lyrics[i]['startTime']) - TimeUtils.unformat_timespan(self.duration))
                )
                nearest_dict = self.lyrics[nearest_index]
                self.data["lyrics"] = nearest_dict["text"]
                self.lyricnumber = nearest_index
                self.firstrun = False
            elif starttime + int(self.offset) <= TimeUtils.unformat_timespan(self.duration) and not self.firstrun:
                self.started = True
                self.lyricnumber += 1
                self.data["lyrics"] = currentlyrics["text"]

            self.data["title"] = song.title
            self.data["artist"] = song.artist
            self.data["duration"] = TimeUtils.seconds_to_m_s(self.duration)
            self.data["totalduration"] = song.duration

            if self.data["lyrics"] == "":
                self.data["lyrics"] = self.placeholder

            if self.contains_japanese(self.data["lyrics"]) and self.romaji:
                result = self.kakasi.convert(self.data["lyrics"])
                romaji_text = " ".join([item['hepburn'] for item in result])
                self.data["lyrics"] = romaji_text
                Logger.info(f"Converted lyrics to Romaji: {romaji_text}")
            end_time = time.perf_counter()
            elapsed_time = end_time - self.starttime

            if self.pulsoid_enabled:
                heartrate = self.pulsoid_connector.get_latest_heart_rate(max_time=5)
                if heartrate:
                    Logger.debug(f"Got heartrate | {heartrate}")
                    self.data["hr"] = heartrate
            Logger.debug(f"_update_lyrics completed in {elapsed_time:.4f} seconds")
            self.lastrunlabel.setText(f"Last Update Time: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            tb = traceback.format_exc()
            Logger.error(f"Error in _update_lyrics: {e}\n{tb}")

    def _update_lyrics_spotify(self, position, song):
        """Update the lyrics based on the current playback position."""
        current_playback = self.sp.current_playback()
        self.ended = len(self.lyrics)
        if self.lyricnumber == self.ended:
            if current_playback:
                current_position_ms = current_playback['progress_ms']
                current_position_sec = current_position_ms * 0.001
                self.duration = current_position_sec
                return
        if current_playback and current_playback['is_playing']:
            current_position_ms = current_playback['progress_ms']
            current_position_sec = current_position_ms * 0.001
            self.duration = current_position_sec
        try:
            currentlyrics = self.lyrics[self.lyricnumber]
            starttime = int(currentlyrics["startTime"])
            Logger.debug(
                f"{str(starttime)} || {position} || {self.duration} || {TimeUtils.unformat_timespan(self.duration)}")
            if self.firstrun and starttime - int(self.offset) >= TimeUtils.unformat_timespan(self.duration):
                self.data["lyrics"] = self.placeholder
            currentlyrics = self.lyrics[self.lyricnumber]
            starttime = currentlyrics["startTime"]
            if self.firstrun and int(starttime) + int(self.offset) <= TimeUtils.unformat_timespan(self.duration):
                self.started = True
                nearest_index = min(
                    range(len(self.lyrics)),
                    key=lambda i: abs(int(self.lyrics[i]['startTime']) - TimeUtils.unformat_timespan(self.duration))
                )
                nearest_dict = self.lyrics[nearest_index]
                self.data["lyrics"] = nearest_dict["text"]
                self.lyricnumber = nearest_index
                self.firstrun = False
            elif int(starttime) + int(self.offset) <= TimeUtils.unformat_timespan(self.duration) and not self.firstrun:
                self.started = True
                self.lyricnumber += 1
                self.data["lyrics"] = currentlyrics["text"]

            self.data["title"] = song.title
            self.data["artist"] = song.artist
            self.data["duration"] = TimeUtils.seconds_to_m_s(self.duration)
            self.data["totalduration"] = song.duration

            if self.data["lyrics"] == "":
                self.data["lyrics"] = self.placeholder

            if self.contains_japanese(self.data["lyrics"]) and self.romaji:
                result = self.kakasi.convert(self.data["lyrics"])
                romaji_text = " ".join([item['hepburn'] for item in result])
                self.data["lyrics"] = romaji_text
                Logger.info(f"Converted lyrics to Romaji: {romaji_text}")
            end_time = time.perf_counter()
            elapsed_time = end_time - self.starttime

            if self.pulsoid_enabled:
                heartrate = self.pulsoid_connector.get_latest_heart_rate(max_time=5)
                if heartrate:
                    Logger.debug(f"Got heartrate | {heartrate}")
                    self.data["hr"] = heartrate
            Logger.debug(f"_update_lyrics_spotify completed in {elapsed_time:.4f} seconds")
            self.lastrunlabel.setText(f"Last Update Time: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            tb = traceback.format_exc()
            Logger.error(f"Error in _update_lyrics: {e}\n{tb}")

    @staticmethod
    def contains_japanese(text):
        """Check if the given text contains Japanese characters."""
        japanese_pattern = re.compile(r'[\u3040-\u30FF\u4E00-\u9FFF]')
        return bool(japanese_pattern.search(text))


def main():
    global app
    app = QApplication([])
    app.neko_osc_widget = NekoOSC()
    app.neko_osc_widget.show()
    app.exec()


if __name__ == "__main__":
    main()