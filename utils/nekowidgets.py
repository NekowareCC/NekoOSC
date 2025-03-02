import asyncio
import json
import logging
import os
from functools import partial
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from PyQt6.QtGui import (QTextCursor, QTextOption)
from PyQt6.QtWidgets import (QHBoxLayout,
                             QPlainTextEdit, QCheckBox,
                             QLineEdit, QGroupBox, QSpacerItem,
                             QSizePolicy, QTextEdit, QScrollArea)

from main import Logger
from utils.animator import NekoAnimator

logger = logging.getLogger(__name__)

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QPushButton, QSpacerItem, QSizePolicy
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer


class AnimationsTab(QWidget):
    def __init__(self, animator):
        super().__init__()
        self.animator = animator
        self.percentage = 0

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setStyleSheet(""" 
            background-color: #242424;
            color: white;
            padding: 10px;
            font-family: ryo-gothic-plusn, sans-serif;
            border: 2px solid #666;
            border-radius: 5px;
        """)

        self.title_label = QLabel("Current Animations")
        self.title_label.setFont(QFont("ryo-gothic-plusn", 18, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_label)

        button_layout = QHBoxLayout()

        self.refresh_button = QPushButton("Refresh Animations")
        self.refresh_button.setStyleSheet(""" 
                    QPushButton {
                        background-color: #444;
                        color: white;
                        border: 1px solid #666;
                        border-radius: 5px;
                        padding: 8px;
                        font-size: 14px;
                        font-family: ryo-gothic-plusn, sans-serif;
                    }
                    QPushButton:hover {
                        background-color: #555;
                    }
                    QPushButton:pressed {
                        background-color: #333;
                    }
                """)
        self.refresh_button.clicked.connect(self.animator.load_animations)
        button_layout.addWidget(self.refresh_button)

        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.setStyleSheet("""
                    QPushButton {
                        background-color: #444;
                        color: white;
                        border: 1px solid #666;
                        border-radius: 5px;
                        padding: 8px;
                        font-size: 14px;
                        font-family: ryo-gothic-plusn, sans-serif;
                    }
                    QPushButton:hover {
                        background-color: #555;
                    }
                    QPushButton:pressed {
                        background-color: #333;
                    }
                """)
        self.open_folder_button.clicked.connect(self.open_animations_folder)
        button_layout.addWidget(self.open_folder_button)

        main_layout.addLayout(button_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

        self.animation_list_widget = QWidget()
        self.animation_list_layout = QVBoxLayout(self.animation_list_widget)
        self.animation_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.animation_list_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.scroll_area.setWidget(self.animation_list_widget)

        self.update_animation_list()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animations)
        self.timer.start(1500)

    def open_animations_folder(self):
        """Open the folder containing animations."""
        animations_folder = os.path.join(os.getenv("LOCALAPPDATA", ""), "Nekoware", "NekoOSC", "animations")
        if os.path.isdir(animations_folder):
            os.startfile(animations_folder)
        else:
            print(f"Animations folder does not exist: {animations_folder}")

    def update_animation_list(self):
        self.clear_animation_list()

        for animation in self.animator.preview_list:
            group_box = QGroupBox(f"*{animation.name} | {'Duration' if animation.type == 'duration' else 'Frame'}: "
                                  f"{self.percentage if animation.type == 'percentage' else ''}"
                                  f"{'%/' if animation.type == 'percentage' else ''}"
                                  f"{animation.current_frame.duration if animation.type == 'duration' else animation.current_frame.percentage}"
                                  f"{'ms' if animation.type == 'duration' else '%'}")
            group_box.setStyleSheet("""
                QGroupBox { 
                    border: 1px solid gray;
                    border-radius: 5px;
                    margin-top: 0.5em;
                    background-color: #2C2C2C;
                    font-family: ryo-gothic-plusn, sans-serif;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 3px 0 3px;
                    color: #E0E0E0;
                }
            """)

            group_layout = QVBoxLayout()
            group_layout.setContentsMargins(10, 10, 10, 10)
            group_layout.setSpacing(10)

            frame_text = QLabel(f"{animation.current_frame.text}")
            frame_text.setStyleSheet("""
                color: #B0B0B0; 
                font-size: 12px; 
                font-family: ryo-gothic-plusn, sans-serif;
            """)
            group_layout.addWidget(frame_text)

            group_box.setLayout(group_layout)
            self.animation_list_layout.addWidget(group_box)

        self.animation_list_widget.setLayout(self.animation_list_layout)
        self.animation_list_widget.update()

    def update_animations(self):
        """Updates all animations with their next frame and refreshes the UI."""
        self.percentage += 10
        if self.percentage >= 101:
            self.percentage = 0

        for animation in self.animator.preview_list:
            animation.next_frame(self.percentage)

        self.update_animation_list()

    def clear_animation_list(self):
        """Clears the animation list from the layout."""
        for i in reversed(range(self.animation_list_layout.count())):
            item = self.animation_list_layout.itemAt(i)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.animation_list_layout.update()


class ConsoleOutput(QPlainTextEdit):
    new_text_signal = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 10))
        self.setMaximumBlockCount(1000)
        self.document().setMaximumBlockCount(1000)
        self.new_text_signal.connect(self._append)

    def _append(self, text, color=None):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if color:
            format = cursor.charFormat()
            format.setForeground(QColor(color))
            cursor.setCharFormat(format)
        cursor.insertText(text)
        self.ensureCursorVisible()


class ConfigurationManager:
    def __init__(self, config_path, nekoosc):
        self.config_path = config_path
        self.config_data = self.load_config()
        self.nekoosc = nekoosc

    def load_config(self):
        """Load the configuration from the config.json file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading config file: {e}")
            return {}

    def save_config(self):
        """Save the configuration to the config.json file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
            self.nekoosc.load_config(self.config_path)
        except Exception as e:
            print(f"Error saving config file: {e}")

    def get_value(self, key, default=None):
        """Get a value from the configuration using a dot-separated key."""
        keys = key.split(".")
        current = self.config_data
        for k in keys:
            if k in current:
                current = current[k]
            else:
                return default
        return current

    def set_value(self, key, value):
        """Set a value in the configuration using a dot-separated key."""
        keys = key.split(".")
        current = self.config_data
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
        self.save_config()


class ConfigTabs(QTabWidget):
    def __init__(self, nekooscpath, nekoosc_instance, parent=None):
        super().__init__(parent)
        self.nekooscpath = nekooscpath
        self.config_manager = ConfigurationManager(os.path.join(nekooscpath, "config.json"), nekoosc_instance)
        self.create_tabs()
        self.nekoosc = nekoosc_instance

    def create_tabs(self):
        """Create a tab for each section in the config data."""
        config_data = self.config_manager.config_data
        for section, settings in config_data.items():
            tab = QWidget()
            tab_layout = QVBoxLayout()
            tab_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            scroll_area = QScrollArea()
            scroll_widget = QWidget()
            scroll_layout = QVBoxLayout()
            scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            self.add_config_options(scroll_layout, settings, section)

            scroll_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
            scroll_widget.setLayout(scroll_layout)
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(scroll_widget)

            tab_layout.addWidget(scroll_area)
            tab.setLayout(tab_layout)
            self.addTab(tab, section.capitalize())

    def add_config_options(self, layout, settings, parent_key=""):
        """Add configuration options to the layout."""
        if not isinstance(settings, dict):
            print(f"Skipping non-dictionary settings: {settings}")
            return

        for key, value in settings.items():
            full_key = f"{parent_key}.{key}" if parent_key else key

            if isinstance(value, dict):
                group_box = QGroupBox(key.capitalize())
                group_box.setStyleSheet(
                    "QGroupBox { border: 1px solid gray; border-radius: 5px; margin-top: 0.5em; } "
                    "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }"
                )
                group_layout = QVBoxLayout()
                group_layout.setContentsMargins(10, 10, 10, 10)
                group_layout.setSpacing(10)

                self.add_config_options(group_layout, value, full_key)

                group_box.setLayout(group_layout)
                layout.addWidget(group_box)
            elif isinstance(value, bool):
                check_box = QCheckBox(key.capitalize())
                check_box.setChecked(value)
                check_box.stateChanged.connect(
                    self.handle_checkbox_change(full_key)
                )
                layout.addWidget(check_box)
            elif isinstance(value, (int, float, str)):
                group_box = QGroupBox(key)
                group_box.setStyleSheet(
                    "QGroupBox { border: 1px solid gray; border-radius: 5px; margin-top: 0.5em; } "
                    "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }"
                )
                group_layout = QVBoxLayout()
                group_layout.setContentsMargins(10, 10, 10, 10)
                group_layout.setSpacing(10)

                if isinstance(value, str):
                    if key in ["Format", "Text", "Idle"]:
                        text_edit = QTextEdit()
                        text_option = QTextOption()
                        text_option.setWrapMode(QTextOption.WrapMode.WordWrap)
                        text_edit.document().setDefaultTextOption(text_option)

                        text_edit.setMinimumHeight(100)
                        text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                        text_edit.setPlainText(value)
                        text_edit.textChanged.connect(
                            self.handle_text_edit_change(full_key, text_edit)
                        )
                        group_layout.addWidget(text_edit)

                    else:
                        line_edit = QLineEdit()
                        line_edit.setText(value)
                        line_edit.textChanged.connect(
                            self.handle_line_edit_change(full_key, line_edit)
                        )
                        group_layout.addWidget(line_edit)
                    group_box.setLayout(group_layout)
                    layout.addWidget(group_box)
            else:
                print(f"Unsupported type for {key}: {type(value)}")

    def handle_text_edit_change(self, key, text_edit):
        """Handle changes in QTextEdit."""

        def inner():
            self.config_manager.set_value(key, text_edit.toPlainText())

        return inner

    def handle_line_edit_change(self, key, line_edit):
        """Handle changes in QLineEdit."""

        def inner():
            self.config_manager.set_value(key, line_edit.text())

        return inner

    def handle_checkbox_change(self, key):
        """Handle changes in QCheckBox."""

        def inner(state):
            if key == "pulsoid.Enabled" and bool(state):
                asyncio.run(self.nekoosc.setup_pulsoid())
            elif key == "spotify.Enabled" and bool(state):
                asyncio.run(self.nekoosc.setup_spotify())
            self.config_manager.set_value(key, bool(state))

        return inner


class WorkerSignals(QObject):
    data_updated = pyqtSignal(dict)
    osc_sent = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)


class Worker(QThread):
    def __init__(self, neko_osc_instance):
        super().__init__()
        self.neko_osc = neko_osc_instance
        self.running = False
        self.signals = WorkerSignals()
        self.loop = None
        self._stop_event = asyncio.Event()

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self.main_loop())
        except Exception as e:
            logger.exception(f"Worker error: {str(e)}")
            self.signals.error.emit(f"Worker error: {str(e)}")
        finally:
            self.loop.close()
            self.signals.finished.emit()

    async def main_loop(self):
        while True:
            if self.running and not self._stop_event.is_set():
                try:
                    await asyncio.gather(
                        self.refresh_data(),
                        self.send_message(),
                        asyncio.sleep(1.5)
                    )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception(f"Loop error: {str(e)}")
                    self.signals.error.emit(f"Loop error: {str(e)}")
                    break
            else:
                await asyncio.sleep(0.1)
                await asyncio.sleep(0)

            if self._stop_event.is_set():
                break

    async def refresh_data(self):
        """Refresh media data."""
        try:
            song_info, playback_info, timeline_info = await self.neko_osc._get_media_info()
            if all([song_info, playback_info, timeline_info]):
                if self.neko_osc.spotify_enabled and self.neko_osc.app_lock:
                    await self.neko_osc._update_song_info_spotify(song_info)
                else:
                    await self.neko_osc._update_song_info(song_info, playback_info,
                                                          timeline_info)
                self.signals.data_updated.emit(self.neko_osc.data)
        except Exception as e:
            logger.exception(f"Refresh error: {str(e)}")
            self.signals.error.emit(f"Refresh error: {str(e)}")

    async def send_message(self):
        """Send OSC message."""
        if self.neko_osc.is_playing:
            formatted_message = Formatter.format(
                self.neko_osc)
            Logger.info(f"Sending OSC message: \n\n{formatted_message}\n\n")
            if self.neko_osc.osc.send_message(formatted_message):
                self.neko_osc.connection_status.setText("Connected")
            else:
                self.neko_osc.connection_status.setText("Disconnected")
            self.neko_osc.osc_lock = False
            self.signals.osc_sent.emit()
        elif not self.neko_osc.is_playing:
            if self.neko_osc.idle:
                Logger.info("Sending idle message")
                text = Formatter.format(self.neko_osc, self.neko_osc.idle)
                self.neko_osc.osc.send_message(text)
                self.neko_osc.data_display.setText(text if not self.neko_osc.invisible else text[:-2])
            else:
                Logger.info("Sending empty OSC message")
                if self.neko_osc.osc.send_message(""):
                    self.neko_osc.connection_status.setText("Connected")
                else:
                    self.neko_osc.connection_status.setText("Disconnected")
                self.neko_osc.osc_lock = True
            self.signals.osc_sent.emit()

    def start_processing(self):
        self.running = True

    def stop_processing(self):
        self.running = False

    def stop(self):
        self._stop_event.set()
        self.wait()


class Formatter:
    @staticmethod
    def format(nekoosc, text=""):
        """Format the data dictionary using the provided template."""
        try:
            def get_animation(animation, percentage=0):
                if nekoosc.is_playing and not percentage:
                    percentage = nekoosc.duration / nekoosc.totalduration
                    percentage = percentage * 100000
                return nekoosc.animations[animation.name].next_frame(percentage=percentage).text

            def adjust_with_pulsoid():
                pulsoid_text = nekoosc.pulsoid_text.replace("$hr", hr or "")
                for key, value in nekoosc.animations.items():
                    pulsoid_text = pulsoid_text.replace(f"*{key}", get_animation(value, int(hr) or 1))

                pulsoid_text_length = len(pulsoid_text)
                if template:
                    if len(template) + pulsoid_text_length + 1 > 144:
                        return template[:144 - pulsoid_text_length] + "\n" + pulsoid_text
                    return template + "\n" + pulsoid_text
                else:
                    return pulsoid_text

            template = nekoosc.format if not text else text
            hr = 0
            if nekoosc.pulsoid_enabled:
                hr = str(nekoosc.pulsoid_connector.get_latest_heart_rate(max_time=5))
                if not hr:
                    hr = 0

            for key, value in nekoosc.data.items():
                if value:
                    template = template.replace(f"${key}", str(value))
                elif key != "lyrics" and not value and not text or not nekoosc.is_playing and not text:
                    template = ""
                    template = template.replace(f"${key}", "")
                    if nekoosc.pulsoid_enabled and int(hr) != 0:
                        return adjust_with_pulsoid()
                    elif nekoosc.pulsoid_enabled and int(hr) == 0 and nekoosc.invisible:
                        return adjust_with_pulsoid() + "\u0003\u001f"
                    return ""
                elif key and not value:
                    template = template.replace(f"${key}", "")

            for key, value in nekoosc.animations.items():
                template = template.replace(f"*{key}", get_animation(value))

            if nekoosc.pulsoid_enabled and int(hr) != 0:
                if nekoosc.invisible:
                    return adjust_with_pulsoid() + "\u0003\u001f"
                else:
                    return adjust_with_pulsoid()
            elif nekoosc.invisible and not nekoosc.pulsoid_enabled or int(hr) == 0 and nekoosc.invisible:
                return (template[:142] if len(template) >= 144 else template) + "\u0003\u001f"

            return template

        except Exception as e:
            Logger.error(f"Error in Formatter: {e}")
            return ""