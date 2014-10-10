#!/usr/bin/env python


class DirWhereFileExpectedError(Exception):
    pass


class OSOperationFailedError(Exception):
    pass


class ParanoiaError(Exception):
    pass


class ObjectInTheWayError(Exception):
    pass


class NonDirFoundAtDirLocationError(ObjectInTheWayError):
    pass


class NonLinkFoundAtLinkLocationError(ObjectInTheWayError):
    pass


class TruncatedHashfileError(Exception):
    pass


class URLMustBeOfTypeFileError(Exception):
    pass


class ContentsFetchFailedError(Exception):
    pass


class CommandLineArgumentsError(Exception):
    pass


class UnexpectedArgumentsError(CommandLineArgumentsError):
    pass

# lockfile.py


class NotADirectoryError(OSError):
    pass
