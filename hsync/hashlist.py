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

import cPickle
import logging
import os
import shutil
import sqlite3
import tempfile

from exceptions import *
from filehash import FileHash

log = logging.getLogger()


class HashList(object):
    '''
    A disk-backed list of objects. Used when there are far more objects
    than can be comfortably stored in memory.
    '''

    # Sync the database every so many writes. (XXX necessary for sqlite?)
    # force_sync_count = 100000

    def __init__(self,
                 warn_on_duplicates=True, raise_on_duplicates=True,
                 delete_on_close=True):
        log.debug("Hashlist __init__()")
        self.tmpd = tempfile.mkdtemp()  # XXX spec? test?
        self.tmpname = tempfile.mktemp("", "hashlist.", self.tmpd)
        log.debug("Hashlist: open sqlite3 database on '%s'", self.tmpname)
        self.dbconn = sqlite3.connect(self.tmpname)

        self.cur = self.dbconn.cursor()
        self.cur.execute("create table fh (hash str, blob blob)")
        self.cur.execute("create index fhindex on fh(hash)")

        self.list = []
        self.warn_on_duplicates = warn_on_duplicates
        self.raise_on_duplicates = raise_on_duplicates
        self.write_count = 0
        self.write_total = 0
        self.read_total = 0

    def close(self, want_sync=False):
        log.debug("HashList.close() total reads %i writes %i",
                  self.read_total, self.write_total)

        # No point doing a commit if we're about to delete.
        if want_sync:
            self.sync()

        self.cur = None
        if self.dbconn is not None:
            self.dbconn.close()
        self.dbconn = None

    def __del__(self):
        self.close()
        log.debug("HashList.__del__(): removing filesystem objects")
        try:
            os.unlink(self.tmpname)
        except OSError:
            pass  # Don't care if it fails.

        shutil.rmtree(self.tmpd, True)  # Don't care if this fails either.
        log.debug("HashList: Final exit")

    def sync(self):
        log.debug("HashList.sync()")
        self.dbconn.commit()

    def _assert_filehash(self, fh):
        '''Raise NotAFileHashError unless fh is a FileHash'''
        if type(fh) is not FileHash:
            raise NotAFileHashError()

    def write_increment(self):
        self.write_count += 1
        self.write_total += 1
        # if self.write_count >= self.force_sync_count:
        #     log.debug("HashList: sync() after %i writes", self.write_count)
        #     self.sync()
        #     self.write_count = 0

    def _insert(self, fh):
        '''Insert the given filehash into the database.'''
        pdata = cPickle.dumps(fh, cPickle.HIGHEST_PROTOCOL)
        self.cur.execute('insert into fh (hash, blob) values (:hs, :blob)',
                         {"hs": fh.strhash(), "blob": sqlite3.Binary(pdata)})

    def _fetch(self, hashstr):
        '''Retrieve filehashes with the given hashstr.'''
        self.cur.execute('select (blob) from fh where hash = :hs',
                         {"hs": hashstr})
        fhlist = []
        for row in self.cur:
            fhlist.append(cPickle.loads(str(row[0])))

        return fhlist

    def append(self, fh):
        '''
        Add a FileHash object to the store. Raise a NotAFileHashError
        if anything other than a FileHash is offered.
        '''
        self._assert_filehash(fh)
        log.debug("HashList.append('%s') cursize %i", fh, len(self))
        strhash = fh.strhash()
        if self.raise_on_duplicates or self.warn_on_duplicates:
            fhl = self._fetch(strhash)
            if len(fhl) > 0:
                if self.raise_on_duplicates:
                    raise DuplicateEntryInHashListError()
                if self.warn_on_duplicates:
                    log.warning("Duplicate entry for hash '%s' in HashList",
                                strhash)

        self._insert(fh)
        self.list.append(strhash)
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
        log.debug("HashList.__getitem__[%i]", index)
        self.read_total += 1
        fh = self._fetch(self.list[index])
        return fh[0]

    def __iter__(self):
        return self.list_generator()

    def list_generator(self):
        log.debug("HashList.list_generator()")
        for hashstr in self.list:
            yield self._fetch(hashstr)[0]

    def sort_by_path(self):
        '''Sort the hashlist by the FileHash.fpath field.'''
        self.list.sort(key=lambda hashstr: self._fetch(hashstr)[0].fpath)
