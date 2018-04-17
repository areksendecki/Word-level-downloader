# WordLevelDownloader

Downloading word levels according to Common European Framework of Reference for Languages. The word level downloader app downloads word levels according to Common European Framework of Reference for Languages and sorts them for you so that you know which of the words you have jotted down are the most important to learn. Phrasal verbs and guessing the correct forms of words are supported.

## Getting Started

Downloading word levels according to Common European Framework of Reference for Languages. The word level downloader app downloads word levels according to Common European Framework of Reference for Languages and sorts them for you so that you know which of the words you have jotted down are the most important to learn. Phrasal verbs and guessing the correct forms of words are supported.

### Example usage

Getting and printing levels of the mentioned words:

```
word_level_downloader car home coffee
```

Getting words from the file and saving them and their downloaded levels into another file:

```
word_level_downloader --input my_list.txt --output: word_levels.txt
```

More advanced usage:

```
word_level_downloader --silent --fix --many --max 5 --input my_list.txt --output: word_levels.txt car home coffee
```

## Running the tests

Just run tests.py