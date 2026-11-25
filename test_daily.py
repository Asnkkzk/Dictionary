import unittest
from unittest.mock import patch
from worddict import daily
class DailyTests(unittest.TestCase):
    def test_same_day_and_next_day(self):
        settings={'daily_word':{}}
        def save(path,value):
            settings['daily_word'][path.split('.')[-1]]=value
        with patch.object(daily.cfg,'get',return_value=settings), patch.object(daily.cfg,'set_value',side_effect=save), patch.object(daily.database,'all_word_keys',return_value=set()), patch.object(daily,'_today',return_value='2026-11-24'):
            first=daily.pick()
            self.assertEqual(first,daily.pick())
            daily.mark_shown()
            self.assertTrue(daily.shown_today())
        with patch.object(daily.cfg,'get',return_value=settings), patch.object(daily.cfg,'set_value',side_effect=save), patch.object(daily.database,'all_word_keys',return_value=set()), patch.object(daily,'_today',return_value='2026-11-25'):
            self.assertFalse(daily.shown_today())
            self.assertNotEqual(first[0],daily.pick()[0])
    def test_excludes_owned_and_cached(self):
        settings={'daily_word':{'selection':{'date':daily._today(),'word':'abandon'}}}
        with patch.object(daily.cfg,'get',return_value=settings), patch.object(daily.cfg,'set_value'), patch.object(daily.database,'all_word_keys',return_value={'abandon'}):
            self.assertNotEqual('abandon',daily.pick()[0])

    def test_exhausted(self):
        with patch.object(daily.cfg,'get',return_value={'daily_word':{}}), patch.object(daily.database,'all_word_keys',return_value={w for w,t in daily.BUILTIN}):
            self.assertIsNone(daily.pick())

    def test_toggle_hour(self):
        from worddict.dictionary_window import DictionaryWindow
        from unittest.mock import Mock
        win=Mock()
        with patch('worddict.dictionary_window.cfg.get', return_value={'daily_word':{'hour':9}}), patch('worddict.dictionary_window.cfg.set_value') as save:
            DictionaryWindow._toggle_daily_hour(win,9)
            save.assert_called_with('daily_word.hour',-1)
            DictionaryWindow._toggle_daily_hour(win,10)
            save.assert_called_with('daily_word.hour',10)
if __name__=='__main__': unittest.main()
