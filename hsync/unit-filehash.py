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
		log.debug("XXX ldir %s lfile %s", ldir, lfile)

		shutil.rmtree(tmp, True)
		os.makedirs(tmp)

		if ldir:
			self.ldir_real = os.path.join(tmp, ldir)
			log.debug("ldir_real %s", self.ldir_real)
			os.makedirs(self.ldir_real)

		os.symlink(tgt, os.path.join(self.tmp, link))

		linkstr = self.linkbase + '%s/%s>>> %s' % (ldir, lfile, tgt)
		fh = FileHash.init_from_string(linkstr)
		
		self.assertIsInstance(fh, FileHash, "Can create link FileHash")
		norm_tpath = fh.source_symlink_make_relative(self.tmp,
												absolute_is_error=absfail)
		if check:
			self.assertEqual(norm_tpath, tgt)
		return norm_tpath


	def test_symlink_norm_up_l0(self):
		link = os.path.join(self.tdir, 'link')
		self._symlink_norm(link, 'target', absfail=True)
		self._symlink_norm(link, '../target', absfail=True)
		self._symlink_norm(link, '../../target', absfail=True)
		self._symlink_norm(link, '../../../target', absfail=True)

	def test_symlink_norm_up_l4_fail(self):
		'''Link points up one directory too many, don't allow'''
		with self.assertRaises(SymlinkPointsOutsideTreeError):
			self._symlink_norm('link', '../../../../target', absfail=True)


	def test_symlink_norm_up_l4_abs(self):
		'''Link points up one directory too many, abs link results'''
		link = os.path.join(self.tdir, 'link')
		abslink = self._symlink_norm(link, '../../../../target', check=False)
		# It will point to topdir, not self.tmp which is a subdir of topdir.
		# That's the point.
		self.assertEqual(abslink, os.path.join(self.topdir, 'target'),
						"Absolute link is correct")


	def test_symlink_norm_inside(self):
		norm = self._symlink_norm('source/link', 'source/d1/d1.2/target', absfail=True)
		self._symlink_norm('source/link', 'source/d1/target', absfail=True)			
		self._symlink_norm('source/link', 'source/target', absfail=True)
		self._symlink_norm('source/link', 'target', absfail=True)

