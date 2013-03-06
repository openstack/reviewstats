#!/usr/bin/python
#
# Copyright (C) 2011 - Soren Hansen
# Copyright (C) 2013 - Red Hat, Inc.

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
import cPickle as pickle
import datetime
import json
import optparse
import os
import os.path
import paramiko
from pprint import pprint
import prettytable
import sys
import time


CACHE_AGE = 3600  # Seconds

CLIENT_MAP = {
    'python-novaclient': 'nova',
}


optparser = optparse.OptionParser()
optparser.add_option('-p', '--project', default='nova',
        help='Project to generate stats for')
optparser.add_option('-d', '--days', type='int', default=14,
        help='Number of days to consider')
optparser.add_option('-u', '--user', default='russellb', help='gerrit user')
optparser.add_option('-k', '--key', default=None, help='ssh key for gerrit')

options, args = optparser.parse_args()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.load_system_host_keys()


changes = []

pickle_fn = '%s-changes.pickle' % options.project

if os.path.isfile(pickle_fn):
    mtime = os.stat(pickle_fn).st_mtime
    if (time.time() - mtime) <= CACHE_AGE:
        with open(pickle_fn, 'r') as f:
            changes = pickle.load(f)

if len(changes) == 0:
    while True:
        client.connect('review.openstack.org', port=29418,
                key_filename=options.key, username=options.user)
        cmd = ('gerrit query project:openstack/%s '
               '--all-approvals --patch-sets --format JSON' % options.project)
        if len(changes) > 0:
            cmd += ' resume_sortkey:%s' % changes[-2]['sortKey']
        stdin, stdout, stderr = client.exec_command(cmd)
        for l in stdout:
            changes += [json.loads(l)]
        if changes[-1]['rowCount'] == 0:
            break

    with open(pickle_fn, 'w') as f:
        pickle.dump(changes, f)


reviews = []

for change in changes:
#    print json.dumps(change, sort_keys=True, indent=4)
    for patchset in change.get('patchSets', []):
        for review in patchset.get('approvals', []):
            reviews += [review]

cut_off = datetime.datetime.now() - datetime.timedelta(days=options.days)
ts = calendar.timegm(cut_off.timetuple())
reviews = filter(lambda x:x['grantedOn'] > ts, reviews)

def round_to_day(ts):
    SECONDS_PER_DAY = 60*60*24
    return (ts / (SECONDS_PER_DAY)) * SECONDS_PER_DAY

reviewers = {}
for review in reviews:
    if review['type'] != 'CRVW':
        # Only count code reviews.  Don't add another for Approved, which is
        # type 'APRV'
        continue

    reviewer = review['by'].get('username', 'unknown')
    reviewers.setdefault(reviewer,
            {'votes': {'-2': 0, '-1': 0, '1': 0, '2': 0}})
    reviewers[reviewer]['total'] = reviewers[reviewer].get('total', 0) + 1
    cur = reviewers[reviewer]['votes'][review['value']]
    reviewers[reviewer]['votes'][review['value']] = cur + 1

#print json.dumps(reviewers, sort_keys=True, indent=4)

reviewers = [(v, k) for k, v in reviewers.iteritems()
             if k.lower() not in ('jenkins', 'smokestack')]
reviewers.sort(reverse=True)

core_team = []
core_team_name = CLIENT_MAP.get(options.project, options.project)
core_team_fn = '%s-core-team.json' % core_team_name
if os.path.isfile(core_team_fn):
    with open(core_team_fn, 'r') as f:
        core_team = json.loads(f.read())

print 'Reviews for the last %d days in %s' % (options.days, options.project)
print '** -- %s-core team member' % core_team_name
table = prettytable.PrettyTable(('Reviewer', 'Reviews (-2|-1|+1|+2)'))
total = 0
for k, v in reviewers:
    name = '%s%s' % (v, ' **' if v in core_team else '')
    r = '%d (%d|%d|%d|%d)' % (k['total'],
            k['votes']['-2'], k['votes']['-1'],
            k['votes']['1'], k['votes']['2'])
    table.add_row((name, r))
    total += k['total']
print table
print '\nTotal reviews: %d' % total
