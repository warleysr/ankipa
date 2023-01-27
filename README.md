# AnkiPA
<img src="https://i.imgur.com/yi7tN9j.png" width="250px" align="right">

This project is an Anki addon for pronunciation assessment. You can record your own voice when studying a flashcard and get an overview of what your pronunciation looks like!

## How it works

When you are reviewing a flashcard and press `Ctrl + W` AnkiPA starts to record your voice and then send the data to Azure Speech Services to get an pronunciation assessment based on their service.

For Mac the command will be `Cmd + W`. It can be changed in the settings.

## Installation

Open Anki and go to **Tools** -> **Add-ons** -> **Get Add-ons...** -> Place the code below and then click OK.

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;`86363097`

See more details at <a href="https://ankiweb.net/shared/info/86363097">AnkiWeb page</a>. You can also clone this repository to your Anki addons folder if you prefer. 


## Configuring your API key

To use this addon you will need an Azure API key. You can create an free account at <a href="https://portal.azure.com">Azure Portal</a>. After logging into your account, go to **Speech services** and create a new resource, selecting the **region** of the endpoint. Once created the resource you will be able to find your API **key**.

With that informations you need to open your Anki and go to **Tools** and then **AnkiPA Settings**. A window will appear and there you place your key and select the region and also choose the language that you will be evaluating your pronunciation.

<img src="https://i.imgur.com/DAE57WI.png" width="250px">

## Settings
In the settings besides the API configs you will find some other options:
- **Card fields:** a comma separated list of the fields to be used as text source for evaluating the pronunciation, prioritazed by order. If none of them be found the first one will be used. The field names are case sensitive.
- **Timeout:** how many seconds a pronunciation assessment can last
- **Phoneme system:** only for en-US/GB, it defines how the syllables will be shown
- **Shortcut:** your preferred shortcut to start recording your voice
- **Enable sound effect:** sounds based on pronunciation score

## Testing key
If you're just taking a look and don't want to have the work of creating your own key, try using this:

**Key**: `55e82f46c625437c94fee3d3eea655b8`

**Region**: `centralus`

## Supported languages
Azure Pronunciation Assessment supports 9 languages with different accents for English, Spanish and French. They are:
- English (United States)
- English (United Kingdom)
- English (Australia)
- English (India)
- Spanish (Spain)
- Spanish (Mexico)
- French (France)
- French (Canada)
- German (Germany)
- Norwegian (Bokmål, Norway)
- Japanese (Japan)
- Chinese (Mandarin, Simplified)
- Vietnamese (Vietnam)
- Arabic (Saudi Arabia)


## Results

After clicking on `Save` button, in few seconds a popup screen will appear showing details about your pornunciation. It shows the percentage scores for accuracy, fluency and overall pronunciation , the amount of errors you committed and what words your pronounced correctly. When you hover your mouse in the words you can see details about the phonemes. The result screen looks like this:

<img src="https://i.imgur.com/EFCk9Vs.png">
