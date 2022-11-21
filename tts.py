import requests
import tempfile
import os


class TTS:
    @classmethod
    def gen_tts_audio(cls, region, key, voice_code, text):
        ssml = (
            "<speak version='1.0' xml:lang='en-US'>"
            + f"<voice name='{voice_code}' style='default'>"
            + f"{text}</voice></speak>"
        )

        req = requests.post(
            "https://%s.tts.speech.microsoft.com/cognitiveservices/v1" % region,
            headers={
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
                "Ocp-Apim-Subscription-Key": key,
            },
            data=ssml.encode("utf-8"),
        )

        if req.status_code != 200:
            return None

        tmpdir = tempfile.gettempdir() + os.sep + "ankipa"
        os.makedirs(tmpdir, exist_ok=True)

        _, name = tempfile.mkstemp(suffix=".mp3", dir=tmpdir)

        with open(name, "wb") as fp:
            fp.write(bytearray(req.content))

        return name
