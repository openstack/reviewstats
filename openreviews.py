#!/usr/bin/python
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

import calendar
import datetime
import optparse
import os
import os.path
import sys

import utils


optparser = optparse.OptionParser()
optparser.add_option('-p', '--project', default='nova.json',
        help='JSON file describing the project to generate stats for')
optparser.add_option('-a', '--all', action='store_true',
        help='Generate stats across all known projects (*.json)')
optparser.add_option('-u', '--user', default='russellb', help='gerrit user')
optparser.add_option('-k', '--key', default=None, help='ssh key for gerrit')

options, args = optparser.parse_args()

projects = utils.get_projects_info(options.project, options.all)

if not projects:
    print "Please specify a project."
    sys.exit(1)

changes = utils.get_changes(projects, options.user, options.key,
        only_open=True)

waiting_on_submitter = []
waiting_on_reviewer = []

now = datetime.datetime.utcnow()
now_ts = calendar.timegm(now.timetuple())

for change in changes:
    if 'rowCount' in change:
        continue
    latest_patch = change['patchSets'][-1]
    waiting_for_review = True
    for review in latest_patch.get('approvals', []):
        if review['type'] == 'CRVW' and (review['value'] != '-1' or
                                         review['value'] == '-2'):
            waiting_for_review = False
            break
    change['age'] = now_ts - latest_patch['createdOn']
    if waiting_for_review:
        waiting_on_reviewer.append(change)
    else:
        waiting_on_submitter.append(change)


def average_age(changes):
    total_seconds = 0
    for change in changes:
        total_seconds += change['age']
    avg_age = total_seconds / len(changes)
    days = avg_age / (3600 * 24)
    hours = (avg_age / 3600) - (days * 24)
    minutes = (avg_age / 60) - (days * 24 * 60) - (hours * 60)
    return '%d days, %d hours, %d minutes' % (days, hours, minutes)


print 'Projects: %s' % [project['name'] for project in projects]
print 'Total Open Reviews: %d' % (len(waiting_on_reviewer) +
        len(waiting_on_submitter))
print 'Waiting on Submitter: %d' % len(waiting_on_submitter)
print 'Waiting on Reviewer: %d' % len(waiting_on_reviewer)
print ' --> Average wait time: %s' % average_age(waiting_on_reviewer)
