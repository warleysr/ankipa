from aqt import mw, gui_hooks
from aqt.webview import AnkiWebView, WebContent
from aqt.utils import showInfo
from aqt.qt import *
from aqt.sound import play, MpvManager, av_player
from .tts import TTS
from .ankipa import AnkiPA
import tempfile
import time
import shutil
import json
import os
from .stats import load_stats
from .updater import update_available_languages


SETTINGS_ORGANIZATION = "github_warleysr"
SETTINGS_APPLICATION = "ankipa"

app_settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)

# Load Azure API data
addon = os.path.dirname(os.path.abspath(__file__))
data_file = os.path.join(addon, "azure_data.json")
with open(data_file, "r") as fp:
    data = json.load(fp)

# Update languages
new_languages = update_available_languages(data["languages"])
if new_languages:
    with open(data_file, "w") as fp:
        json.dump(data, fp, indent=4)
    from . import showInfo

    update_message = (
        f"<h3>AnkiPA Update</h3><br> These {len(new_languages)} new languages "
        "was added to the addon:<br><br>"
    )
    for lang in new_languages:
        update_message += f"&#x2022; {lang}<br>"
    showInfo(update_message)

fp.close()

# Load HTML template
with open(os.path.join(addon, "template.html"), "r") as ft:
    html_template = ft.read()

# Load statistics
load_stats(addon)

# Remove temporary files
shutil.rmtree(tempfile.gettempdir() + os.sep + "ankipa", ignore_errors=True)

def set_audio_speed(speed: float):
    for player in av_player.players:
        if isinstance(player, MpvManager):
            player.command("set_property", "speed", speed)


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
        container.setFixedSize(380, 40)
        container.move(5, 5)
        self.options = QHBoxLayout(container)

        self.replay_btn = QPushButton("Replay your voice")
        self.replay_btn.setFixedSize(150, 20)
        self.replay_btn.clicked.connect(self.replay_voice)

        self.play_tts_btn = QPushButton("Play TTS")
        self.play_tts_btn.setFixedSize(100, 20)
        self.play_tts_btn.clicked.connect(self.replay_tts)

        self.audio_speed = QSlider(Qt.Orientation.Horizontal, self)
        self.audio_speed.setFixedSize(100, 20)
        self.audio_speed.setRange(10, 200)
        self.audio_speed.setValue(100)
        self.audio_speed.setToolTip("Control audio speed")
        self.audio_speed.valueChanged.connect(self.update_audio_speed)

        self.options.addWidget(self.replay_btn)
        self.options.addWidget(self.play_tts_btn)
        self.options.addWidget(self.audio_speed)

        vbox.addLayout(self.options)
        vbox.addWidget(self.web)

        self.web.setHtml(html)
        self.resize(1024, 720)

        self.setLayout(vbox)

        if app_settings.value("sound-effects", "False") == "True":
            play(get_sound(pronunciation_score))

    def replay_voice(self):
        self.update_audio_speed()
        play(AnkiPA.RECORDED)


    def replay_tts(self):
        self.update_audio_speed()
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

    def update_audio_speed(self):
        set_audio_speed(self.audio_speed.value() / 100)


class AnkiPADialog(QDialog):
    def __init__(self, *args, **kwargs):
        super(AnkiPADialog, self).__init__(*args, **kwargs)

        self.setWindowTitle("AnkiPA Options")

        self.base_layout = QVBoxLayout()

        # AnkiPA label
        self.ankipa_label = QLabel("AnkiPA Options")
        self.ankipa_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ankipa_label.setFont(SettingsDialog._FONT_HEADER)

        # Settings
        self.settings_btn = QPushButton("Settings", self)
        self.settings_btn.clicked.connect(self.settings_dialog)
        self.settings_btn.setIcon(
            QIcon(os.path.join(addon, f"icons{os.sep}settings.png"))
        )
        self.settings_btn.setIconSize(QSize(32, 32))

        # Statistics
        self.statistics_btn = QPushButton("Statistics", self)
        self.statistics_btn.clicked.connect(self.statistics_dialog)
        self.statistics_btn.setIcon(
            QIcon(os.path.join(addon, f"icons{os.sep}statistics.png"))
        )
        self.statistics_btn.setIconSize(QSize(32, 32))

        # About
        self.about_btn = QPushButton("About", self)
        self.about_btn.clicked.connect(self.about_dialog)
        self.about_btn.setIcon(QIcon(os.path.join(addon, f"icons{os.sep}about.png")))
        self.about_btn.setIconSize(QSize(32, 32))

        self.base_layout.addWidget(self.ankipa_label)
        self.base_layout.addWidget(self.settings_btn)
        self.base_layout.addWidget(self.statistics_btn)
        self.base_layout.addWidget(self.about_btn)

        self.setLayout(self.base_layout)

        self.setMinimumWidth(180)

    def settings_dialog(self):
        SettingsDialog(mw).show()

    def statistics_dialog(self):
        html = ""
        with open(os.path.join(addon, f"chart{os.sep}chart.html"), "r") as fp:
            for line in fp.readlines():
                html += line

        # Generate statistics data
        stats_data = stats.get_stats_data()
        days = sorted(
            list(stats_data.keys()),
            key=lambda d: time.strptime(d, "%d/%m/%Y"),
            reverse=True,
        )
        ndays = len(days)
        days = days[: 31 if ndays > 31 else ndays]
        days = days[::-1]

        pronunciation = []
        accuracy = []
        fluency = []
        pron_time = []
        pron_words = []
        assessments = []

        for day in days:
            pronunciation.append(stats_data[day]["avg_pronunciation"])
            accuracy.append(stats_data[day]["avg_accuracy"])
            fluency.append(stats_data[day]["avg_fluency"])
            pron_time.append(stats_data[day]["pronunciation_time"])
            pron_words.append(stats_data[day]["words"])
            assessments.append(stats_data[day]["assessments"])

        html = (
            html.replace("['DAYS']", str(days))
            .replace("['PRONUNCIATION']", str(pronunciation))
            .replace("['ACCURACY']", str(accuracy))
            .replace("['FLUENCY']", str(fluency))
            .replace("['PRON_TIME']", str(pron_time))
            .replace("['PRON_WORDS']", str(pron_words))
            .replace("['ASSESSMENTS']", str(assessments))
        )

        StatisticsDialog(html).show()

    def about_dialog(self):
        dialog = QDialog(mw)
        dialog.setWindowTitle("About AnkiPA")
        dialog.setFixedSize(750, 500)

        icon = QPixmap(os.path.join(addon, f"icons{os.sep}ankipa.png"))
        icon_label = QLabel()
        icon_label.setFixedSize(128, 128)
        icon_label.setPixmap(icon)
        icon_label.setScaledContents(True)

        font_header = QFont()
        font_header.setPointSize(24)
        font_header.setBold(True)

        font_body = QFont()
        font_body.setPointSize(12)

        ankipa_label = QLabel("AnkiPA - Pronunciation Assessment")
        ankipa_label.setFont(font_header)
        ankipa_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        hbox = QHBoxLayout()
        hbox.addWidget(icon_label)
        hbox.addWidget(ankipa_label)

        about = (
            "AnkiPA is an addon that helps you practice your pronunciation. Your voice is recorded "
            "and compared to the reference text to evaluate the pronunciation. Within seconds you "
            "receive an overview containing accuracy, fluency and pronunciation score and which words "
            "you pronounced correctly and what mistakes you commited.\n\n"
            "It uses Microsoft Azure Speech services to provide the assessment results. Your voice "
            "is sent to their servers and if you play TTS the audio data is retrieved. Besides that AnkiPA "
            "doesn't make any other internet connection. It's recommended to create your own API key in "
            "the closest available region to faster evaluations.\n\n"
            "If you find a bug or need help reach me out by opening an issue on GitHub."
        )
        about_edit = QTextEdit()
        about_edit.setPlainText(about)
        about_edit.setReadOnly(True)
        about_edit.setFont(font_body)

        buttons = QDialogButtonBox() 
        contact_btn = QPushButton("Contact author")
        contact_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://github.com/warleysr/ankipa"))
        )
        buttons.addButton("Ok", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(contact_btn, QDialogButtonBox.ButtonRole.ActionRole) 
        buttons.accepted.connect(dialog.accept)      

        layout = QVBoxLayout()
        layout.addLayout(hbox)
        layout.addWidget(about_edit)
        layout.addWidget(buttons)
        layout.setAlignment(buttons, Qt.AlignmentFlag.AlignCenter)

        dialog.setLayout(layout)

        dialog.show()


class StatisticsDialog(QDialog):
    def __init__(self, html: str):
        super().__init__(mw)
        self.setWindowTitle("AnkiPA Statistics")

        vbox = QVBoxLayout()
        self.web = AnkiWebView(self)

        vbox.addWidget(self.web)

        self.web.stdHtml(html)
        self.resize(1024, 720)

        self.setLayout(vbox)


class SettingsDialog(QDialog):
    _FONT_HEADER = QFont()
    _FONT_HEADER.setPointSize(12)
    _FONT_HEADER.setBold(True)

    def __init__(self, *args, **kwargs):
        super(SettingsDialog, self).__init__(*args, **kwargs)
        mw.garbage_collect_on_dialog_finish(self)
        self.setWindowTitle("AnkiPA Settings")

        self.base_layout = QVBoxLayout()

        self.button_box = QDialogButtonBox()
        self.button_box.addButton("Ok", QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

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
        langs = sorted(list(data["languages"].keys()))
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
        self.base_layout.addWidget(self.button_box)

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
        shortcut.setKey(QKeySequence(f"Ctrl+{curr_shortcut}"))

        app_settings.setValue(
            "sound-effects", str(self.sound_effects_check.isChecked())
        )

        super(SettingsDialog, self).accept()

    def reject(self):
        super(SettingsDialog, self).reject()


def main_dialog():
    AnkiPADialog(mw).show()


def start_assessment():
    if mw.reviewer.card:
        AnkiPA.test_pronunciation()
    else:
        main_dialog()


def on_webview_will_set_content(web_content: WebContent, _):
    addon_package = mw.addonManager.addonFromModule(__name__)
    web_content.js.append(f"/_addons/{addon_package}/chart/chart.js")


mw.addonManager.setWebExports(__name__, r"chart/.*(css|js)")
gui_hooks.webview_will_set_content.append(on_webview_will_set_content)

gui_hooks.av_player_did_end_playing.append(lambda _: set_audio_speed(1.0))

ankipa_action = QAction("AnkiPA...", mw)
ankipa_action.triggered.connect(main_dialog)
mw.form.menuTools.addAction(ankipa_action)

curr_shortcut = app_settings.value("shortcut", defaultValue="W")
shortcut = QShortcut(QKeySequence(f"Ctrl+{curr_shortcut}"), mw)

start_action = QAction("Start pronunciation assessment", mw)
start_action.triggered.connect(AnkiPA.test_pronunciation)

mw.addAction(start_action)
shortcut.activated.connect(start_assessment)
