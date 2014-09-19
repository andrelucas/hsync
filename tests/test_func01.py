#!/usr/bin/env python

# Functional tests for hsync.

from __future__ import print_function

import inspect
import logging
import os
import shutil
import stat
import cStringIO as StringIO
import subprocess
import sys
import time
import unittest
import urllib2

from hsync import hsync

log = logging.getLogger()

class HsyncBruteForceFunctionalTestCase(unittest.TestCase):

	me = inspect.getfile(inspect.currentframe())
	medir = os.path.dirname(me)
	topdir = os.path.join(medir, 'test')
	in_tmp = os.path.join(topdir, 'in_tmp')
	out_tmp = os.path.join(topdir, 'out_tmp')
	web_server_running = False

	wport = 8880

	@classmethod
	def setUpClass(cls):
		oldwd = os.getcwd()
		os.chdir(os.path.dirname(cls.topdir))
		redir = StringIO.StringIO()
		cmd = "/usr/bin/env python -m SimpleHTTPServer %d" % cls.wport
		#fnull = open(os.devnull, 'w')
		fnull = open('server.log', 'w')
		cls.webp = subprocess.Popen(cmd.split(),
								stdout=fnull, stderr=subprocess.STDOUT)
		os.chdir(oldwd)
		time.sleep(1)
		success = False
		for n in range(1,5):
			try:
				u = urllib2.urlopen('http://127.0.0.1:%d/' % cls.wport)
				success = True
				cls.web_server_running = True
			except urllib2.URLError:
				log.debug("Waiting for server to start (%d)" % n)
				time.sleep(1)
		if not success:
			raise OSError("Failed to start web server")


	@classmethod
	def tearDownClass(cls):
		cls.webp.terminate()
		cls.webp.wait()


	def tearDown(self):
		shutil.rmtree(self.in_tmp, True)
		shutil.rmtree(self.out_tmp, True)


	def rundiff(self, in_dir, out_dir=None, delete=True,
				src_optlist=None, dst_optlist=None, web=False,
				diff_optlist=None, run_diff=True):
		'''
		Set up copies of an existing tree (or existing trees), run hsync
		and report on any differences.

		Differences are detected using 'diff -Purd'. This has a few problems,
		notably it's not that portable, and that broken symlinks will cause
		it to fail.

		If delete is True, remove the temporary output directories.
		Otherwise, return (in_tmp, out_tmp), probably for further
		comparison.

		src_optlist and dst_optlist are optional lists of additional options
		to pass to the -S and -D commands respectively.

		'''

		in_tmp = self.in_tmp
		out_tmp = self.out_tmp
		hashfile = os.path.join(self.topdir, 'in_tmp', 'HSYNC.SIG')
		
		shutil.rmtree(in_tmp, True)
		shutil.rmtree(out_tmp, True)

		shutil.copytree(os.path.join(self.topdir, in_dir), in_tmp, symlinks=True)
		subprocess.check_call(['find', in_tmp, '-name', '.gitignore',
								'-exec', 'rm', '{}', ';'])
		if out_dir is not None:
			shutil.copytree(os.path.join(self.topdir, out_dir), out_tmp, symlinks=True)
			subprocess.check_call(['find', out_tmp, '-name', '.gitignore',
									'-exec', 'rm', '{}', ';'])
		else:
			os.mkdir(out_tmp)
		
		srcopt = ['-S', in_tmp]
		if src_optlist is not None:
			srcopt.extend(src_optlist)
		self.assertTrue(hsync.main(srcopt))

		in_url = in_tmp
		port = None
		if web:
			in_url = 'http://127.0.0.1:%d/test/in_tmp' % (self.wport)
			log.debug("Fetch URL: %s", in_url)

		#time.sleep(20) # XXX
		dstopt = ['--no-write-hashfile', '-D', out_tmp, '-u', in_url, '-d']
		if dst_optlist is not None:
			dstopt.extend(dst_optlist)
		self.assertTrue(hsync.main(dstopt))

		#os.unlink(hashfile)
		
		if run_diff:
			diffopt = ['diff', '-Purd', '-x', 'HSYNC.SIG', in_tmp, out_tmp]
			if diff_optlist is not None:
				diffopt.extend(diff_optlist)
			ret = subprocess.call(diffopt)
			# if ret != 0:
			# 	subprocess.call("bash", shell=True)
			self.assertEqual(ret, 0, "diff -Purd should return 0 ('no differences')")

		if delete:
			shutil.rmtree(in_tmp)
			shutil.rmtree(out_tmp)
		else:
			return (in_tmp, out_tmp)


	def runverify(self, in_dir, out_dir=None, munge_output=None,
					src_optlist=None, dst_optlist=None, vfy_optlist=None):
		'''
		Run hsync, optionally change something, then run the verifier.
		'''

		(in_tmp, out_tmp) = self.rundiff(in_dir, out_dir, delete=False,
											src_optlist=src_optlist,
											dst_optlist=dst_optlist)
		hashfile = os.path.join(self.topdir, in_tmp, 'HSYNC.SIG')

		if munge_output is not None:
			munge_output(out_tmp)

		vfyopt = ['--verify-only', '-D', out_tmp, '-u', in_tmp, '-d']
		if vfy_optlist is not None:
			vfyopt.extend(vfy_optlist)
		ret = hsync.main(vfyopt)

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
		'''Trivial contents change verify check'''
		def change_f1_1(out_tmp):
			'''Contents change'''
			fh = open(os.path.join(out_tmp, 'f1'), 'w')
			print("hello2", file=fh)
			fh.close()

		self.assertFalse(self.runverify('t_verify3_in', None,
										munge_output=change_f1_1))


	def test_local_verify3_modes(self):
		'''Mode change verify and toggle'''
		def change_f1_2(out_tmp):
			'''Mode change'''
			os.chmod(os.path.join(out_tmp, 'f1'), 0755)
		# Should fail.
		self.assertFalse(self.runverify('t_verify4_in', None,
										munge_output=change_f1_2))
		# Should succeed.
		self.assertTrue(self.runverify('t_verify4_in', None,
										vfy_optlist=['--ignore-mode'],
										munge_output=change_f1_2))


	def _checklink(self, linkpath, target):
		lstat = os.lstat(linkpath)
		self.assertTrue(stat.S_ISLNK(lstat.st_mode), "Symlink created")
		self.assertEqual(os.readlink(linkpath), target, "Symlink target correct")


	def test_local_symlink1(self):
		'''Simple symlink copy'''
		self.rundiff('t_sym1_in', None, delete=False)
		#subprocess.check_call(("ls -lR %s" % self.out_tmp).split())
		linkpath = os.path.join(self.out_tmp, 'l1')
		self._checklink(linkpath, 'f1')

	
	def test_local_symlink2(self):
		'''Symlink copy with relative paths'''
		self.rundiff('t_sym2_in', None, delete=False)
		linkpath = os.path.join(self.out_tmp, 'd1/d1.1/l1')
		self._checklink(linkpath, '../../f1')
		

	def test_local_symlink3_del(self):
		'''Delete symlink'''
		self.rundiff('t_sym3_in', 't_sym3_out', delete=False)
		# Make sure it didn't delete the target.
		fpath = os.path.join(self.out_tmp, 'f1')
		self.assertTrue(os.path.exists(fpath), "Didn't delete target")
		self.assertTrue(stat.S_ISREG(os.lstat(fpath).st_mode), "Didn't transmute target")


	def test_web_tarball(self):
		'''Unpack some tarballs, run a web server on their dir and diff'''
		os.chdir(self.topdir)
		tarball = 'zlib-1.2.8.tar.gz'
		tardir = 'zlib-1.2.8'
		subprocess.check_call(("tar xzf %s" % tarball).split())
		self.rundiff(tardir, None, web=True)
		shutil.rmtree(tardir)


	def test_exclude_simple_src(self):
		'''Check manual -X option works on the server end'''
		# Have to manually check, diff is useless here.
		self.rundiff('t_exclude1_in', 't_exclude1_out',
			delete=False, src_optlist=['-X', 'd2_exclude'], run_diff=False)
		self.assertTrue(os.path.exists(os.path.join(self.in_tmp, 'd1')),
			"Not-excluded directory is in the source")
		self.assertTrue(os.path.exists(os.path.join(self.in_tmp, 'd2_exclude')),
			"Excluded directory is in the source")
		self.assertTrue(os.path.exists(os.path.join(self.out_tmp, 'd1')),
			"Not-excluded directory does not get copied")
		self.assertTrue(not os.path.exists(os.path.join(self.out_tmp, 'd2_exclude')),
			"Excluded directory does not get copied")
		

	def test_exclude_simple_dst(self):
		'''Check manual -X option works on the client end'''
		# Exclude d2_exclude on the client side (it's in the HSYNC.SIG).
		# Have to manually check, diff is useless here.
		self.rundiff('t_exclude2_in', 't_exclude2_out',
			delete=False, dst_optlist=['-X', 'd2_exclude'], run_diff=False)
		#subprocess.call("bash", shell=True)
		self.assertTrue(os.path.exists(os.path.join(self.in_tmp, 'd1')),
			"Not-excluded directory is in the source")
		self.assertTrue(os.path.exists(os.path.join(self.in_tmp, 'd2_exclude')),
			"Excluded directory is in the source")
		self.assertTrue(os.path.exists(os.path.join(self.out_tmp, 'd1')),
			"Not-excluded directory gets copied")
		self.assertTrue(not os.path.exists(os.path.join(self.out_tmp, 'd2_exclude')),
			"Excluded directory does not get copied")


	def test_signature_url(self):
		'''Check the signature-outside-tree feature works'''
		sigurl = '%s/t_sigoutside1/HSYNC.SIG' % self.topdir
		self.rundiff('t_sigoutside1/in', 't_sigoutside1/out',
			src_optlist=['-U', sigurl],
			dst_optlist=['-U', sigurl])
		os.unlink(sigurl)


