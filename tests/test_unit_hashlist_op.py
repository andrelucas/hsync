# Unit test for hashlist_op_impl.py


import unittest

from hsync.hashlist_op_impl import *
from hsync.utility import is_dir_excluded, is_path_pre_excluded


class HashlistOpTestCase(unittest.TestCase):

    def test_dir_exclude(self):
        '''Hashlist exclusions 101'''
        direx = ['exclude/']
        direx_glob = []
        excluded_dirs = set()

        def _test_dir_exclude(fpath):
            return is_dir_excluded(fpath, direx, direx_glob, excluded_dirs)

        self.assertFalse(_test_dir_exclude('notexcluded/'))
        self.assertTrue(_test_dir_exclude('exclude/'))

        self.assertFalse(_test_dir_exclude('notexcluded/exclude/'))

    def test_dir_exclude_glob_simple(self):
        '''Hashlist glob exclusions 101'''
        direx = []
        direx_glob = ['excl*']
        excluded_dirs = set()

        def _test_dir_exclude(fpath):
            return is_dir_excluded(fpath, direx, direx_glob, excluded_dirs)

        self.assertFalse(_test_dir_exclude('notexcluded/'))
        self.assertTrue(_test_dir_exclude('exclude/'))

        self.assertFalse(_test_dir_exclude('notexcluded/exclude/'))

    def test_dir_exclude_glob_simple_nullstate(self):
        '''Hashlist glob exclusions, stateless mode'''
        direx = []
        direx_glob = ['excl*']

        def _test_dir_exclude(fpath):
            # This variant doesn't keep any state, useful for one-shot
            # (e.g. during a walk where all subtrees can be excluded).
            return is_dir_excluded(fpath, direx, direx_glob)

        self.assertFalse(_test_dir_exclude('notexcluded/'))
        self.assertTrue(_test_dir_exclude('exclude/'))

        self.assertFalse(_test_dir_exclude('notexcluded/exclude/'))

    def test_dir_exclude_glob_sub(self):
        '''Hashlist glob exclusions in subdir'''
        direx = []
        direx_glob = ['*/exclude/']
        excluded_dirs = set()

        def _test_dir_exclude(fpath):
            return is_dir_excluded(fpath, direx, direx_glob, excluded_dirs)

        self.assertFalse(_test_dir_exclude('notexcluded/'))
        self.assertFalse(_test_dir_exclude('exclude/'))  # No leading path.

        self.assertTrue(_test_dir_exclude('notexcluded/exclude/'))
        self.assertTrue(_test_dir_exclude('notexcluded/exclude/alsoexcluded'))

    def test_path_pre_exclude(self):
        '''Exclusion of files under excluded directories'''
        excluded_dirs = set(['exclude/'])

        def _test_file_exclude(fpath, is_dir=False):
            return is_path_pre_excluded(fpath, excluded_dirs, is_dir=is_dir)

        self.assertFalse(_test_file_exclude('notexcluded/'))
        self.assertTrue(_test_file_exclude('exclude/'))
        self.assertTrue(_test_file_exclude('exclude/gone'))
        self.assertFalse(_test_file_exclude('notexcluded/excluded/keep'))

        excluded_dirs = set(['notexcluded/exclude/'])

        self.assertFalse(_test_file_exclude('notexcluded/excl_nope'))
        self.assertFalse(_test_file_exclude('notexcluded/excl_nope/exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/exclude/gone'))

        # Edge case: This should fail if notexcluded/exclude is a file, and
        # pass if notexcluded/exclude is a directory.
        self.assertFalse(_test_file_exclude('notexcluded/exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/exclude',
                        is_dir=True))

    def test_path_pre_exclude_glob(self):
        '''Exclusion of files under excluded directories (glob)'''
        excluded_dirs = set()
        is_dir_excluded('exclude', [], ['excl*'], excluded_dirs)

        def _test_file_exclude(fpath, is_dir=False):
            return is_path_pre_excluded(fpath, excluded_dirs, is_dir=is_dir)

        self.assertFalse(_test_file_exclude('notexcluded/'))
        self.assertTrue(_test_file_exclude('exclude/'))
        self.assertTrue(_test_file_exclude('exclude/gone'))
        self.assertFalse(_test_file_exclude('notexcluded/excluded/keep'))

        excluded_dirs = set()
        is_dir_excluded('notexcluded/exclude', [], ['notexcluded/excl*'],
                        excluded_dirs)

        self.assertFalse(_test_file_exclude('notexcluded/excl_nope'))
        self.assertFalse(_test_file_exclude('notexcluded/excl_nope/exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/exclude/gone'))

        # Edge case: This should fail if notexcluded/exclude is a file, and
        # pass if notexcluded/exclude is a directory.
        self.assertFalse(_test_file_exclude('notexcluded/exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/exclude',
                        is_dir=True))
