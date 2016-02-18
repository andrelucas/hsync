# Hashlist implemetation.

# Copyright (c) 2015, Andre Lucas
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function

from exceptions import *
from filehash import FileHash
import logging

log = logging.getLogger()


class HashList(object):
    '''
    A memory-backed list of objects. Fast, but requires that all the objects
    and their collections to fit in memory.
    '''

    def __init__(self,
                 warn_on_duplicates=True, raise_on_duplicates=True,
                 delete_on_close=True):
        log.debug("Hashlist __init__()")

        self.warn_on_duplicates = warn_on_duplicates
        self.raise_on_duplicates = raise_on_duplicates
        self.write_count = 0
        self.write_total = 0
        self.read_total = 0
        self.storage_init()

    def storage_init(self):
        log.debug("HashList _storage_init()")
        self.list = []
        self.dup_detect = set()

    def close(self, want_sync=False):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("HashList.close() total reads %i writes %i",
                      self.read_total, self.write_total)

        # No point doing a commit if we're about to delete.
        if want_sync:
            self.sync()

    def __del__(self):
        self.close()
        log.debug("HashList: Final exit")

    def sync(self):
        pass

    def _assert_filehash(self, fh):
        '''Raise NotAFileHashError unless fh is a FileHash'''
        if type(fh) is not FileHash:
            raise NotAFileHashError()

    def write_increment(self):
        self.write_count += 1
        self.write_total += 1

    def _insert(self, fh):
        '''Insert the given filehash into the database.'''
        self.list.append(fh)

    def append(self, fh):
        '''
        Add a FileHash object to the store. Raise a NotAFileHashError
        if anything other than a FileHash is offered.
        '''
        self._assert_filehash(fh)
        strhash = fh.strhash()

        if log.isEnabledFor(logging.DEBUG):
            log.debug("HashList.append('%s') cursize %i", fh, len(self))

        if self.raise_on_duplicates or self.warn_on_duplicates:
            if strhash in self.dup_detect:
                if self.raise_on_duplicates:
                    raise DuplicateEntryInHashListError()
                if self.warn_on_duplicates:
                    log.warning("Duplicate entry for hash '%s' in HashList",
                                strhash)
            self.dup_detect.add(strhash)

        self.list.append(fh)
        self.write_increment()

    def extend(self, fhlist):
        '''
        Add a list of FileHash objects to the store. Calls append() on each
        item.
        '''
        for fh in fhlist:
            self.append(fh)

    def __len__(self):
        return len(self.list)

    def __getitem__(self, index):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("HashList.__getitem__[%i]", index)
        self.read_total += 1
        return self.list[index]

    def __iter__(self):
        return self.list_generator()

    def list_generator(self):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("HashList.list_generator()")
        for fh in self.list:
            yield fh

    def sort_by_path(self):
        '''Sort the hashlist by the FileHash.fpath field.'''
        self.list.sort(key=lambda fh: fh.fpath)


class HashDict(object):
    '''
    A path-indexed lookup dict for a HashList.
    '''

    def __init__(self, hashlist=None):
        if hashlist is None or not isinstance(hashlist, HashList):
            log.error("HashDict() must be initialised with a HashList")
            raise InitialiserNotAHashListError()

        self.hl = hashlist
        self.hd = {}
        self._dict_from_list()

    def _dict_from_list(self):
        if log.isEnabledFor(logging.DEBUG):
            log.debug("HashDict._dict_from_list()")

        for n, fh in enumerate(self.hl):
            self.hd[fh.fpath] = n

    def __getitem__(self, key):
        if key is None or key == '':
            raise KeyError()

        fh = self.hl[self.hd[key]]
        # if log.isEnabledFor(logging.DEBUG):
        #     log.debug("XXX HashDict.__getitem__[%s]: %s", key, fh)
        return fh

    def __contains__(self, key):
        return key in self.hd

    def __setitem__(self, key, value):
        raise KeyError("HashDict does not allow direct writes")

    def __iter__(self):
        # if log.isEnabledFor(logging.DEBUG):
        #     log.debug("XXX HashDict.__iter__()")
        for k in self.hd.iterkeys():
            # log.debug("XXX HashDict.__iter__() pre-yield:")
            # self._dumpframe()
            yield k

    def keys(self):
        return self.keys_gen()

    def iterkeys(self):
        return self.keys_gen()

    def keys_gen(self):
        for k in self.hd.iterkeys():
            yield k

    def items(self):
        return self.items_gen()

    def iteritems(self):
        return self.items_gen()

    def items_gen(self):
        for k, v in self.hd.iteritems():
            yield k, self[k]
