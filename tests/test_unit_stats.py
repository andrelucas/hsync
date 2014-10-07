# Unit test for stats collector object.

import unittest

from hsync.stats import *


class StatsCollectorUnitTestCase(unittest.TestCase):

	def test_basic1(self):
		'''Simple set test'''
		s = StatsCollector.init('statstest', ['a', 'b'])
		s.a += 1
		s.b = 2
		self.assertEquals(s.a, 1, "Increment")
		self.assertEquals(s.b, 2, "Set directly")


	def test_unknown_attr_fail(self):
		'''Unknown attribute should raise'''
		s = StatsCollector.init('statstest', ['a', 'b'])
		with self.assertRaises(TypeError):
			s.c = 1


	def test_add_del_attr(self):
		'''Can add and delete attributes'''
		s = StatsCollector.init('statstest', ['a', 'b'])
		with self.assertRaises(TypeError):
			s.c = 3
		s.add_attributes(['c'])
		s.c = 3
		self.assertEquals(s.c, 3, "Set new attr")
		s.del_attributes(['b'])
		with self.assertRaises(TypeError):
			s.b = 2


	def test_iteritems(self):
		'''iteritems() works'''
		s = StatsCollector.init('statstest', ['a', 'b', 'c'])
		s.a = 1
		s.b = 2
		s.c = 3
		copy = {}
		for k,v in s.iteritems():
			copy[k] = v

		test = { 'a': 1, 'b': 2, 'c': 3 }
		self.assertEquals(copy, test)


	def test_check_str(self):
		'''str() works'''
		s = StatsCollector.init('statstest', ['a', 'b'])
		s.a = 1
		s.b = 2
		self.assertEquals(str(s), 'statstest: a=1, b=2',
							"str() is as expected")