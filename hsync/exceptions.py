#!/usr/bin/env python

class DirWhereFileExpectedError(Exception): pass

class OSOperationFailedError(Exception): pass
class ParanoiaError(Exception): pass

class ObjectInTheWayError(Exception): pass
class NonDirFoundAtDirLocationError(ObjectInTheWayError): pass
class NonLinkFoundAtLinkLocationError(ObjectInTheWayError): pass

