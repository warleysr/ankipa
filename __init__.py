from aqt import mw
from aqt.main import AnkiQt
from aqt.webview import AnkiWebView
from aqt.utils import showInfo
from aqt.qt import *
from aqt.sound import record_audio, play
from .pronunciation import pron_assess
from .tts import TTS
import tempfile
import shutil
import json
import re
import os


SETTINGS_ORGANIZATION = "github_warleysr"
SETTINGS_APPLICATION = "ankipa"
REMOVE_HTML_RE = re.compile("<[^<]+?>")
REMOVE_TAG_RE = re.compile("\[[^\]]+\]")
WORD_HTML = """
<h2 class="word tooltip [ERROR]">
[WORD]
<div class="bottom" style="min-width: 100px;">
    <p style="font-weight: bold;">[ERROR-INFO]</p>
    <u>[WORD]</u>
    <p>[SYLLABLES]</p>
    <i></i>
</div>
</h2>
"""


app_settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)

# Load Azure API data
addon = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(addon, "azure_data.json"), "r") as fp:
    data = json.load(fp)

# Remove temporary files
shutil.rmtree(tempfile.gettempdir() + os.sep + "ankipa", ignore_errors=True)


class AnkiPA:

    REFTEXT = None
    RECORDED = None
    TTS_GEN = None
    LAST_TTS = None

    @classmethod
    def test_pronunciation(cls):
        if not mw.reviewer.card:
            settings_dialog()
            return

        idx = app_settings.value("field-index", defaultValue=0)
        field = mw.col.models.fieldNames(mw.reviewer.card.note().model())[idx]
        to_read = mw.reviewer.card.note()[field]

        # Remove html tags
        to_read = re.sub(REMOVE_HTML_RE, " ", to_read).replace("&nbsp;", "")

        # Remove addons tags
        to_read = re.sub(REMOVE_TAG_RE, "", to_read).strip()

        cls.REFTEXT = to_read

        cid = mw.reviewer.card.id
        if cls.LAST_TTS != cid:
            AnkiPA.TTS_GEN = None
            cls.LAST_TTS = cid

        # Record user voice
        record_audio(mw, mw, False, cls.after_record)

    @classmethod
    def after_record(cls, recorded_voice):
        if not recorded_voice:
            return

        cls.RECORDED = recorded_voice

        region = app_settings.value("region")
        language = app_settings.value("language")
        key = app_settings.value("key")
        if not all((region, language, key)):
            showInfo("Please configure your Azure service properly.")
            return

        # Perform pronunciation assessment
        lang = data["languages"][language][0]
        phoneme_system = app_settings.value("phoneme-system", defaultValue="IPA")
        result = pron_assess(
            region, lang, key, cls.REFTEXT, recorded_voice, phoneme_system
        )

        if result["RecognitionStatus"] != "Success":
            showInfo("There was an error recognizing your speech.")
            return

        scores = result["NBest"][0]
        accuracy = scores["AccuracyScore"]
        fluency = scores["FluencyScore"]
        pronunciation = scores["PronScore"]

        with open(os.path.join(addon, "template.html"), "r") as ft:
            html_template = ft.read()

            # Replace percentages in template
            html = html_template.replace("[ACCURACY]", str(int(accuracy)))
            html = html.replace("[FLUENCY]", str(int(fluency)))
            html = html.replace("[PRONUNCIATION]", str(int(pronunciation)))

            # Replace percentages colors in template
            html = html.replace("[ACCURACY-COLOR]", get_color(accuracy))
            html = html.replace("[FLUENCY-COLOR]", get_color(fluency))
            html = html.replace("[PRONUNCIATION-COLOR]", get_color(pronunciation))

        errors = {"Mispronunciation": 0, "Omission": 0, "Insertion": 0}

        words_html = ""
        for word in scores["Words"]:
            syllables = ""
            if "Syllables" in word:
                syllable_count = len(word["Syllables"])
                for i, syllable in enumerate(word["Syllables"]):
                    syllable_score = syllable["AccuracyScore"]
                    add = " &#x2022; " if i < (syllable_count - 1) else ""
                    syllables += (
                        f"<span style='color: {get_color(syllable_score)};'>"
                        + f"{syllable['Syllable']}</span>"
                        + f"<span style='color: white;'>{add}</span>"
                    )

            error = word["ErrorType"]
            words_html += (
                WORD_HTML.replace("[WORD]", word["Word"])
                .replace("[SYLLABLES]", syllables)
                .replace("[ERROR]", error)
                .replace("[ERROR-INFO]", error if error != "None" else "Correct")
            )
            if error != "None":
                errors[error] += 1

        # Replace wordlist
        html = html.replace("[WORDLIST]", words_html)

        # Replace errors count
        html = html.replace("[MISPRONUNCIATIONS]", str(errors["Mispronunciation"]))
        html = html.replace("[OMISSIONS]", str(errors["Omission"]))
        html = html.replace("[INSERTIONS]", str(errors["Insertion"]))

        ResultsDialog(mw, html, pronunciation).exec()


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
    def __init__(self, mw: AnkiQt, html: str, pronunciation_score: float):
        super().__init__(mw)
        self.mw = mw
        self.config = self.mw.addonManager.getConfig(__name__)
        self.setWindowTitle("AnkiPA Results")

        vbox = QVBoxLayout()
        self.web = AnkiWebView(self, title="AnkiPA Results")

        container = QWidget(self)
        container.setFixedSize(250, 35)
        container.move(5, 5)
        self.buttons = QHBoxLayout(container)

        self.replay_btn = QPushButton("Replay your voice")
        self.replay_btn.clicked.connect(replay_voice)

        self.play_tts_btn = QPushButton("Play TTS")
        self.play_tts_btn.clicked.connect(replay_tts)

        self.buttons.addWidget(self.replay_btn)
        self.buttons.addWidget(self.play_tts_btn)

        vbox.addLayout(self.buttons)
        vbox.addWidget(self.web)

        self.web.setHtml(html)
        self.resize(1024, 720)

        self.setLayout(vbox)

        if app_settings.value("sound-effects", "false") == "true":
            play(get_sound(pronunciation_score))

    def exec(self) -> int:
        return super().exec()

    def closeEvent(self, a0) -> None:
        return super().closeEvent(a0)


def settings_dialog():
    SettingsDialog(app_settings, mw).show()


class SettingsDialog(QDialog):
    _FONT_HEADER = QFont()
    _FONT_HEADER.setPointSize(12)
    _FONT_HEADER.setBold(True)

    def __init__(self, my_settings: QSettings, *args, **kwargs):
        super(SettingsDialog, self).__init__(*args, **kwargs)
        self.setWindowTitle("AnkiPA Settings")
        self.my_settings = my_settings

        self.base_layout = QVBoxLayout()

        buttons = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(buttons)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.api_label = QLabel("Configure your Azure service")
        self.api_label.setFont(self._FONT_HEADER)

        # Key input
        self.key_label = QLabel("API key:")
        self.key_field = QLineEdit()

        curr_key = self.my_settings.value("key")
        if curr_key is not None:
            self.key_field.setText(curr_key)

        # Region options
        self.region_label = QLabel("Region:")
        self.region_combo = QComboBox()
        self.region_combo.addItems(data["regions"])

        curr_region = self.my_settings.value("region")
        if curr_region is not None:
            self.region_combo.setCurrentIndex(data["regions"].index(curr_region))

        # Language options
        self.lang_label = QLabel("Language:")
        self.lang_combo = QComboBox()
        langs = list(data["languages"].keys())
        self.lang_combo.addItems(langs)

        curr_lang = self.my_settings.value("language")
        if curr_lang is not None:
            self.lang_combo.setCurrentIndex(langs.index(curr_lang))

        # Field index option
        self.fidx_label = QLabel("Field index:")
        self.fidx_spin = QSpinBox()
        self.fidx_spin.setValue(self.my_settings.value("field-index", defaultValue=0))

        # Phoneme system for en-us
        phonemes = ["IPA", "SAPI"]

        self.phoneme_label = QLabel("Phoneme system (only for en-US/GB):")
        self.phoneme_combo = QComboBox()
        self.phoneme_combo.addItems(phonemes)

        curr_phoneme = self.my_settings.value("phoneme-system", defaultValue="IPA")
        self.phoneme_combo.setCurrentIndex(phonemes.index(curr_phoneme))

        # Sound effects
        self.sound_effects_check = QCheckBox("Enable sound effects on results")
        self.sound_effects_check.setChecked(
            True
            if self.my_settings.value("sound-effects", "false") == "true"
            else False
        )

        # Add elements to base layout
        self.base_layout.addWidget(self.api_label)
        self.base_layout.addWidget(self.key_label)
        self.base_layout.addWidget(self.key_field)
        self.base_layout.addWidget(self.region_label)
        self.base_layout.addWidget(self.region_combo)
        self.base_layout.addWidget(self.lang_label)
        self.base_layout.addWidget(self.lang_combo)
        self.base_layout.addWidget(self.fidx_label)
        self.base_layout.addWidget(self.fidx_spin)
        self.base_layout.addWidget(self.phoneme_label)
        self.base_layout.addWidget(self.phoneme_combo)
        self.base_layout.addWidget(self.sound_effects_check)
        self.base_layout.addWidget(self.buttonBox)

        self.setLayout(self.base_layout)

    def accept(self):
        self.my_settings.setValue("key", self.key_field.text())
        self.my_settings.setValue("region", self.region_combo.currentText())
        self.my_settings.setValue("language", self.lang_combo.currentText())
        self.my_settings.setValue("phoneme-system", self.phoneme_combo.currentText())
        self.my_settings.setValue("field-index", self.fidx_spin.value())
        self.my_settings.setValue("sound-effects", self.sound_effects_check.isChecked())
        super(SettingsDialog, self).accept()

    def reject(self):
        super(SettingsDialog, self).reject()


cp_action = QAction("Test Your Pronunciation", mw)
cp_action.triggered.connect(AnkiPA.test_pronunciation)
mw.form.menuTools.addAction(cp_action)
cp_action.setShortcut(QKeySequence("Ctrl+W"))

cps_action = QAction("AnkiPA Settings", mw)
cps_action.triggered.connect(settings_dialog)
mw.form.menuTools.addAction(cps_action)
