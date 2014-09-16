#!/usr/bin/env python

import os
import unittest

from idmapper import *
from filehash import *

class FileHashUnitTestcase(unittest.TestCase):

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




