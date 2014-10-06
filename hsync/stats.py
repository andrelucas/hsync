# Stats collection object

from collections import namedtuple
import logging

log = logging.getLogger()


class StatsCollector(object):
	'''
	Simple stats collector object.

	Useful object to pass around, has an attribute for a list of names so one
	doesn't have to mess around with getters and setters.

	'''

	__is_frozen = False

	def __init__(self, name, attrlist):
		self.__name = name
		self.set_attributes(attrlist)
		self._freeze()


	@staticmethod
	def init(name, attrlist):
		'''
		Factory method, recommended way of creating a StatsCollector object.
		'''
		return StatsCollector(name, attrlist)


	def __str__(self):
		skey = self._existing_keys()
		skey.sort()
		log.debug(skey)
		items = ['%s=%s' % (k, getattr(self, k)) for k in skey]
		return '%s: %s' % (self.__name, ', '.join(items))


	def name(self):
		return self.__name


	def _unfreeze(self):
		self.__is_frozen = False


	def _freeze(self):
		self.__is_frozen = True


	def _existing_keys(self):
		return [k for k in self.__dict__.keys() if not k.startswith('_')]


	def keys(self):
		return self._existing_keys()


	def iteritems(self):
		for k in self.keys():
			yield k, getattr(self, k)


	def set_attributes(self, attrlist):
		'''
		Change the current attribute list to attrlist. Add new keys and
		remove existing keys as required.
		'''

		self._unfreeze()
		attrset = set(attrlist)

		# Current attributes.
		oldkeys = set(self._existing_keys())
		# Keys to add, in attrlist but not in oldkeys.
		newkeys = attrset - oldkeys
		# Keys to remove, in oldkeys but not in attrlist.
		delkeys = oldkeys - attrset

		self._add(newkeys)
		self._del(delkeys)
		self._freeze()


	def _add(self, itemset):
		for item in itemset:
			log.debug("adding attribute '%s'", item)
			setattr(self, item, 0)


	def add_attributes(self, newattrlist):
		'''
		Add attributes in newattrlist that aren't in the current list of
		attributes.
		'''

		self._unfreeze()
		attrset = set(newattrlist)
		oldkeys = set(self._existing_keys())
		newkeys = attrset - oldkeys
		self._add(newkeys)
		log.debug("result: %s", ', '.join(self._existing_keys()))
		self._freeze()


	def _del(self, itemset):
		for item in itemset:
			log.debug("deleting attribute '%s'", item)
			delattr(self, item)


	def del_attributes(self, delattrlist):
		'''
		Delete attributes in delattrlist that are currently attributes.
		Ignore non-attribute entries in delattrlist.
		'''
		self._unfreeze()
		attrset = set(delattrlist)
		oldkeys = set(self._existing_keys())
		# Delete existing keys.
		delkeys = oldkeys & attrset
		self._del(delkeys)
		log.debug("result: %s", ', '.join(self._existing_keys()))
		self._freeze()


	# http://stackoverflow.com/questions/3137558/\
	# python-can-a-class-forbid-clients-setting-new-attributes
	def __setattr__(self, name, value):
	  	if not self.__is_frozen:
	  		return super(self.__class__, self).__setattr__(name, value)
	  	else:
			if hasattr(self, name):
				object.__setattr__(self, name, value)
			else:
			  raise TypeError('Cannot set name %r on object of type %s' % (
			                	name, self.__class__.__name__))