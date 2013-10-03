#!/usr/bin/env python
#
# Copyright (C) 2011 - Soren Hansen
# Copyright (C) 2013 - Red Hat, Inc.
#

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Identify approved and open patches, that are probably just trivial rebases.

Prints out list of approved patches that failed to merge and are currently
still open. Only show patches that are likely to be trivial rebases.
"""

import getpass
import optparse
import sys

import utils


def main(argv=None):
    if argv is None:
        argv = sys.argv

    optparser = optparse.OptionParser()
    optparser.add_option(
        '-p', '--project', default='projects/nova.json',
        help='JSON file describing the project to generate stats for')
    optparser.add_option(
        '-a', '--all', action='store_true',
        help='Generate stats across all known projects (*.json)')
    optparser.add_option(
        '-u', '--user', default=getpass.getuser(), help='gerrit user')
    optparser.add_option(
        '-k', '--key', default=None, help='ssh key for gerrit')
    optparser.add_option('-s', '--stable', action='store_true',
                         help='Include stable branch commits')
    options, args = optparser.parse_args()

    projects = utils.get_projects_info(options.project, options.all)

    if not projects:
        print "Please specify a project."
        sys.exit(1)

    changes = utils.get_changes(projects, options.user, options.key,
                                only_open=True)

    approved_and_rebased = set()
    for change in changes:
        if 'rowCount' in change:
            continue
        if not options.stable and 'stable' in change['branch']:
            continue
        if change['status'] != 'NEW':
            # Filter out WORKINPROGRESS
            continue
        for patch_set in change['patchSets'][:-1]:
            if approved(patch_set) and not approved(change['patchSets'][-1]):
                if has_negative_feedback(change['patchSets'][-1]):
                    continue
                approved_and_rebased.add("%s %s" % (change['url'],
                                                    change['subject']))

    for x in approved_and_rebased:
        print x
    print "total %d" % len(approved_and_rebased)


def has_negative_feedback(patch_set):
    approvals = patch_set.get('approvals', [])
    for review in approvals:
        if review['type'] in ('CRVW', 'VRIF') \
                and review['value'] in ('-1', '-2'):
            return True
    return False


def approved(patch_set):
    approvals = patch_set.get('approvals', [])
    for review in approvals:
        if review['type'] == 'APRV':
            return True
    return False


if __name__ == '__main__':
    sys.exit(main())
