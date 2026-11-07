# AnkiPA
<img src="https://i.imgur.com/yi7tN9j.png" width="250px" align="right">

This project is an Anki addon for pronunciation assessment. You can record your own voice when studying a flashcard and get an overview of what your pronunciation looks like!

## How it works

When you are reviewing a flashcard and press `Ctrl + W` AnkiPA starts to record your voice and then send the data to Azure Speech Services to get an pronunciation assessment based on their service.

For Mac the command will be `Cmd + W`. It can be changed in the settings.

### Trigger from Card Template (Embedded Button)

You can trigger AnkiPA directly by embedding a button in your card template (Front or Back):

```html
<!-- Option 1: Automatic click binding using class or data attribute -->
<button type="button" class="ankipa-start">🎙️ Pronounce</button>

<!-- Option 2: Using the JavaScript bridge function -->
<button type="button" onclick="ankipaStart()">🎙️ Pronounce</button>

<!-- Option 3: Using Anki's pycmd bridge -->
<button type="button" onclick="pycmd('ankipa:start')">🎙️ Pronounce</button>
```

#### Multiple Entries / Passing Custom Text or Selectors

If your card contains multiple entries (e.g., a Word and an example Sentence), you can pass the specific field or selector to evaluate:

```html
<!-- 1. Pass field content directly via JavaScript -->
<div class="word-section">
  <span>{{Word}}</span>
  <button type="button" onclick="ankipaStart('{{Word}}')">🎙️ Word</button>
</div>

<div class="sentence-section">
  <p>{{Sentence}}</p>
  <button type="button" onclick="ankipaStart('{{Sentence}}')">🎙️ Sentence</button>
</div>

<!-- 2. Pass field content using data-ankipa-text without writing JS -->
<button type="button" class="ankipa-start" data-ankipa-text="{{Word}}">🎙️ Word</button>
<button type="button" class="ankipa-start" data-ankipa-text="{{Sentence}}">🎙️ Sentence</button>

<!-- 3. Pass a CSS selector of the target element -->
<button type="button" onclick="ankipaStart('.sentence-section p')">🎙️ Sentence</button>
```

## Installation

Open Anki and go to **Tools** -> **Add-ons** -> **Get Add-ons...** -> Place the code below and then click OK.

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`86363097`

See more details at <a href="https://ankiweb.net/shared/info/86363097">AnkiWeb page</a>. You can also clone this repository to your Anki addons folder if you prefer. 


## Configuring your API key

To use this addon you will need an Azure API key. You can create an free account at <a href="https://portal.azure.com">Azure Portal</a>. After logging into your account, go to **Speech services** and create a new resource, selecting the **region** of the endpoint. Once created the resource you will be able to find your API **key**.

With that informations you need to open your Anki and go to **Tools** and then **AnkiPA Settings**. A window will appear and there you place your key and select the region and also choose the language that you will be evaluating your pronunciation.

&ensp;&ensp;&ensp;&ensp;&ensp;&ensp;&ensp; <img src="https://i.imgur.com/kPbw66L.png">

## Settings
In the settings besides the API configs you will find some other options:
- **Card fields:** a comma separated list of the fields to be used as text source for evaluating the pronunciation, prioritazed by order. If none of them be found the first one will be used. The field names are case sensitive.
- **Timeout:** how many seconds a pronunciation assessment can last
- **Phoneme system:** only for en-US/GB, it defines how the syllables will be shown
- **Shortcut:** your preferred shortcut to start recording your voice
- **Enable sound effect:** sounds based on pronunciation score
- **Audio trimming method:** Choose how your recorded audio is trimmed before uploading to Azure:
  - **Disabled:** Sends the full recorded audio directly to Azure (default behavior)
  - **Visual dialog (interactive trim):** Displays a visual audio waveform dialog after recording so you can preview, listen to the selected snippet, remove silence with auto-trim, and send only the desired audio segment to Azure
  - **Auto-trim silence (direct upload):** Automatically strips leading and trailing silence and uploads directly to Azure without showing the dialog, saving costs and review time
- **Text extraction method:** Choose how AnkiPA extracts text from your cards:
  - **Auto (DOM first, then fields):** Tries to extract visible text from the card DOM first, falls back to field extraction
  - **DOM only:** Only uses DOM extraction (useful for cards with dynamic/rotating content)
  - **Fields only:** Traditional field-based extraction (default behavior)
- **CSS selectors for DOM extraction:** Comma-separated CSS selectors to find text in the card DOM. Useful for custom card templates. Default: `#sentences-inner .fr, .sentence.fr, .fr.sentence, [data-sentence], .example-sentence`

## Supported languages
AnkiPA relies on <b>Azure Pronunciation Assessment</b>, which supports multiple languages and different accents for English, Spanish and French.   

The addon update the supported languages automatically, and the newly added ones will appear on the options when Microsoft releases them.

You can check the current supported languages <a href="https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=pronunciation-assessment">here</a>.

Also it has an updater that automatically will add new languages options when it's made available by Microsoft.

&ensp;&ensp;&ensp;&ensp;&ensp;&ensp;&ensp; <img src="https://i.imgur.com/fsj1yEC.png">



## Results

After clicking on `Save` button, in few seconds a popup screen will appear showing details about your pronunciation. It shows the percentage scores for accuracy, fluency and overall pronunciation , the amount of errors you committed and what words your pronounced correctly. When you hover your mouse in the words you can see details about the phonemes. The result screen looks like this:

<img src="https://i.imgur.com/EFCk9Vs.png">
