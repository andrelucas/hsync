# Unit test for stats collector object.

import unittest

from hsync.stats import *


class StatsCollectorUnitTestCase(unittest.TestCase):

	def test_basic1(self):
		s = StatsCollector.init('statstest', ['a', 'b'])
		s.a += 1
		s.b = 2
		self.assertEquals(s.a, 1, "Increment")
		self.assertEquals(s.b, 2, "Set directly")


	def test_unknown_attr_fail(self):
		s = StatsCollector.init('statstest', ['a', 'b'])
		with self.assertRaises(TypeError):
			s.c = 1


	def test_add_del_attr(self):
		s = StatsCollector.init('statstest', ['a', 'b'])
		with self.assertRaises(TypeError):
			s.c = 3
		s.add_attributes(['c'])
		s.c = 3
		self.assertEquals(s.c, 3, "Set new attr")
		s.del_attributes(['b'])
		with self.assertRaises(TypeError):
			s.b = 2
