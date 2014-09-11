#!/usr/bin/env python

# Functional tests for hsync.

import inspect
import os
import shutil
import subprocess
import unittest

import hsync

class HsyncBruteForceFunctionalTestCase(unittest.TestCase):

	me = inspect.getfile(inspect.currentframe())
	topdir = os.path.dirname(me)

	def rundiff(self, in_dir):
		in_tmp = os.path.join(self.topdir, 'in_tmp')
		hashfile = os.path.join(self.topdir, 'in_tmp', 'HSYNC.SIG')
		out_tmp = os.path.join(self.topdir, 'out_tmp')
		shutil.rmtree(in_tmp, True)
		shutil.rmtree(out_tmp, True)
		os.mkdir(out_tmp)
		shutil.copytree(os.path.join(self.topdir, in_dir), in_tmp)
		self.assertTrue(hsync.main(['-S', in_tmp, '-t']))
		self.assertTrue(hsync.main(['-D', out_tmp, '-u', in_tmp, '-t', '-d']))
		os.unlink(hashfile)
		ret = subprocess.call(['diff', '-Purd', in_tmp, out_tmp])
		self.assertEqual(ret, 0, "diff -Purd should return 0 ('no differences')")
		shutil.rmtree(in_tmp)
		shutil.rmtree(out_tmp)


	def test_runnable(self):
		'''Program is runnable directly from Python'''
		with self.assertRaises(SystemExit):
			hsync.main(['-h'])


	def test_local_flat1(self):
		'''Single directory of files, local filesystem'''
		self.rundiff('t_flat1')
		self.rundiff('t_flat2')


	def test_local_sub1(self):
		'''Small file tree, local filesystem'''
		self.rundiff('t_sub1')
		self.rundiff('t_sub2')


	