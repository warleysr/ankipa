from aqt.sound import RecordDialog
from aqt import mw
from aqt.qt import Qt
from .stats import *
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
    DIAG = None

    @classmethod
    def test_pronunciation(cls):
        from . import app_settings

        to_read = None
        dom_text_extracted = False
        extraction_method = app_settings.value("extraction-method", defaultValue="auto")

        if extraction_method in ["auto", "dom"]:
            try:
                default_selectors = "#sentences-inner .fr, .sentence.fr, .fr.sentence, [data-sentence], .example-sentence"
                selectors = app_settings.value("dom-selectors", defaultValue=default_selectors)

                mw.reviewer.web.eval(f"window.ankipaSetSelectors ? window.ankipaSetSelectors({json.dumps(selectors)}) : null")

                def on_js_result(result):
                    nonlocal to_read, dom_text_extracted
                    if result and isinstance(result, str) and result.strip():
                        to_read = result.strip()
                        dom_text_extracted = True

                mw.reviewer.web.evalWithCallback(
                    "window.ankipaGetVisibleText ? window.ankipaGetVisibleText() : null",
                    on_js_result
                )

                import time
                max_wait = 0.2
                start = time.time()
                while not dom_text_extracted and (time.time() - start) < max_wait:
                    mw.app.processEvents()
                    time.sleep(0.01)

                if dom_text_extracted:
                    mw.reviewer.web.eval("window.ankipaHighlightText ? window.ankipaHighlightText() : null")
            except:
                pass

        if not to_read and extraction_method != "dom":
            field_names = mw.col.models.fieldNames(mw.reviewer.card.note().model())
            fields: str = app_settings.value("fields")
            field_to_use = field_names[0]

            if fields is not None:
                fields = fields.replace(" ", "").split(",")
                for field in fields:
                    if field in field_names:
                        field_to_use = field
                        break

            to_read = mw.reviewer.card.note()[field_to_use]

            to_read = re.sub(REMOVE_HTML_RE, " ", to_read).replace("&nbsp;", "")

            to_read = re.sub(REMOVE_TAG_RE, "", to_read).strip()

        cls.REFTEXT = to_read

        cid = mw.reviewer.card.id
        if cls.LAST_TTS != cid:
            cls.TTS_GEN = None
            cls.LAST_TTS = cid

        # Record user voice
        cls.DIAG = RecordDialog(mw, mw, cls.after_record)

    @classmethod
    def after_record(cls, recorded_voice):
        if not recorded_voice:
            mw.reviewer.web.eval("window.ankipaRemoveHighlight ? window.ankipaRemoveHighlight() : null")
            return

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
            mw.reviewer.web.eval("window.ankipaRemoveHighlight ? window.ankipaRemoveHighlight() : null")
            return

        elapsed = cls.DIAG._recorder.duration() - 0.5
        elapsed = round(elapsed, 2)

        # Visual audio trimming if enabled
        if app_settings.value("trim-audio", "False") == "True":
            from .trimmer import AudioTrimDialog
            trim_dialog = AudioTrimDialog(recorded_voice, mw, reference_text=cls.REFTEXT)
            if trim_dialog.exec():
                recorded_voice = trim_dialog.get_trimmed_file()
                elapsed = trim_dialog.get_trimmed_duration()
            else:
                mw.reviewer.web.eval("window.ankipaRemoveHighlight ? window.ankipaRemoveHighlight() : null")
                return

        cls.RECORDED = recorded_voice

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
            mw.reviewer.web.eval("window.ankipaRemoveHighlight ? window.ankipaRemoveHighlight() : null")
            showInfo(
                "There was a <b>network error</b> recognizing your speech.<br><br>"
                + "<b>&#x2022;</b> Check if your API credentials are correct.<br><br>"
                + "<b>&#x2022;</b> Verify if your internet connection is working properly.<br><br>"
                + "<b>&#x2022;</b> Try to increase the <b>Timeout</b> parameter in  "
                + "Settings.<br><br>"
                + "<b>&#x2022;</b> Also check Azure Speech services status in your region: "
                + "<a href='https://status.azure.com/en-gb/status'>status.azure.com/en-gb/status</a>"
            )
            return

        if cls.RESULT["RecognitionStatus"] != "Success":
            from . import addon

            mw.reviewer.web.eval("window.ankipaRemoveHighlight ? window.ankipaRemoveHighlight() : null")

            with open(os.path.join(addon, "debug.json"), "w+") as fp:
                data = {}
                data["language"] = lang
                data["region"] = region
                data["text"] = cls.REFTEXT
                data["response"] = cls.RESULT
                json.dump(data, fp, indent=4)

            showInfo(
                "There was a <b>service error</b> recognizing your speech.<br><br>"
                + "<b>&#x2022;</b> Check if your microphone is working well "
                + "and recording clearly.<br><br>"
                + "<b>&#x2022;</b> Make sure the text that you are pronuncing is in the "
                + "correct field and configured language. Take a look at the Settings.<br><br>"
                + "<b>&#x2022;</b> Check <b>debug.json</b> file in your addon's folder "
                + "and contact me on GitHub if you need help: "
                + "<a href='https://github.com/warleysr/ankipa'>github.com/warleysr/ankipa</a>"
            )
            return

        update_stat("assessments", 1)
        update_stat("pronunciation_time", elapsed)

        assessments = get_stat("assessments")

        scores = cls.RESULT["NBest"][0]
        accuracy = scores["AccuracyScore"]
        fluency = scores["FluencyScore"]
        pronunciation = scores["PronScore"]

        update_avg_stat("avg_accuracy", accuracy, assessments)
        update_avg_stat("avg_fluency", fluency, assessments)
        update_avg_stat("avg_pronunciation", pronunciation, assessments)

        update_stat("words", len(scores["Words"]))
        save_stats()

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

        mw.reviewer.web.eval("window.ankipaRemoveHighlight ? window.ankipaRemoveHighlight() : null")

        widget = ResultsDialog(html, pronunciation)
        widget.setWindowModality(Qt.WindowModality.NonModal)
        widget.show()
