"""
word downloader
"""

import re
import sys
import os
import threading
import pdb
import urllib.request
import urllib.parse
import lxml.html
import getopt
import functools
import json
import multiprocessing.dummy
import io

class LevelsDownloaderBase:
    def __init__(self,**kwargs):
        self.words=set() #place to store words which are to be processed after calling the process_words method
        self.words_and_levels=[] #place to store words and levels which are a result of calling the process_words method
        self.lock=threading.Lock()
        self.urlopen_function = urllib.request.urlopen

        self.__default_options_for_LevelsDownloaderBase()
        self.update_options(kwargs)             

        self.get_words_from_xml = functools.partial(
            self._parse_with_xpath_and_regexp,
            xpath=self.options['words_extraction_from_xml']['xpath'],
            regexp_compiled_pattern=re.compile(self.options['words_extraction_from_xml']['regexp'],
            flags=re.VERBOSE))
        self.get_levels_from_xml = functools.partial(
            self._parse_with_xpath_and_regexp,
            xpath=self.options['levels_extraction_from_xml']['xpath'],
            regexp_compiled_pattern=re.compile(self.options['levels_extraction_from_xml']['regexp'],
            flags=re.VERBOSE))
        self.get_source_link = functools.partial(re.sub,
            self.options['link_building']['regexp'],
            self.options['link_building']['repl'],
            flags=re.VERBOSE)
        self.words_regexp_pattern = re.compile(self.options['words_extraction_from_source_file']['prefix']+\
            self.options['max_number_of_words_in_phrasal_verb']*self.options['words_extraction_from_source_file']['repeated_part'],
            flags=re.VERBOSE)
    def __del__(self,**kwargs):
        pass
    def update_options(self,dictionary,options_allowed_to_be_changed=set()):
        if not hasattr(self,'options'):
            self.options=dict()
        self.options.update({
            key:value for key, value in dictionary.items()
            if (key in options_allowed_to_be_changed or not options_allowed_to_be_changed)
            #and key not in self.options
            })
    def __default_options_for_LevelsDownloaderBase(self):
        """restores the default options"""
        self.update_options ({
            #data to build self.words_regexp_pattern
            'words_extraction_from_source_file':{
                    'prefix':r'''
                        ^\W* #any number of not word-like characters at the beginning of a line
                        ([^\W\d\-]+\b) #followed by word characters without digits, which are treated as the first word
                    ''',
                    'repeated_part':r'''
                        (?:\s+[^\w\s].*)? #if followed by a space and a non-word like character then ignore everything right from this point
                        \W*([^\W\d\-\#\!\*]+\b)? #after any number of non-word like characters catch a group of resembling word-like characters as another word
                    ''' 
                    },
            #data to build the self.get_words_from_xml function
            'words_extraction_from_xml':{'xpath':r'head/title/text()', 'regexp':r'^\s*([\w\s]+)\s+(?:[Cc]lause\s+)?(?:[Mm]eaning|[De]efinition)\s+in\s+the\s+[Cc]ambridge\s+[Ee]nglish\s+[Dd]ictionary'},
            #data to build the self.get_levels_from_xml function
            'levels_extraction_from_xml':{'xpath':r"//span[@class='def-info']/*/text()",'regexp':r'[A-C][1-2]'},
            #data to build the self.get_source_link function
            'link_building':{'regexp':r'(.*)', 'repl':r'https://dictionary.cambridge.org/us/search/english/direct/?q=\1'},
            #maximal number of words in a prasal verb, for example from "do away with sb" string  and 'max_number_of_words_in_phrasal_verb'=2, there will be 2 results: "do" and "do away"
            'max_number_of_words_in_phrasal_verb':3,
            #maximal number of threads the app can spawn into existence to download words (tip: set to 1 for most debugging purposes)
            'max_number_of_threads':50,
            #whether to follow dictionaries suggestions, for example if set then "releases" should be changed to "release"
            'do_not_change_words':False,
            #whether to download level of all phrasal verbs or only the longest allowed one, if set then for the "do away" string, the "do" and "do away" levels will be downloaded
            'many_phrasal_verbs':False,
            #the characters which are used in the urls of a dictionary to denote phrasal verbs
            'phrasal_verb_separator':'-',
            #whether to print any output
            'silent_mode':False})
    @staticmethod
    def _parse_with_xpath_and_regexp(lxml_object, xpath, regexp_compiled_pattern=None):
        """Takes an lxml object, xpath and regular expression,\
        applies regexp to the results of xpath and returns the result\
        xpath must return text not anything else (use text())"""
        ret = []
        for text in lxml_object.xpath(xpath):
            if regexp_compiled_pattern:
                match = regexp_compiled_pattern.findall(text)
                if match:
                    ret.extend(match)
            else:
                ret.extend(text)
        return ret
    def _get_level_from_page_text(self,suggested_word,text):
        """Takes a webpage text and returns the main form of the word in it
        and the lowest found level"""
        processed_suggested_word = ' '.join(suggested_word.split(self.options['phrasal_verb_separator'])) #removing phrasal verb separator
        if text == '':
            return processed_suggested_word, 'UNFOUND'
        lxml_page = lxml.html.fromstring(text)
        words = self.get_words_from_xml(lxml_page)
        levels = self.get_levels_from_xml(lxml_page)
        if words:
            word = words[0]
            if word != processed_suggested_word and self.options['do_not_change_words']:
                word = processed_suggested_word
                level = 'UNFOUND'
            elif levels:
                level = sorted(levels)[0]
            else:
                level = 'UNDEFINED'
        else:
            word = processed_suggested_word
            level = 'UNFOUND'    
        return word, level
    def _get_page_from_dictionary(self, word):
        """Takes a page for a specific word from the dictionary"""
        page = ''
        try:
            link = self.get_source_link(urllib.parse.quote(word.lower(),encoding='utf-8'))
            with self.urlopen_function(link) as response:
                page = response.read().decode('utf-8')
        except (IOError, urllib.request.http.client.IncompleteRead):
            pass
        return word, page
    def __get_word_and_level(self, word):
        """Gets a main form of a word and level for a given word, stores it in the self.words_and_levels"""
        word, level = self._get_level_from_page_text(*self._get_page_from_dictionary(word))
        self.words_and_levels.append((word.lower(), level))
    def process_words(self):
        """Returns a list of tuples containing words and their levels sorted by their levels"""
        #initiating the threads
        #print('Min:%s' % min(self.options['max_number_of_threads'],len(self.words)))
        pool = multiprocessing.dummy.Pool(
            min(self.options['max_number_of_threads'],len(self.words)) #no more threads than words to be processed
            )
        pool.map(self.__get_word_and_level,self.words)
        pool.close()
        pool.join()
        self.words_and_levels=sorted(list(set(self.words_and_levels)), key=lambda x: (x[1], ' ' in x[0], len(x[0]), x[0]))
    def read(self,file):
        """reads words from a given file-like object"""
        for line in file:
            match = self.words_regexp_pattern.search(line)
            if match:
                text = ''
                for number_of_words in range(1, self.options['max_number_of_words_in_phrasal_verb']+1):
                    try:
                        if match.group(number_of_words):
                            text += ' ' + match.group(number_of_words).lower()
                            if self.options['many_phrasal_verbs']:
                                self.words.add(self.options['phrasal_verb_separator'].join(text.split()))
                    except IndexError:
                        break
                if not self.options['many_phrasal_verbs']:
                    self.words.add(self.options['phrasal_verb_separator'].join(text.split()))

def not_in_silent_mode(func):
    @functools.wraps(func)
    def decorated(self,*args,**kwargs):
        if hasattr(self,'options') and not self.options.get('silent_mode',None):
            return func(self,*args,**kwargs)
    return decorated

class LevelsDownloaderWithFiles(LevelsDownloaderBase):
    @not_in_silent_mode
    def problem_info(self, text='Some kind of problem'):
        print(text)
    def save_words_to_file(self, file_path, encoding='utf-8'):
        """Saves words and levels into a file"""
        try:
            with open(file_path, 'w', encoding=encoding) as file:
                file.writelines(('%s %s\n' % (level, word) for word, level in self.words_and_levels))
        except (IOError, TypeError) as error:
            if __name__ == '__main__':
                self.problem_info('Problem during saving to the file.')
            else:
                raise error
    def read_words_from_file(self, file_path=None, encoding='utf-8'):
        """Reads words from a file"""
        if not file_path:
            return None
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                self.read(file)
        except Exception as error:
            if __name__ == '__main__':
                if isinstance(error, UnicodeDecodeError):
                    self.problem_info('The input file encoding is not utf-8.')
                elif isinstance(error, FileNotFoundError):
                    self.problem_info('The input file does not exist')
                elif isinstance(error, IOError):
                    self.problem_info('Problem openning the file.')
                else:
                    self.problem_info('Unidentified error when openning the file.')
            else:
                raise error  

class LevelsDownloaderWithReporting(LevelsDownloaderBase):
    @not_in_silent_mode
    def __print_info(self,percent):
        print("\r{:.0%} completed...".format(percent),end='')
    def __report_progress(self):
        """Reports progress of the process"""
        number_of_words_to_be_processed=len(self.words)
        number_of_already_processed_words=len(self.words_and_levels)
        while number_of_words_to_be_processed and not self.__exit_event.is_set():
            self.__print_info((len(self.words_and_levels)-number_of_already_processed_words)/(number_of_words_to_be_processed))
            self.__exit_event.wait(0.2)
    def __start_reporting(self):
        self.__exit_event = threading.Event()
        self.reporting = threading.Thread(target=self.__report_progress)
        self.reporting.start()
    def __stop_reporting(self):
        self.__exit_event.set()
        self.reporting.join()
    @not_in_silent_mode
    def present(self):
        if self.words_and_levels:
            print('\rDownloaded words:\n'+'\n'.join(['%s: %s' % (level, word) for word, level in self.words_and_levels]))
    def process_words(self):
        """Returns a list of tuples containing words and their levels sorted by their levels"""
        self.__start_reporting()
        super().process_words()
        self.__stop_reporting()
        self.present()

class LevelsDownloaderLoaderSaver(LevelsDownloaderBase):
    def __init__(self, dump_config=True, config_file='config.json', **kwargs):
        self.load(config_file)
        self.update_options({'config_file':config_file, 'dump_config':dump_config})
        super().__init__(**kwargs)
    def __del__(self,**kwargs):
        if self.options['dump_config']:
            self.dump()
        super().__del__(**kwargs)
    def dump(self):
        try:
            with open(self.options['config_file'],'w') as f:
                json.dump({name:value for name, value in self.options.items() if name not in ('config_file','dump_config')}, f, indent='\t')
        except IOError:
            pass
    def load(self, config_file):
        try:
            with open(config_file, 'r') as f:
                self.update_options(json.load(f))
        except (IOError, json.JSONDecodeError):
            pass
    def _delete_dumped(self):
        if os.path.exists(self.options['config_file']):
            os.remove(self.options['config_file'])
     
class LevelsDownloader(LevelsDownloaderLoaderSaver, LevelsDownloaderWithFiles, LevelsDownloaderWithReporting):
    pass

def program_help():
    print('''The word level downloader app downloads word levels according to \
Common European Framework of Reference for Languages and sorts them for you \
so that you know which of the words you jotted down are most important to learn. \
Phrasal verbs and guessing the correct form of the word are supported. 
Example Usage:
    Getting and printing levels of the mentioned words: word_level_downloader car home coffee
    Getting words from the file and saving them and their downloaded levels into another file: word_level_downloader --input my_list.txt --output: word_levels.txt
    word_level_downloader --silent --fix --many --max 5 --input my_list.txt --output: word_levels.txt car home coffee
        ''')

def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'sfmi:o:t:', ['silent','many','fix','input=', 'output=','threads='])
    except getopt.GetoptError:
        program_help()   
        sys.exit(2)
    else:
        options=dict(opts)
        if options.get('--help',options.get('-h','')):
            program_help()
        input_file=options.get('--input',options.get('-i',''))
        output_file=options.get('--output',options.get('-o','words_and_levels.txt'))
        downloader=LevelsDownloader(
            silent_mode='--silent' in options or '-s' in options,
            do_not_change_words='--fix' in options or '-f' in options,
            many_phrasal_verbs='--many' in options or '-m' in options,
            max_number_of_words_in_phrasal_verb=options.get('--max',options.get('-m','3')).isnumeric() and int(options.get('--max',options.get('-m','3'))) or 3
            )
        downloader.read_words_from_file(input_file)
        downloader.read(io.StringIO('\n'.join(args)))
        downloader.process_words()
        downloader.save_words_to_file(output_file)

if __name__ == '__main__':            
    main()

