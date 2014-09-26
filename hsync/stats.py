# Stats collection object

from collections import namedtuple
import logging

log = logging.getLogger()


class StatsCollector(object):

	@staticmethod
	def init(name, attrlist):
		StatClass = namedtuple(name, attrlist)
		zeroes = [0] * len(attrlist)
		return StatClass._make(zeroes)

