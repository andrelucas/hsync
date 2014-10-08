# Unit tests for lockfile

from __future__ import print_function

import inspect
import os
import shutil
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
