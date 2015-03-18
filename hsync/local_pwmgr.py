# Instrumented HTTPPasswordMgrWithDefaultRealm

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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import logging
import urllib2

log = logging.getLogger()


class InstrumentedHTTPPassManager(urllib2.HTTPPasswordMgrWithDefaultRealm,
                                  object):
    '''
    Instrumented wrapper around urllib2.HTTPPasswordMgrWithDefaultRealm.

    Simply upcall the base object with helpful log.debug() calls.

    In Python 2, the base class is old-style, so we need the object
    multiple-inheritance trick.
    '''

    def __init__(self):
        super(InstrumentedHTTPPassManager, self).__init__()
        log.debug("InstrumentedHTTPPassManager:__init__()")

    def add_password(self, realm, uri, user, password):
        log.debug("InstrumentedHTTPPassManager: add_password(): "
                  "realm '%s' uri '%s' user '%s' password '%s'",
                  realm, uri, user, password)
        super(InstrumentedHTTPPassManager, self).add_password(
            realm, uri, user, password)

    def find_user_password(self, realm, authuri):
        (user, password) = \
            super(InstrumentedHTTPPassManager, self).find_user_password(
                realm, authuri)
        log.debug("Instrumented)HTTPPassManager: "
                  "(%s, %s) = find_user_password('%s', '%s')",
                  user, password, realm, authuri)
        return (user, password)
