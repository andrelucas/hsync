# Unit test for hashlist_op_impl.py

# Copyright (c) 2015, Andre Lucas
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import unittest

from hsync.utility import *


class UtilityExcludeDirUnitTestCase(unittest.TestCase):

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

        excluded_dirs = set(['notexcluded/.exclude/'])

        self.assertFalse(_test_file_exclude('notexcluded/.excl_nope'))
        self.assertFalse(_test_file_exclude('notexcluded/.excl_nope/.exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/.exclude/gone'))

        # Edge case: This should fail if notexcluded/exclude is a file, and
        # pass if notexcluded/exclude is a directory.
        self.assertFalse(_test_file_exclude('notexcluded/.exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/.exclude',
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

        excluded_dirs = set()
        is_dir_excluded('notexcluded/.exclude', ['nonsense1', 'nonsense2'],
                        ['nonsense1', '*/.exclude', 'nonsense2'],
                        excluded_dirs)
        self.assertFalse(_test_file_exclude('notexcluded/.excl_nope'))
        self.assertFalse(_test_file_exclude('notexcluded/.excl_nope/exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/.exclude/gone'))

        # Edge case: This should fail if notexcluded/exclude is a file, and
        # pass if notexcluded/exclude is a directory.
        self.assertFalse(_test_file_exclude('notexcluded/.exclude'))
        self.assertTrue(_test_file_exclude('notexcluded/.exclude',
                                           is_dir=True))


class UtilityIncludeUnitTestCase(unittest.TestCase):

    def test_simple_include(self):
        '''Basic include matching'''
        included_dirs = set()
        inclist = ['include']
        inclist_glob = []

        def _test_include(fpath, is_dir=False):
            return is_path_included(fpath, inclist, inclist_glob,
                                    included_dirs, is_dir=is_dir)

        self.assertFalse(_test_include('notincluded'))
        self.assertTrue(_test_include('include'))

        self.assertFalse(_test_include('notincluded/include/'))
        # False because 'include' above wasn't marked as a directory.
        # This is a bit of an implementation artefact rather than a
        # desirable behaviour.
        self.assertFalse(_test_include('include/alsoincluded'))

        self.assertTrue(_test_include('include', is_dir=True))
        # Should be True now as we've said 'include' is a directory.
        self.assertTrue(_test_include('include/alsoincluded'))
        # Test component termination.
        self.assertFalse(_test_include('includex'))

    def test_simple_include_glob(self):
        '''Basic include globbing'''
        included_dirs = set()
        inclist = []
        inclist_glob = ['inc*']

        def _test_include(fpath, is_dir=False):
            return is_path_included(fpath, inclist, inclist_glob,
                                    included_dirs, is_dir=is_dir)

        self.assertFalse(_test_include('notincluded'))
        self.assertTrue(_test_include('include'))

        self.assertFalse(_test_include('notincluded/include/'))
        # True because fnmatch() makes it so - '*' translates to '.*' which
        # gets past the '/'.
        # XXX this isn't right - should really do better, I'm guessing this
        # will involve an alternative to fnmatch. Another day.
        self.assertTrue(_test_include('include/alsoincluded'))

        self.assertTrue(_test_include('include', is_dir=True))
        self.assertTrue(_test_include('include/alsoincluded'))


class UtilityHashfileUnitTestCase(unittest.TestCase):

    def test_simple_default(self):
        '''Default hashfile detection'''
        self.assertTrue(is_hashfile('HSYNC.SIG'))
        self.assertTrue(is_hashfile('HSYNC.SIG.gz'))
        self.assertFalse(is_hashfile('not-a-hashfile'))

    def test_simple_compress(self):
        '''Switchable compressed hashfile detection'''
        self.assertTrue(is_hashfile('HSYNC.SIG', allow_compressed=True))
        self.assertTrue(is_hashfile('HSYNC.SIG', allow_compressed=False))
        self.assertTrue(is_hashfile('HSYNC.SIG.gz', allow_compressed=True))
        self.assertFalse(is_hashfile('HSYNC.SIG.gz', allow_compressed=False))

    def test_override(self):
        '''Custom hashfile spec'''
        override = 'custom-HSYNC.SIG'
        self.assertTrue(is_hashfile('HSYNC.SIG', custom_hashfile=override))
        self.assertTrue(is_hashfile(override, custom_hashfile=override))
        self.assertFalse(is_hashfile('not-a-hashfile',
                                     custom_hashfile=override))
        self.assertTrue(is_hashfile('HSYNC.SIG.gz', custom_hashfile=override))
        self.assertTrue(is_hashfile('%s.gz' % override,
                                    custom_hashfile=override))
        self.assertFalse(is_hashfile('HSYNC.SIG.gz',
                                     custom_hashfile=override,
                                     allow_compressed=False))
        self.assertFalse(is_hashfile('%s.gz' % override,
                                     custom_hashfile=override,
                                     allow_compressed=False))

    def test_lock(self):
        '''Should detect locks too'''
        self.assertTrue(is_hashfile('HSYNC.SIG.lock'))
        self.assertFalse(is_hashfile('HSYNC.SIG.lock', allow_locks=False))

        override = 'custom-HSYNC.SIG'

        self.assertTrue(is_hashfile('HSYNC.SIG.lock',
                                    custom_hashfile=override))
        self.assertFalse(is_hashfile('HSYNC.SIG.lock',
                                     custom_hashfile=override,
                                     allow_locks=False))
        self.assertTrue(is_hashfile('%s.lock' % override,
                                    custom_hashfile=override))
        self.assertFalse(is_hashfile('%s.lock' % override,
                                     custom_hashfile=override,
                                     allow_locks=False))

        self.assertTrue(is_hashfile('HSYNC.SIG.gz.lock',
                                    custom_hashfile=override))
        self.assertFalse(is_hashfile('HSYNC.SIG.gz.lock',
                                     custom_hashfile=override,
                                     allow_locks=False))
        self.assertTrue(is_hashfile('%s.gz.lock' % override,
                                    custom_hashfile=override))
        self.assertFalse(is_hashfile('%s.gz.lock' % override,
                                     custom_hashfile=override,
                                     allow_locks=False))

        self.assertFalse(is_hashfile('HSYNC.SIG.gz.lock',
                                     custom_hashfile=override,
                                     allow_compressed=False))
        self.assertFalse(is_hashfile('HSYNC.SIG.gz.lock',
                                     custom_hashfile=override,
                                     allow_locks=False,
                                     allow_compressed=False))
        self.assertFalse(is_hashfile('%s.gz.lock' % override,
                                     custom_hashfile=override,
                                     allow_compressed=False))
        self.assertFalse(is_hashfile('%s.gz.lock' % override,
                                     custom_hashfile=override,
                                     allow_locks=False,
                                     allow_compressed=False))

    def test_bad_hashfile_name(self):
        '''Don't allow bogus hashfile spec'''
        with self.assertRaises(Exception):
            is_hashfile('HSYNC.SIG', custom_hashfile='')
