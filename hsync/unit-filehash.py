#!/usr/bin/env python

import inspect
import os
import shutil
import unittest

from idmapper import *
from filehash import *

class FileHashUnitTestcase(unittest.TestCase):

	me = inspect.getfile(inspect.currentframe())
	topdir = os.path.join(os.path.dirname(me), 'test')

	mapper = UidGidMapper()

	def setUp(self):
		self.user = self.mapper.get_name_for_uid(os.getuid())
		self.group = self.mapper.get_name_for_gid(os.getgid())


	def test_symlink_localise(self):
		'''Localise symlink'''
		linkbase = "0 120644 %s %s 0 0 " % (self.user, self.group)

		linkstr = linkbase + "source/d1/d1.1/link>>>/dest/d1/d1.1/target"
		expect_src = 'source/d1/d1.1/link'
		expect_tgt = '/dest/d1/d1.1/target'
		expect_tgt_local = 'd1/d1.1/target'

		fh = FileHash.init_from_string(linkstr)
		self.assertIsInstance(fh, FileHash, "Can create link FileHash")
		self.assertTrue(fh.is_link, "FileHash is indeed a link")
		self.assertEqual(fh.fpath, expect_src,
							"Source is set correctly")
		self.assertEqual(fh.link_target, expect_tgt,
							"Target is set correctly")

		nonlocal = fh.localise_link_target('/somewhere/else')
		self.assertEqual(expect_tgt, nonlocal,
							"Don't normalise remote link")
		local = fh.localise_link_target('/dest')
		self.assertNotEqual(expect_tgt, local,
							"Normalise local link")
		local = fh.localise_link_target('/dest/')
		self.assertNotEqual(expect_tgt, local,
							"Normalise local link (trailing slash)")
		self.assertEqual(expect_tgt_local, local,
							"Normalise local link (trailing slash)")


class FileHashSymlinkSourceNormUnitTestcase(unittest.TestCase):

	me = inspect.getfile(inspect.currentframe())
	topdir = os.path.join(os.path.dirname(me), 'test')

	# Three directories deep. '../../../target' is ok. '../../../../target'
	# is not ok.
	tdir = 'source/d1/d1.1'

	mapper = UidGidMapper()

	@classmethod
	def setUpClass(self):
		self.user = self.mapper.get_name_for_uid(os.getuid())
		self.group = self.mapper.get_name_for_gid(os.getgid())
		self.linkbase = "0 120644 %s %s 0 0 " % (self.user, self.group)


	def setUp(self):
		tmp = os.path.join(self.topdir, "tmp")

		def t_mktmp(pathlist):
			assert isinstance(pathlist, (list, tuple))
			shutil.rmtree(tmp, True)
			os.makedirs(tmp)
			for p in pathlist:
				dpath = os.path.join(tmp, p)
				log.debug("makedirs(%s)", dpath)
				os.makedirs(dpath)

		tdir = self.tdir
		self.tdir_real = os.path.join(tmp, self.tdir)
		t_mktmp([tdir])
		self.tmp = tmp


	def _symlink_norm(self, link, tgt, absfail=False, check=True):

		tdir = self.tdir
		os.symlink(tgt, os.path.join(self.tmp, tdir, link))

		linkstr = self.linkbase + '%s/%s>>> %s' % (tdir, link, tgt)
		fh = FileHash.init_from_string(linkstr)
		
		self.assertIsInstance(fh, FileHash, "Can create link FileHash")
		norm_tpath = fh.source_symlink_make_relative(self.tmp,
												absolute_is_error=absfail)
		if check:
			self.assertEqual(norm_tpath, tgt)
		return norm_tpath


	def test_symlink_norm_up_l0(self):
		self._symlink_norm('link', 'target', absfail=True)
			

	def test_symlink_norm_up_l1(self):
		self._symlink_norm('link', '../target', absfail=True)


	def test_symlink_norm_up_l2(self):
		self._symlink_norm('link', '../../target', absfail=True)


	def test_symlink_norm_up_l3(self):
		self._symlink_norm('link', '../../../target', absfail=True)


	def test_symlink_norm_up_l4_fail(self):
		'''Link points up one directory too many, don't allow'''
		with self.assertRaises(SymlinkPointsOutsideTreeError):
			self._symlink_norm('link', '../../../../target', absfail=True)


	def test_symlink_norm_up_l4_abs(self):
		'''Link points up one directory too many, abs link results'''
		abslink = self._symlink_norm('link', '../../../../target', check=False)
		# It will point to topdir, not self.tmp which is a subdir of topdir.
		# That's the point.
		self.assertEqual(abslink, os.path.join(self.topdir, 'target'),
						"Absolute link is correct")


