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
    gid_to_group = {}
    group_to_gid = {}

    missing_name_warned = set()
    missing_group_warned = set()
    missing_uid_warned = set()
    missing_gid_warned = set()

    default_uid = os.getuid()
    default_gid = os.getgid()

    # Let these throw KeyError - if we can't find our own username and group
    # given our own uid and gid, we're in bad shape.
    default_name = pwd.getpwuid(default_uid)
    default_group = grp.getgrgid(default_gid)
    

    def get_name_for_uid(self, uid):
        if not uid in self.uid_to_name:
            try:
                name = pwd.getpwuid(uid).pw_name
            except KeyError:
                if not name in self.missing_uid_warned:
                    log.warn("No name found for uid %d, setting "
                        "default username", uid)
                    self.missing_uid_warned.add(uid)
                    self.uid_to_name[uid] = self.default_name
                    return self.default_name

            self.uid_to_name[uid] = name
            self.name_to_uid[name]  = uid
        return self.uid_to_name[uid]

    
    def get_group_for_gid(self, gid):
        if not gid in self.gid_to_group:
            try:
                name = grp.getgrgid(gid).gr_name
            except KeyError:
                if not name in self.missing_gid_warned:
                    log.warn("No group found for gid %d, setting "
                        "default group", gid)
                    self.missing_gid_warned.add(gid)
                    self.gid_to_group[gid] = self.default_group
                    return self.default_group

            self.gid_to_group[gid] = name
            self.group_to_gid[name] = gid
        return self.gid_to_group[gid]


    def get_uid_for_name(self, name):
        if not name is self.name_to_uid:
            try:
                uid = int(pwd.getpwnam(name).pw_uid)
            except KeyError:
                if not name in self.missing_name_warned:
                    log.warn("No uid found for name %s, setting "
                        "default uid", name)
                    self.missing_name_warned.add(name)
                    self.name_to_uid[name] = self.default_uid
                    return self.default_uid

            self.name_to_uid[name] = uid
            self.uid_to_name[uid] = name

        return self.name_to_uid[name]


    def get_gid_for_group(self, group):
        if not group in self.group_to_gid:
            try:
                gid = int(grp.getgrnam(group).gr_gid)
            except KeyError:
                if not group in self.missing_group_warned:
                    log.warn("No gid found for group %s, setting "
                        "default gid", group)
                    self.missing_group_warned.add(group)
                    self.group_to_gid[group] = self.default_gid
                    return self.default_gid

            self.group_to_gid[group] = gid
            self.gid_to_group[gid] = group

        return self.group_to_gid[group]
