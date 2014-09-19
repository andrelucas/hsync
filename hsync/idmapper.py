#!/usr/bin/env python

import grp
import logging
import os
import pwd

log = logging.getLogger()

class UidGidMapper(object):

    # These are all program-wide settings, and so suitable for class
    # attributes.
    #
    # (Ok, uid and gid can change; but this isn't really intended for
    # setuid operation.)

    uid_to_name = {}
    name_to_uid = {}
    gid_to_name = {}
    name_to_gid = {}

    missing_name_warned = set()
    missing_group_warned = set()

    default_uid = os.getuid()
    default_gid = os.getgid()
    

    def get_name_for_uid(self, uid):
        if not uid in self.uid_to_name:
            name = pwd.getpwuid(uid).pw_name
            self.uid_to_name[uid] = name
            self.name_to_uid[name]  = uid
        return self.uid_to_name[uid]

    
    def get_name_for_gid(self, gid):
        if not gid in self.gid_to_name:
            name = grp.getgrgid(gid).gr_name
            self.gid_to_name[gid] = name
            self.name_to_gid[name] = gid
        return self.gid_to_name[gid]


    def get_uid_for_name(self, name):
        if not name is self.name_to_uid:
            try:
                uid = int(pwd.getpwnam(name).pw_uid)
            except KeyError:
                if not name in self.missing_name_warned:
                    log.warn("No uid found for name %s", name)
                    self.missing_name_warned.add(name)
                    self.name_to_uid[name] = self.default_uid
                    return self.default_uid

            self.name_to_uid[name] = uid
            self.uid_to_name[uid] = name

        return self.name_to_uid[name]


    def get_gid_for_name(self, group):
        if not group in self.name_to_gid:
            try:
                gid = int(grp.getgrnam(group).gr_gid)
            except KeyError:
                if not group in self.missing_group_warned:
                    log.warn("No gid found for group %s", group)
                    self.missing_group_warned.add(group)
                    self.name_to_gid[group] = self.default_gid
                    return self.default_gid

            self.name_to_gid[group] = gid
            self.gid_to_name[gid] = group

        return self.name_to_gid[group]
