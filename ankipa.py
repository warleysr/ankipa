from aqt.sound import record_audio
from aqt import mw
import threading
import json
import re
import os

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


class AnkiPA:

    REFTEXT = None
    RECORDED = None
    TTS_GEN = None
    LAST_TTS = None
    RESULT = None

    @classmethod
    def test_pronunciation(cls):
        from . import settings_dialog, app_settings

        if not mw.reviewer.card:
            settings_dialog()
            return

        idx = int(app_settings.value("field-index", defaultValue=0))
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

        from . import (
            app_settings,
            data,
            html_template,
            showInfo,
            get_color,
            ResultsDialog,
        )
        from .pronunciation import pron_assess

        region = app_settings.value("region")
        language = app_settings.value("language")
        key = app_settings.value("key")
        if not all((region, language, key)):
            showInfo("Please configure your Azure service properly.")
            return

        # Perform pronunciation assessment
        lang = data["languages"][language][0]
        phoneme_system = app_settings.value("phoneme-system", defaultValue="IPA")
        timeout = int(app_settings.value("timeout", defaultValue=5))

        t = threading.Thread(
            target=pron_assess,
            args=(
                region,
                lang,
                key,
                cls.REFTEXT,
                recorded_voice,
                phoneme_system,
                timeout,
            ),
        )
        t.start()
        t.join(timeout)

        if cls.RESULT is None or t.is_alive():
            cls.RESULT = None
            showInfo("There was a network error recognizing your speech. Try again.")
            return

        if cls.RESULT["RecognitionStatus"] != "Success":
            from . import addon

            # Save file for debug
            with open(os.path.join(addon, "debug.json"), "w+") as fp:
                data = {}
                data["language"] = lang
                data["region"] = region
                data["text"] = cls.REFTEXT
                data["response"] = cls.RESULT
                json.dump(data, fp, indent=4)

            showInfo(
                "There was a service error recognizing your speech. "
                + "Check <b>debug.json</b> in your addon's folder. "
                + "Contact me in GitHub if you need help: "
                + "<a href='github.com/warleysr'>github.com/warleysr</a>"
            )
            return

        scores = cls.RESULT["NBest"][0]
        accuracy = scores["AccuracyScore"]
        fluency = scores["FluencyScore"]
        pronunciation = scores["PronScore"]

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

        cls.RESULT = None

        widget = ResultsDialog(html, pronunciation)
        widget.setWindowModality(False)
        widget.show()
