# Unit tests for lockfile

import inspect
import logging
import os
import shutil
from time import sleep
import unittest

from hsync.lockfile import LockFile


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
		l = LockFile(self.locktmp)
		self.assertIsNotNone(l, "Object created")
		self.assertTrue(os.path.isfile(self.locktmp), "Lockfile created")
		l.remove()
		self.assertFalse(os.path.isfile(self.locktmp), "Lockfile removed")


	def test_open_destructor(self):
		l = LockFile(self.locktmp)
		self.assertIsNotNone(l, "Object created")
		self.assertTrue(os.path.isfile(self.locktmp), "Lockfile created")
		l = None
		self.assertFalse(os.path.isfile(self.locktmp), "Lockfile removed")


	def test_open_multi(self):
		l1 = LockFile(self.locktmp)
		self.assertIsNotNone(l1, "Object created")
		self.assertTrue(os.path.isfile(self.locktmp), "Lockfile created")
		with self.assertRaises(OSError):
			l2 = LockFile(self.locktmp)

		l1.remove()
		self.assertFalse(os.path.isfile(self.locktmp), "Lockfile removed")
