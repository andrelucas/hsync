# Unit tests for lockfile

from __future__ import print_function

import inspect
import os
import shutil
import sys
import unittest

from hsync.exceptions import NotADirectoryError
from hsync.lockfile import LockFile, LockFileManager


class TestUnitLockFileTestCase(unittest.TestCase):

    me = inspect.getfile(inspect.currentframe())
    medir = os.path.dirname(me)
    topdir = os.path.join(medir, 'test')
    lfdir = os.path.join(topdir, 'lockfile')
    locktmp = os.path.join(lfdir, 't')

    def setUp(self):
        shutil.rmtree(self.lfdir, True)
        os.mkdir(os.path.join(self.lfdir))

    def test_open_remove(self):
        '''Lockfile create and destroy'''
        l = LockFile(self.locktmp)
        self.assertIsNotNone(l, "Object created")
        self.assertTrue(os.path.isfile(self.locktmp), "Lockfile created")
        l.remove()
        self.assertFalse(os.path.isfile(self.locktmp), "Lockfile removed")

    def test_open_destructor(self):
        '''Lockfile auto-destroy'''
        l = LockFile(self.locktmp)
        self.assertIsNotNone(l, "Object created")
        self.assertTrue(os.path.isfile(self.locktmp), "Lockfile created")
        l = None
        self.assertFalse(os.path.isfile(self.locktmp), "Lockfile removed")

    def test_open_multi(self):
        '''Lockfile multi-open failure'''
        l1 = LockFile(self.locktmp)
        self.assertIsNotNone(l1, "Object created")
        self.assertTrue(os.path.isfile(self.locktmp), "Lockfile created")
        with self.assertRaises(OSError):
            LockFile(self.locktmp)

        l1.remove()
        self.assertFalse(os.path.isfile(self.locktmp), "Lockfile removed")

    def test_context(self):
        '''Lockfile context manager'''
        with LockFileManager(self.locktmp):
            self.assertTrue(os.path.exists(self.locktmp),
                            "Lockfile exists inside manager")

        self.assertFalse(os.path.isfile(self.locktmp), "Lockfile removed")

    def test_lock_in_non_dir(self):
        '''Shouldn't try to create a lockfile under a non-directory'''
        regfilename = os.path.join(self.topdir, 'not_a_directory')
        regfile_subdir_lock = os.path.join(regfilename, 'bad')
        regfile = open(regfilename, 'w')
        print("hello", file=regfile)
        regfile.close()
        self.assertTrue(os.path.isfile(regfilename), 'Regular file created')
        with self.assertRaises(NotADirectoryError):
            LockFile(regfile_subdir_lock)

        os.unlink(regfilename)

    def _create_bogus_lockfile(self, lockname, lockself=False,
                               badpid=False, shortfile=False):

        if lockself:
            testpid = os.getpid()
        else:
            # Non-existent pid.
            testpid = 6666
            if os.getpid() == testpid:
                testpid -= 1

        if badpid:
            testpid = 'FAIL'
        else:
            testpid = str(testpid)

        # Create a bogus lockfile.
        with open(lockname, 'w') as f:
            if shortfile:
                print("%s" % testpid, file=f, end='')
            else:
                print('%s\n%s' % (testpid, sys.argv[0]), file=f)

    def test_lockfile_dead_nobreak(self):
        '''When instructed, don't remove dead process lockfile'''

        self._create_bogus_lockfile(self.locktmp)

        # This should raise, as we've told it not to remove the lockfile
        # when normally it would be removed.
        with self.assertRaises(OSError):
            LockFile(self.locktmp, break_dead_lockfile=False)

    def test_lockfile_dead_break(self):
        '''Detect and break a lockfile from a dead process'''

        self._create_bogus_lockfile(self.locktmp)

        # This should succeed, but the dead lock needs to be broken first.
        with LockFileManager(self.locktmp, break_dead_lockfile=True):
            self.assertTrue(os.path.isfile(self.locktmp))

    def test_lockfile_alive_nobreak(self):
        '''Don't break the lockfile when we're the process holding it'''

        self._create_bogus_lockfile(self.locktmp, lockself=True)

        # This should fail - it's this process' lockfile.
        with self.assertRaises(OSError):
            LockFile(self.locktmp, break_dead_lockfile=True)

    def test_lockfile_detect_corrupt_pid(self):
        '''Notice when the lockfile PID is bogus.'''

        self._create_bogus_lockfile(self.locktmp, lockself=True, badpid=True)

        with self.assertRaises(Exception):
            LockFile(self.locktmp)

    def test_lockfile_detect_corrupt_lockfile_length(self):
        '''Notice when the lockfile isn't two lines long'''

        self._create_bogus_lockfile(self.locktmp, lockself=True,
                                    shortfile=True)

        with self.assertRaises(Exception):
            LockFile(self.locktmp)
