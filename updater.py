import requests
from bs4 import BeautifulSoup


def update_available_languages(current_data: dict):
    url = (
        "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/"
        "language-support?tabs=pronunciation-assessment"
    )
    response = requests.get(url)

    if response.status_code != 200:
        return

    doc = BeautifulSoup(response.content, "html.parser")

    section = doc.find("section", {"id": "tabpanel_1_pronunciation-assessment"})
    if section is None:
        return
    tts_section = doc.find("section", {"id": "tabpanel_1_tts"})

    table = section.find_next("table").find_next("tbody")
    tts_table = tts_section.find_next("table").find_next("tbody")
    trs = table.find_all("tr")

    new_languages = []
    for tr in trs:
        tds = tr.find_all("td")
        lang_name, lang_code = tds[0].text, tds[1].find_next("code").text
        if lang_name in current_data:
            continue

        tts_voice = None
        for tts_tr in tts_table.find_all("tr"):
            tts_tds = tts_tr.find_all("td")
            if tts_tds[0].text != lang_code:
                continue
            voices = tts_tds[2].text.split(")")
            tts_voice = next((voice for voice in voices if "Male" in voice), None)
            tts_voice = tts_voice.split("(")[0].strip()

        if not tts_voice:
            continue
        current_data[lang_name] = [lang_code, tts_voice]
        new_languages.append(lang_name)

    return new_languages
