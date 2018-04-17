import unittest
import os
import time
import shutil
import sys
import unittest.mock
import copy
import random

from word_level_downloader import *

class mock_urllib_request_urlopen():
    '''Mock used to speed up tests depending on internet'''
    responses = {}
    original_function = urllib.request.urlopen
    def __init__(self,response=None,*args,**kwargs):
        self.overwrite_response = response
        if not os.path.exists('cache'):
            os.mkdir('cache')
        super().__init__(*args,**kwargs)
    def __call__(self,url=None):
        return self.urlopen(url)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def open_file(self,url,mode):
        return open(os.path.join(b'cache',urllib.request.base64.b64encode(url.encode('utf-8'))+b'.txt'), mode)
    def urlopen(self,url):
        if url not in self.__class__.responses:
            try:
                with self.open_file(url,'rb') as file:
                    self.__class__.responses[url] = file.read()
            except IOError:
                try:
                    with self.__class__.original_function(url) as file:
                        self.__class__.responses[url] = file.read()
                except IOError:
                    self.__class__.responses[url] = b''
                try:
                    with self.open_file(url,'wb') as file:
                        file.write(self.__class__.responses[url])
                except IOError:
                    pass
        self.response = self.__class__.responses[url]
        if not self.response:
            raise IOError('Sample mock IOError')
        return self
    def read(self):
        if self.overwrite_response:
            if isinstance(self.overwrite_response, Exception):
                raise self.overwrite_response
            else:
                return self.overwrite_response
        if self.response:
            return self.response
        else:
            raise AttributeError('Mock attribute error - read() called after unsuccessful urlopen')

class TestStdout:
    def __init__(self,analyzer,show_output=True):
        self.last_number=0
        self.analyzer=analyzer
        self.show_output=True
    def __enter__(self):
        self.original_stdout=sys.stdout
        sys.stdout=self
    def __exit__(self,*args):
        sys.stdout=self.original_stdout
    def write(self, text):
        if self.show_output:
            self.original_stdout.write(text)
        self.analyzer.write(text)

class LevelsDownloaderTestWithMockUrlopen(unittest.TestCase):
    def setUp(self):
        self.downloader=LevelsDownloader()
        self.downloader.urlopen_function = mock_urllib_request_urlopen()

class requirement_tests(LevelsDownloaderTestWithMockUrlopen):
    def test_basic_download(self):
        self.downloader.words=[('car')]
        expected=[('car','A1')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_additional_download(self):
        self.downloader.words=[('car')]
        self.downloader.process_words()
        self.downloader.words=[('need')]
        expected=[('car','A1'), ('need','A1')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_undefined_download(self):
        self.downloader.words=[('truncate')]
        expected=[('truncate','UNDEFINED')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_phrasal_verb_download(self):
        self.downloader.words=[('go-away')]
        expected=[('go away','B1')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_download_suggested(self):
        self.downloader.options['do_not_change_words'] = False
        self.downloader.words=[('needing')]
        expected=[('need','A1')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_sorting_order(self):
        self.downloader.words=['keyboard','key','perplex','ABCD123','get-away']
        expected=[('key','A1'),
        ('keyboard','A2'),
        ('get away','B2'),
        ('perplex','UNDEFINED'),
        ('abcd123','UNFOUND'),] 
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_taking_the_lowest_level_on_the_page(self):
        self.downloader.words=[('form')]
        expected=[('form','A2')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_to_file(self):
        test_file='test_file.txt'
        self.downloader.words=['coffee','keyboard','get-away']
        expected='A1 coffee\nA2 keyboard\nB2 get away\n'
        self.downloader.process_words()
        self.downloader.save_words_to_file(test_file)
        with open(test_file,'r') as f:
            content=f.read()
        os.remove(test_file)
        self.assertEqual(content,expected)
    def test_not_existing_download(self):
        self.downloader.words=[('ABCD123')]
        expected=[('abcd123','UNFOUND')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_incorrect_webpage_code(self):
        self.downloader.urlopen_function = mock_urllib_request_urlopen(b'<head> >/')
        self.downloader.words=[('car')]
        expected=[('car','UNFOUND')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_stdout(self):

        class analyzer:
            def __init__(self,TestCase):
                self.last_number=0.0
                self.TestCase=TestCase
            def write(self,text):
                match=re.search(r'([\d\.]+)%',text)
                if match:
                    number=float(match.group(1))
                    self.TestCase.assertGreaterEqual(number,self.last_number,msg='Last number is higher than the current one!')
                    self.TestCase.assertLessEqual(number,100.0,msg='The number is higher than 100%')
                    self.last_number=number

        with TestStdout(analyzer(self)):
            self.downloader.words = ['keyboard','key','perplex','ABCD123','get-away']
            self.downloader.options['silent_mode'] = False
            self.downloader.process_words()
    def test_options_update_aditional_option(self):
        self.downloader=LevelsDownloader(random_test_option=True)
        self.assertIn('random_test_option',self.downloader.options)
        self.assertEqual(True,self.downloader.options['random_test_option'])
    def test_options_update_not_overwritting_option_given_before_with_defaults(self):
        self.downloader=LevelsDownloader(max_number_of_words_in_phrasal_verb=999)
        self.assertEqual(999,self.downloader.options['max_number_of_words_in_phrasal_verb'])
    def test_starting_without_configuration_available(self):
        self.downloader.options['dump_config']=False
        self.downloader._delete_dumped()
        del(self.downloader)
        self.downloader = LevelsDownloader()
        self.assertIn('silent_mode',self.downloader.options)
        self.assertIn('words_extraction_from_source_file',self.downloader.options)
        self.assertIn('words_extraction_from_xml',self.downloader.options)
    def test_saving_and_restoring_configuration(self):
        self.downloader.options['dump_config']=True
        self.downloader._delete_dumped()
        self.downloader.options['test option']='test'
        del(self.downloader)
        self.downloader = LevelsDownloader()
        self.assertIn('test option',self.downloader.options)
        self.assertEqual('test',self.downloader.options['test option'])
    def test_many_phrasal_verbs_True(self):
        self.downloader.options['many_phrasal_verbs'] = True
        self.downloader.options['max_number_of_words_in_phrasal_verb'] = 3
        self.downloader.read(io.StringIO('get into sth'))
        expected=[('get','A1'), ('get into sth','C1')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_many_phrasal_verbs_False(self):
        self.downloader.options['many_phrasal_verbs'] = False
        self.downloader.options['max_number_of_words_in_phrasal_verb'] = 3
        self.downloader.read(io.StringIO('get into sth'))
        expected=[('get into sth','C1')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_max_number_of_words_in_phrasal_verb_6(self):
        self.downloader.options['many_phrasal_verbs'] = False
        self.downloader.options['max_number_of_words_in_phrasal_verb'] = 6
        self.downloader.read(io.StringIO('give a dog a bad name'))
        expected=[('give a dog a bad name','UNDEFINED')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_max_number_of_words_in_phrasal_verb_1(self):
        self.downloader.options['many_phrasal_verbs'] = True
        self.downloader.options['max_number_of_words_in_phrasal_verb'] = 1
        self.downloader.read(io.StringIO('give a dog a bad name'))
        expected=[('give','A1')]
        self.downloader.process_words()
        self.assertEqual(self.downloader.words_and_levels,expected)
    def test_http_client_IncompleteRead(self):
        import http
        self.downloader.urlopen_function = mock_urllib_request_urlopen(http.client.IncompleteRead(''))
        self.downloader.words=[('car')]
        self.downloader.process_words()
    def test_many_words(self):
        n = 5000 #a number of words which can be said to be high
        self.downloader.words=[*(random.random() > 0.95 and 'car' or 'abcd123' for i in range(0,n))] #some quick "not founds" and some which require processing
        self.downloader.process_words()
    # def test_many_threads(self):
    #     n = 1500 #a number of threads which can be said to be high
    #     self.downloader.options['max_number_of_threads'] = n
    #     self.downloader.words=[*(random.random() > 0.95 and 'car' or 'abcd123' for i in range(0,n))] #some quick "not founds" and some which require processing
    #     self.downloader.process_words()

# class performance_test(unittest.TestCase):
#     def setUp(self):
#         self.downloader=LevelsDownloader()
#         self.downloader.words = ['time',
#         'person',
#         'year',
#         'way',
#         'day',
#         'thing',
#         'man',
#         'world',
#         'life',
#         'hand',
#         'part',
#         'child',
#         'eye',
#         'woman',
#         'place',
#         'work',
#         'week',
#         'case',
#         'point',
#         'government',
#         'company',
#         'number',
#         'group',
#         'problem',
#         'fact']
#     def _tic(self):
#         self._time=time.time()
#     def _toc(self,info=''):
#         ret = time.time()-self._time
#         print('%s. Time elapsed: {:.4}'.format(ret) % info)
#         return ret
#     def _empty_cache(self):
#         shutil.rmtree('cache')
#         os.mkdir('cache')
#     def test_the_whole(self):
#         self.downloader.options['use_cache']=False
#         self._tic()
#         dump=self.downloader.process_words()
#         self._toc('Test with network')
#     def test_without_the_network(self):
#         self.downloader.options['use_cache']=True
#         dump=self.downloader.process_words()
#         self.setUp()
#         self.downloader.options['use_cache']=True
#         self._tic()
#         dump=self.downloader.process_words()
#         self._toc('Test without network')

if __name__ == '__main__':
    unittest.main()