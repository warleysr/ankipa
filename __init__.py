from aqt import mw
from aqt.main import AnkiQt
from aqt.webview import AnkiWebView
from aqt.utils import showInfo
from aqt.qt import *
from aqt.sound import record_audio
from .pronunciation import pron_assess
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
        <p>[WORD]</p>
        <i></i>
    </div>
    </h2>
</div>
"""


app_settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)

# Load Azure API data
addon = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(addon, "azure_data.json"), "r") as fp:
    data = json.load(fp)


class AnkiPA:

    REFTEXT = None

    @classmethod
    def test_pronunciation(cls):
        if not mw.reviewer.card:
            settings_dialog()
            return

        to_read = mw.reviewer.card.note()["Frente"]
        # Remove html tags
        to_read = re.sub(REMOVE_HTML_RE, " ", to_read).replace("&nbsp;", "")
        # Remove addons tags
        to_read = re.sub(REMOVE_TAG_RE, "", to_read).strip()

        cls.REFTEXT = to_read

        record_audio(mw, mw, False, cls.after_record)

    @classmethod
    def after_record(cls, recorded_voice):
        if not recorded_voice:
            return

        region = app_settings.value("region")
        language = app_settings.value("language")
        key = app_settings.value("key")
        if not all((region, language, key)):
            showInfo("Please configure your Azure service properly.")
            return

        lang = data["languages"][language]
        result = pron_assess(region, lang, key, cls.REFTEXT, recorded_voice)

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

        words_html = ""
        for word in scores["Words"]:
            words_html += WORD_HTML.replace("[WORD]", word["Word"]).replace(
                "[ERROR]", word["ErrorType"]
            )

        html = html.replace("[WORDLIST]", words_html)

        ResultsDialog(mw, html).exec()


def get_color(percentage):
    if percentage < 30:
        return "red"
    elif percentage < 50:
        return "orange"
    elif percentage < 70:
        return "#fcd303"
    else:
        return "green"


class ResultsDialog(QDialog):
    def __init__(self, mw: AnkiQt, html: str):
        super().__init__(mw)
        self.mw = mw
        self.config = self.mw.addonManager.getConfig(__name__)
        self.setWindowTitle("AnkiPA Results")

        vbox = QVBoxLayout()
        self.web = AnkiWebView(self, title="AnkiPA Results")
        vbox.addWidget(self.web)
        self.web.set_open_links_externally(False)
        self.web.setHtml(html)
        self.web.setZoomFactor(1)
        self.resize(1024, 720)
        self.setLayout(vbox)

    def exec(self) -> int:
        return super().exec()


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

        self.base_layout.addWidget(self.api_label)
        self.base_layout.addWidget(self.key_label)
        self.base_layout.addWidget(self.key_field)
        self.base_layout.addWidget(self.region_label)
        self.base_layout.addWidget(self.region_combo)
        self.base_layout.addWidget(self.lang_label)
        self.base_layout.addWidget(self.lang_combo)
        self.base_layout.addWidget(self.buttonBox)
        self.setLayout(self.base_layout)

    def accept(self):
        self.my_settings.setValue("key", self.key_field.text())
        self.my_settings.setValue("region", self.region_combo.currentText())
        self.my_settings.setValue("language", self.lang_combo.currentText())
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
