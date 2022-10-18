# AnkiPA
This project is an Anki addon for pronunciation assessment. You can record your own voice when studying a flashcard and get an overview of what your pronunciation looks like!

## How it works

When you are reviewing a flashcard and press `Ctrl + W` AnkiPA starts to record your voice and then send the data to Azure Speech Services to get an pronunciation assessment based on their 

## Installation

You need to clone this repository to  your Anki addons folder. ...

## Configuring your API key

To use this addon you will need an Azure API key. You can create an free account at <a href="https://portal.azure.com">Azure Portal</a>. After logging into your account, go to **Speech services** and create a new resource, selecting the **region** of the endpoint. Once created the resource you will be able to find your API **key**.

With that informations you need to open your Anki and go to **Tools** and then **AnkiPA Settings**. A window will appear and there you place your key and select the region and also choose the language that you will be evaluating your pronunciation.

## Supported languages
Azure Pronunciation Assessment supports 5 languages with 3 different accents for English. They are:
- English (United States)
- English (United Kingdom)
- English (Australia)
- Chinese (Mandarin, Simplified)
- French (France)
- German (Germany)
- Spanish (Spain)
