#!/usr/bin/python
import calendar
import datetime
import json
import optparse
import paramiko
from pprint import pprint
import sys


optparser = optparse.OptionParser()
optparser.add_option('-p', '--project', default='nova', help='Project to generate stats for')
optparser.add_option('-d', '--days', type='int', default=14, help='Number of days to consider')
optparser.add_option('-r', '--raw', action='store_true', default=False, help='Um... Hard to explain. Try it and see')

options, args = optparser.parse_args()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.load_system_host_keys()
client.connect('review.openstack.org', port=29418, key_filename='/home/soren/.ssh/statskey', username='usagestats')
stdin, stdout, stderr = client.exec_command('gerrit query project:openstack/%s --all-approvals --patch-sets --format JSON' % options.project)
changes = []
for l in stdout:
    changes += [json.loads(l)]

reviews = []

for change in changes:
#    print json.dumps(change, sort_keys=True, indent=4)
    for patchset in change.get('patchSets', []):
        for review in patchset.get('approvals', []):
            reviews += [review]

if not options.raw:
    cut_off = datetime.datetime.now() - datetime.timedelta(days=options.days)
    ts = calendar.timegm(cut_off.timetuple())
    reviews = filter(lambda x:x['grantedOn'] > ts, reviews)

def round_to_day(ts):
    SECONDS_PER_DAY = 60*60*24
    return (ts / (SECONDS_PER_DAY)) * SECONDS_PER_DAY

reviewers = {}
for review in reviews:
    reviewer = review['by'].get('username', 'unknown')
    if options.raw:
        if reviewer not in reviewers:
            reviewers[reviewer] = {}
        day = round_to_day(review['grantedOn'])
        reviewers[reviewer][day] = reviewers[reviewer].get(day, 0) + 1
    else:
        reviewers[reviewer] = reviewers.get(reviewer, 0) + 1

print json.dumps(reviewers, sort_keys=True, indent=4)
