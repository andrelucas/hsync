

import unittest

from hsync.numformat import *

class NumFormatTestCase(unittest.TestCase):

	def test_iec_simple(self):
		'''Whole-number IEC units are exactly correct'''
		self.assertEquals(IECUnitConverter.bytes_to_unit(1024).lstrip(), '1.0KiB')
		self.assertEquals(IECUnitConverter.bytes_to_unit(1024*1024).lstrip(), '1.00MiB')
		self.assertEquals(IECUnitConverter.bytes_to_unit(1024*1024*1024).lstrip(), '1.000GiB')


	def test_si_simple(self):
		'''Whole-number SI units are exactly correct'''
		self.assertEquals(SIUnitConverter.bytes_to_unit(1000).lstrip(), '1.0kB')
		self.assertEquals(SIUnitConverter.bytes_to_unit(1000*1000).lstrip(), '1.00MB')
		self.assertEquals(SIUnitConverter.bytes_to_unit(1000*1000*1000).lstrip(), '1.000GB')


	def test_iec_thresh(self):
		'''Test edge cases for IEC'''
		bytes_edge = floor(threshold*KiB)
		self.assertEquals(IECUnitConverter.bytes_to_unit(bytes_edge).lstrip(), '921B')
		self.assertEquals(IECUnitConverter.bytes_to_unit(bytes_edge+1).lstrip(), '0.9KiB')

		megabytes_edge = floor(threshold * MiB)
		self.assertTrue(IECUnitConverter.bytes_to_unit(megabytes_edge).endswith('KiB'))
		self.assertTrue(IECUnitConverter.bytes_to_unit(megabytes_edge+1).endswith('MiB'))

		gigabytes_edge = floor(threshold * GiB)
		self.assertTrue(IECUnitConverter.bytes_to_unit(gigabytes_edge).endswith('MiB'))
		self.assertTrue(IECUnitConverter.bytes_to_unit(gigabytes_edge+1).endswith('GiB'))


	def test_si_thresh(self):
		'''Test edge cases for IEC'''
		bytes_edge = floor(threshold*kB)-1
		self.assertEquals(SIUnitConverter.bytes_to_unit(bytes_edge).lstrip(), '899B')
		self.assertEquals(SIUnitConverter.bytes_to_unit(bytes_edge+1).lstrip(), '0.9kB')

		megabytes_edge = floor(threshold * MB)-1
		self.assertTrue(SIUnitConverter.bytes_to_unit(megabytes_edge).endswith('kB'))
		self.assertTrue(SIUnitConverter.bytes_to_unit(megabytes_edge+1).endswith('MB'))

		gigabytes_edge = floor(threshold * GB)-1
		self.assertTrue(SIUnitConverter.bytes_to_unit(gigabytes_edge).endswith('MB'))
		self.assertTrue(SIUnitConverter.bytes_to_unit(gigabytes_edge+1).endswith('GB'))

