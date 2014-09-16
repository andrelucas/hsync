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

	def rundiff(self, in_dir, out_dir=None, delete=True):
		'''
		Set up copies of an existing tree (or existing trees), run hsync
		and report on any differences.

		If delete is True, remove the temporary output directories.
		Otherwise, return (in_tmp, out_tmp), probably for further
		comparison.
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

		#os.unlink(hashfile)
		
		ret = subprocess.call(['diff', '-Purd', '-x', 'HSYNC.SIG', in_tmp, out_tmp])
		self.assertEqual(ret, 0, "diff -Purd should return 0 ('no differences')")
		
		if delete:
			shutil.rmtree(in_tmp)
			shutil.rmtree(out_tmp)
		else:
			return (in_tmp, out_tmp)


	def runverify(self, in_dir, out_dir=None, munge_output=None):
		'''
		Run hsync, optionally change something, then run the verifier.
		'''

		(in_tmp, out_tmp) = self.rundiff(in_dir, out_dir, delete=False)
		hashfile = os.path.join(self.topdir, in_tmp, 'HSYNC.SIG')

		if munge_output is not None:
			munge_output(out_tmp)

		ret = hsync.main(['--verify-only', '-D', out_tmp, '-u', in_tmp, '-d'])

		shutil.rmtree(in_tmp)
		shutil.rmtree(out_tmp)
		return ret


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


	def test_local_verify1(self):
		'''Simple verify pass and fail'''
		# No-op successs.
		self.assertTrue(self.runverify('t_verify1_in'))
		# Detect deletion.
		def unlink_f1(out_tmp):
			os.unlink(os.path.join(out_tmp, 'f1'))

		self.assertFalse(self.runverify('t_verify2_in', None,
										munge_output=unlink_f1))


	def test_local_verify2(self):
		'''Less obvious verify fail'''
		def change_f1_1(out_tmp):
			'''Contents change'''
			fh = open(os.path.join(out_tmp, 'f1'), 'w')
			print >>fh, "hello2"
			fh.close()

		self.assertFalse(self.runverify('t_verify3_in', None,
										munge_output=change_f1_1))

	def test_local_verify3_modes(self):
		'''Check modes'''
		def change_f1_2(out_tmp):
			'''Mode change'''
			os.chmod(os.path.join(out_tmp, 'f1'), 0755)
		# Should fail.
		self.assertFalse(self.runverify('t_verify4_in', None,
										munge_output=change_f1_2))
