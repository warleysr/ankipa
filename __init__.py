from aqt import mw
from aqt.webview import AnkiWebView
from aqt.utils import showInfo
from aqt.qt import *
from aqt.sound import play
from .tts import TTS
from .ankipa import AnkiPA
import tempfile
import shutil
import json
import os


SETTINGS_ORGANIZATION = "github_warleysr"
SETTINGS_APPLICATION = "ankipa"

app_settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
cp_action = QAction("Test Your Pronunciation", mw)

# Load Azure API data
addon = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(addon, "azure_data.json"), "r") as fp:
    data = json.load(fp)

# Load HTML template
with open(os.path.join(addon, "template.html"), "r") as ft:
    html_template = ft.read()

# Remove temporary files
shutil.rmtree(tempfile.gettempdir() + os.sep + "ankipa", ignore_errors=True)


def replay_voice():
    play(AnkiPA.RECORDED)


def replay_tts():
    if AnkiPA.TTS_GEN is None:
        region = app_settings.value("region")
        language = app_settings.value("language")
        key = app_settings.value("key")
        voice = data["languages"][language][1]

        generated = TTS.gen_tts_audio(region, key, voice, AnkiPA.REFTEXT)
        if generated is None:
            showInfo("There was an error generating the TTS audio.")
            return

        AnkiPA.TTS_GEN = generated

    play(AnkiPA.TTS_GEN)


def get_color(percentage):
    if percentage < 30:
        return "red"
    elif percentage < 50:
        return "orange"
    elif percentage < 70:
        return "#fcd303"
    else:
        return "green"


def get_sound(percentage):
    sound = "high.mp3"
    if percentage < 30:
        sound = "low.mp3"
    elif percentage < 50:
        sound = "medium-low.mp3"
    elif percentage < 70:
        sound = "medium-high.mp3"

    return os.path.join(addon, "sounds" + os.sep + sound)


class ResultsDialog(QDialog):
    def __init__(self, html: str, pronunciation_score: float):
        super().__init__(mw)
        self.setWindowTitle("AnkiPA Results")

        vbox = QVBoxLayout()
        self.web = AnkiWebView(self)

        container = QWidget(self)
        container.setFixedSize(280, 40)
        container.move(5, 5)
        self.buttons = QHBoxLayout(container)

        self.replay_btn = QPushButton("Replay your voice")
        self.replay_btn.setFixedSize(150, 20)
        self.replay_btn.clicked.connect(replay_voice)

        self.play_tts_btn = QPushButton("Play TTS")
        self.play_tts_btn.setFixedSize(100, 20)
        self.play_tts_btn.clicked.connect(replay_tts)

        self.buttons.addWidget(self.replay_btn)
        self.buttons.addWidget(self.play_tts_btn)

        vbox.addLayout(self.buttons)
        vbox.addWidget(self.web)

        self.web.setHtml(html)
        self.resize(1024, 720)

        self.setLayout(vbox)

        if app_settings.value("sound-effects", "False") == "True":
            play(get_sound(pronunciation_score))

    def closeEvent(self, a0) -> None:
        return super().closeEvent(a0)


class SettingsDialog(QDialog):
    _FONT_HEADER = QFont()
    _FONT_HEADER.setPointSize(12)
    _FONT_HEADER.setBold(True)

    def __init__(self, *args, **kwargs):
        super(SettingsDialog, self).__init__(*args, **kwargs)
        self.setWindowTitle("AnkiPA Settings")

        self.base_layout = QVBoxLayout()

        buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.api_label = QLabel("Configure your AnkiPA addon")
        self.api_label.setFont(self._FONT_HEADER)

        # Key input
        self.key_label = QLabel("Azure API key:")
        self.key_field = QLineEdit()
        self.key_field.setText(app_settings.value("key"))

        # Region options
        self.region_label = QLabel("Region:")
        self.region_combo = QComboBox()
        self.region_combo.addItems(data["regions"])

        curr_region = app_settings.value("region")
        if curr_region is not None:
            self.region_combo.setCurrentIndex(data["regions"].index(curr_region))

        # Language options
        self.lang_label = QLabel("Language:")
        self.lang_combo = QComboBox()
        langs = list(data["languages"].keys())
        self.lang_combo.addItems(langs)

        curr_lang = app_settings.value("language")
        if curr_lang is not None:
            self.lang_combo.setCurrentIndex(langs.index(curr_lang))

        # Fields list
        self.fields_label = QLabel("Card fields:")
        self.fields_text = QLineEdit()
        self.fields_text.setText(app_settings.value("fields"))
        self.fields_text.setPlaceholderText("front, back, other")

        # Timeout
        self.timeout_label = QLabel("Timeout:")
        self.timeout_spin = QSpinBox()
        timeout = int(app_settings.value("timeout", defaultValue=5))
        self.timeout_spin.setValue(timeout)

        # Phoneme system for en-us
        phonemes = ["IPA", "SAPI"]

        self.phoneme_label = QLabel("Phoneme system (only for en-US/GB):")
        self.phoneme_combo = QComboBox()
        self.phoneme_combo.addItems(phonemes)

        curr_phoneme = app_settings.value("phoneme-system", defaultValue="IPA")
        self.phoneme_combo.setCurrentIndex(phonemes.index(curr_phoneme))

        # Shortcut
        self.shortcut_label = QLabel("Shortcut:")
        self.shortcut_box = QHBoxLayout()
        self.shortcut_label_2 = QLabel("Ctrl + ")
        self.shortcut_box.addStretch()
        self.shortcut_field = QLineEdit()
        self.shortcut_field.setFixedWidth(50)
        self.shortcut_box.addWidget(self.shortcut_label_2)
        self.shortcut_box.addWidget(self.shortcut_field)
        self.shortcut_box.addStretch()

        curr_shortcut = app_settings.value("shortcut", defaultValue="W")
        self.shortcut_field.setText(curr_shortcut)

        # Sound effects
        self.sound_effects_check = QCheckBox("Enable sound effects on results")
        self.sound_effects_check.setChecked(
            True if app_settings.value("sound-effects", "False") == "True" else False
        )

        # Add elements to base layout
        self.base_layout.addWidget(self.api_label)
        self.base_layout.addWidget(self.key_label)
        self.base_layout.addWidget(self.key_field)
        self.base_layout.addWidget(self.region_label)
        self.base_layout.addWidget(self.region_combo)
        self.base_layout.addWidget(self.lang_label)
        self.base_layout.addWidget(self.lang_combo)
        self.base_layout.addWidget(self.fields_label)
        self.base_layout.addWidget(self.fields_text)
        self.base_layout.addWidget(self.timeout_label)
        self.base_layout.addWidget(self.timeout_spin)
        self.base_layout.addWidget(self.phoneme_label)
        self.base_layout.addWidget(self.phoneme_combo)
        self.base_layout.addWidget(self.shortcut_label)
        self.base_layout.addLayout(self.shortcut_box)
        self.base_layout.addWidget(self.sound_effects_check)
        self.base_layout.addWidget(self.buttonBox)

        self.setLayout(self.base_layout)

    def accept(self):
        app_settings.setValue("key", self.key_field.text())
        app_settings.setValue("region", self.region_combo.currentText())
        app_settings.setValue("language", self.lang_combo.currentText())
        app_settings.setValue("phoneme-system", self.phoneme_combo.currentText())
        app_settings.setValue("fields", self.fields_text.text())
        app_settings.setValue("timeout", self.timeout_spin.value())

        curr_shortcut = self.shortcut_field.text()
        app_settings.setValue("shortcut", curr_shortcut)
        cp_action.setShortcut(QKeySequence(f"Ctrl+{curr_shortcut}"))

        app_settings.setValue(
            "sound-effects", str(self.sound_effects_check.isChecked())
        )

        super(SettingsDialog, self).accept()

    def reject(self):
        super(SettingsDialog, self).reject()


def settings_dialog():
    SettingsDialog(mw).show()


curr_shortcut = app_settings.value("shortcut", defaultValue="W")
cp_action.triggered.connect(AnkiPA.test_pronunciation)
mw.form.menuTools.addAction(cp_action)
cp_action.setShortcut(QKeySequence(f"Ctrl+{curr_shortcut}"))

cps_action = QAction("AnkiPA Settings", mw)
cps_action.triggered.connect(settings_dialog)
mw.form.menuTools.addAction(cps_action)
