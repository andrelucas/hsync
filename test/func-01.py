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

	def rundiff(self, in_dir, out_dir=None):
		'''
		Set up copies of an existing tree (or existing trees), run hsync
		and report on any differences.
		'''

		in_tmp = os.path.join(self.topdir, 'in_tmp')
		hashfile = os.path.join(self.topdir, 'in_tmp', 'HSYNC.SIG')
		out_tmp = os.path.join(self.topdir, 'out_tmp')
		
		shutil.rmtree(in_tmp, True)
		shutil.rmtree(out_tmp, True)

		shutil.copytree(os.path.join(self.topdir, in_dir), in_tmp)
		if out_dir is not None:
			shutil.copytree(os.path.join(self.topdir, out_dir), out_tmp)
		else:
			os.mkdir(out_tmp)
		
		self.assertTrue(hsync.main(['-S', in_tmp]))
		self.assertTrue(hsync.main(['--no-write-hashfile', '-D', out_tmp, '-u', in_tmp, '-d']))

		os.unlink(hashfile)
		
		ret = subprocess.call(['diff', '-Purd', in_tmp, out_tmp])
		self.assertEqual(ret, 0, "diff -Purd should return 0 ('no differences')")
		
		shutil.rmtree(in_tmp)
		shutil.rmtree(out_tmp)



	def test_00runnable(self):
		'''Program is runnable directly from Python import'''
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


	def test_local_deldir(self):
		'''Make sure directories get deleted'''
		self.rundiff('t_deldir1_in', 't_deldir1_out')
		# Delete nested dirs. Checks the ordering of the deletion, as
		# we never explicitly do a recursive directory delete.
		self.rundiff('t_deldir2_in', 't_deldir2_out')
		# This one puts a file into a subdir that will be deleted.
		self.rundiff('t_deldir3_in', 't_deldir3_out')
	