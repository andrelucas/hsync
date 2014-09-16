#!/usr/bin/env python

import inspect
import os
import shutil
import unittest

from idmapper import *
from filehash import *


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

	def tearDown(self):
		if self.tmp:
			shutil.rmtree(self.tmp, True)


	def _symlink_norm(self, link, tgt, absfail=False, check=True):

		tmp = os.path.join(self.topdir, "tmp")
		self.tmp = tmp

		(ldir, lfile) = os.path.split(link)
		log.debug("ldir %s lfile %s", ldir, lfile)

		shutil.rmtree(tmp, True)
		os.makedirs(tmp)

		if ldir:
			self.ldir_real = os.path.join(tmp, ldir)
			log.debug("ldir_real %s", self.ldir_real)
			os.makedirs(self.ldir_real)

		os.symlink(tgt, os.path.join(self.tmp, link))

		linkstr = self.linkbase + '%s/%s>>> %s' % (ldir, lfile, tgt)
		fh = FileHash.init_from_string(linkstr, trim=True, root=self.tmp)
		
		self.assertIsInstance(fh, FileHash, "Can create link FileHash")
		norm_tpath = fh.source_symlink_make_relative(self.tmp,
												absolute_is_error=absfail)
		if check:
			self.assertEqual(norm_tpath, tgt)
		return (fh, norm_tpath)


	def test_symlink_relative_up(self):
		'''In-tree symlinks relative simple'''
		link = os.path.join(self.tdir, 'link')
		for tgt in ('target', '../target', '../../target',
						'../../../target'):

			(fh, np) = self._symlink_norm(link, tgt, absfail=True)
			self.assertFalse(fh.link_is_external, "External flag not set")
			self.assertEqual(tgt, fh.link_target, "Object link target set")


	def test_symlink_norm_up_l4_throw(self):
		'''Link points up one directory too many, don't allow'''
		with self.assertRaises(SymlinkPointsOutsideTreeError):
			self._symlink_norm('link', '../../../../target', absfail=True)


	def test_symlink_norm_up_l4_abs(self):
		'''Link points up one directory too many, abs link results'''
		link = os.path.join(self.tdir, 'link')
		(fh, norm_tpath) = self._symlink_norm(link, '../../../../target',
												check=False)
		# It will point to topdir, not self.tmp which is a subdir of topdir.
		# That's the point.
		self.assertEqual(norm_tpath, os.path.join(self.topdir, 'target'),
						"Absolute link is correct")
		self.assertTrue(fh.link_is_external, "External flag is set properly")
		fh.normalise_symlink(self.topdir)
		self.assertEqual(fh.link_target, os.path.join(self.topdir, 'target'),
							"Object link is correct")


	def test_symlink_norm_inside(self):
		'''In-tree symlinks relative 2'''
		for tgt in ('source/d1/d1.2/target', 'source/d1/target',
					'source/target', 'target'):
			(fh, np) = self._symlink_norm('source/link', tgt, absfail=True)
			self.assertEqual(np, tgt, "Link stays inbound")
			self.assertEqual(tgt, fh.link_target, "Object link target set")

