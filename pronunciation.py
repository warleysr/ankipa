import requests
import base64
from .ankipa import AnkiPA


def pron_assess(region, lang, key, reftext, recorded_voice, phoneme_system, timeout):
    def get_chunk(audio_source, chunk_size=1024):
        while True:
            chunk = audio_source.read(chunk_size)
            if not chunk:
                break
            yield chunk

    referenceText = reftext
    pronAssessmentParamsJson = (
        '{"ReferenceText":"%s","GradingSystem":"HundredMark","Granularity": "Phoneme",'
        % referenceText
        + '"PhonemeAlphabet": "%s", "Dimension":"Comprehensive","EnableMiscue":"True"}'
        % phoneme_system
    )
    pronAssessmentParamsBase64 = base64.b64encode(
        bytes(pronAssessmentParamsJson, "utf-8")
    )
    pronAssessmentParams = str(pronAssessmentParamsBase64, "utf-8")

    url = (
        "https://%s.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=%s"
        % (region, lang)
    )
    headers = {
        "Accept": "application/json;text/xml",
        "Connection": "Keep-Alive",
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        "Ocp-Apim-Subscription-Key": key,
        "Pronunciation-Assessment": pronAssessmentParams,
        "Transfer-Encoding": "chunked",
        "Expect": "100-continue",
    }

    audioFile = open(recorded_voice, "rb")
    response = requests.post(
        url=url, data=get_chunk(audioFile), headers=headers, timeout=timeout
    )
    audioFile.close()

    if response.status_code == 200:
        AnkiPA.RESULT = response.json()
