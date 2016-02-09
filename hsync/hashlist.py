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

import logging
import shelve
import tempfile

from exceptions import *
from filehash import FileHash

log = logging.getLogger()


class HashList(object):
    '''
    A disk-backed list of objects. Used when there are far more objects
    than can be comfortably stored in memory.
    '''

    def __init__(self, warn_on_duplicates=True, raise_on_duplicates=True):
        log.debug("Hashlist __init__()")
        self.tmpd = tempfile.mkdtemp()  # XXX spec? test?
        self.tmpname = tempfile.mktemp("", "hashlist.", self.tmpd)
        log.debug("Hashlist: open shelve on '%s'", self.tmpname)
        self.shl = shelve.open(self.tmpname, 'n', 2)
        self.list = []
        self.warn_on_duplicates = warn_on_duplicates
        self.raise_on_duplicates = raise_on_duplicates

    def close(self):
        log.debug("HashList.close()")
        self.sync()
        self.shl.close()

    def sync(self):
        log.debug("HashList.sync()")
        self.shl.sync()

    def _assert_filehash(self, fh):
        '''Raise NotAFileHashError unless fh is a FileHash'''
        if type(fh) is not FileHash:
            raise NotAFileHashError()

    def append(self, fh):
        '''
        Add a FileHash object to the store. Raise a NotAFileHashError
        if anything other than a FileHash is offered.
        '''
        self._assert_filehash(fh)
        log.debug("HashList.append('%s')" % fh)
        strhash = fh.strhash()
        if self.raise_on_duplicates or self.warn_on_duplicates:
            if strhash in self.shl:
                if self.raise_on_duplicates:
                    raise DuplicateEntryInHashListError()
                if self.warn_on_duplicates:
                    log.warning("Duplicate entry '%s' in HashList", strhash)
        self.shl[strhash] = fh
        self.list.append(strhash)

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
        return self.shl[self.list[index]]

    def __iter__(self):
        return self.list_generator()

    def list_generator(self):
        for fh in self.list:
            yield self.shl[fh]
