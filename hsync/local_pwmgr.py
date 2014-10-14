# Instrumented HTTPPasswordMgrWithDefaultRealm

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

    def find_password(self, realm, authuri):
        (user, password) = \
            super(InstrumentedHTTPPassManager, self).find_password(
                realm, authuri)
        log.debug("Instrumented)HTTPPassManager: "
                  "(%s, %s) = find_password('%s', '%s')",
                  user, password, realm, authuri)
        return (user, password)
