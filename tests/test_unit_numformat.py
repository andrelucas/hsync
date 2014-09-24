

import unittest

from hsync.numformat import *

class NumFormatTestCase(unittest.TestCase):

	def test_iec_simple(self):
		'''Whole-number IEC units are exactly correct'''
		self.assertEquals(bytes_to_iec(1024).lstrip(), '1.0KiB')
		self.assertEquals(bytes_to_iec(1024*1024).lstrip(), '1.00MiB')
		self.assertEquals(bytes_to_iec(1024*1024*1024).lstrip(), '1.000GiB')


	def test_si_simple(self):
		'''Whole-number SI units are exactly correct'''
		self.assertEquals(bytes_to_si(1000).lstrip(), '1.0kB')
		self.assertEquals(bytes_to_si(1000*1000).lstrip(), '1.00MB')
		self.assertEquals(bytes_to_si(1000*1000*1000).lstrip(), '1.000GB')


	def test_iec_thresh(self):
		'''Test edge cases for IEC'''
		bytes_edge = floor(threshold*KiB)
		self.assertEquals(bytes_to_iec(bytes_edge).lstrip(), '921B')
		self.assertEquals(bytes_to_iec(bytes_edge+1).lstrip(), '0.9KiB')

		megabytes_edge = floor(threshold * MiB)
		self.assertTrue(bytes_to_iec(megabytes_edge).endswith('KiB'))
		self.assertTrue(bytes_to_iec(megabytes_edge+1).endswith('MiB'))

		gigabytes_edge = floor(threshold * GiB)
		self.assertTrue(bytes_to_iec(gigabytes_edge).endswith('MiB'))
		self.assertTrue(bytes_to_iec(gigabytes_edge+1).endswith('GiB'))


	def test_si_thresh(self):
		'''Test edge cases for IEC'''
		bytes_edge = floor(threshold*kB)-1
		self.assertEquals(bytes_to_si(bytes_edge).lstrip(), '899B')
		self.assertEquals(bytes_to_si(bytes_edge+1).lstrip(), '0.9kB')

		megabytes_edge = floor(threshold * MB)-1
		self.assertTrue(bytes_to_si(megabytes_edge).endswith('kB'))
		self.assertTrue(bytes_to_si(megabytes_edge+1).endswith('MB'))

		gigabytes_edge = floor(threshold * GB)-1
		self.assertTrue(bytes_to_si(gigabytes_edge).endswith('MB'))
		self.assertTrue(bytes_to_si(gigabytes_edge+1).endswith('GB'))

