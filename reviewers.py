#!/usr/bin/env python
# -*- coding: utf-8 -*-
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
import csv
import datetime
import getpass
import optparse
import prettytable
import sys

import utils


def round_to_day(ts):
    SECONDS_PER_DAY = 60*60*24
    return (ts / (SECONDS_PER_DAY)) * SECONDS_PER_DAY


def set_defaults(reviewer, reviewers):
    reviewers.setdefault(
        reviewer, {'votes': {'-2': 0, '-1': 0, '1': 0, '2': 0, 'A': 0}})
    reviewers[reviewer].setdefault('disagreements', 0)
    reviewers[reviewer].setdefault('total', 0)
    reviewers[reviewer].setdefault('received', 0)


def process_patchset(project, patchset, reviewers, ts):
    latest_core_neg_vote = 0
    latest_core_pos_vote = 0

    submitter = patchset['uploader'].get('username', 'unknown')

    for review in patchset.get('approvals', []):
        if review['type'] != 'CRVW':
            # Only count code reviews.  Don't add another for Approved, which
            # is type 'APRV'
            continue
        if review['by'].get('username', 'unknown') not in project['core-team']:
            # Only checking for disagreements from core team members
            continue
        if int(review['value']) > 0:
            latest_core_pos_vote = max(latest_core_pos_vote,
                                       int(review['grantedOn']))
        else:
            latest_core_neg_vote = max(latest_core_neg_vote,
                                       int(review['grantedOn']))

    for review in patchset.get('approvals', []):
        if review['grantedOn'] < ts:
            continue

        if review['type'] not in ('CRVW', 'APRV'):
            continue

        reviewer = review['by'].get('username', 'unknown')
        set_defaults(reviewer, reviewers)

        if review['type'] == 'APRV':
            cur = reviewers[reviewer]['votes']['A']
            reviewers[reviewer]['votes']['A'] = cur + 1
        else:
            cur_total = reviewers[reviewer].get('total', 0)
            reviewers[reviewer]['total'] = cur_total + 1
            set_defaults(submitter, reviewers)
            reviewers[submitter]['received'] += 1
            cur = reviewers[reviewer]['votes'][review['value']]
            reviewers[reviewer]['votes'][review['value']] = cur + 1
            if (review['value'] in ('1', '2')
                    and int(review['grantedOn']) < latest_core_neg_vote):
                # A core team member gave a negative vote after this person
                # gave a positive one
                cur = reviewers[reviewer]['disagreements']
                reviewers[reviewer]['disagreements'] = cur + 1
            if (review['value'] in ('-1', '-2')
                    and int(review['grantedOn']) < latest_core_pos_vote):
                # A core team member gave a positive vote after this person
                # gave a negative one
                cur = reviewers[reviewer]['disagreements']
                reviewers[reviewer]['disagreements'] = cur + 1


def write_csv(reviewer_data, file_obj):
    """Write out reviewers using CSV."""
    writer = csv.writer(file_obj)
    writer.writerow(
        ('Reviewer', 'Reviews', '-2', '-1', '+1', '+2', '+A', '+/- %',
         'Disagreements', 'Disagreement%', 'Received'))
    for (name, r_data, d_data, s_data) in reviewer_data:
        row = (name,) + r_data + d_data + s_data
        writer.writerow(row)


def write_pretty(reviewer_data, file_obj):
    """Write out reviewers using PrettyTable."""
    table = prettytable.PrettyTable(
        ('Reviewer',
         'Reviews   -2  -1  +1  +2  +A    +/- %',
         'Disagreements*',
         'Received***'))
    for (name, r_data, d_data, s_data) in reviewer_data:
        r = '%7d  %3d %3d %3d %3d %3d   %s' % r_data
        d = '%3d (%s)' % d_data
        s = '%3d (%s)' % s_data
        table.add_row((name, r, d, s))
    file_obj.write("%s\n" % table)


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
        '-o', '--output', default='-',
        help='Where to write output. If - stdout is used and only one output'
            'format may be given. Otherwise the output format is appended to'
            'the output parameter to generate file names.')
    optparser.add_option(
        '--outputs', default=['txt'], action='append',
        help='Select what outputs to generate. (txt,csv).')
    optparser.add_option(
        '-d', '--days', type='int', default=14,
        help='Number of days to consider')
    optparser.add_option(
        '-u', '--user', default=getpass.getuser(), help='gerrit user')
    optparser.add_option(
        '-k', '--key', default=None, help='ssh key for gerrit')

    options, args = optparser.parse_args()

    projects = utils.get_projects_info(options.project, options.all)

    if not projects:
        print "Please specify a project."
        sys.exit(1)

    reviewers = {}

    now = datetime.datetime.utcnow()
    cut_off = now - datetime.timedelta(days=options.days)
    ts = calendar.timegm(cut_off.timetuple())
    now_ts = calendar.timegm(now.timetuple())

    patches_created = 0

    for project in projects:
        changes = utils.get_changes([project], options.user, options.key)
        for change in changes:
            for patchset in change.get('patchSets', []):
                process_patchset(project, patchset, reviewers, ts)
                age = utils.get_age_of_patch(patchset, now_ts)
                if (now_ts - age) > ts:
                    patches_created += 1

    reviewers = [(v, k) for k, v in reviewers.iteritems()
                 if k.lower() not in ('jenkins', 'smokestack')]
    reviewers.sort(reverse=True, key=lambda r: r[0]['total'])
    # Do logical processing of reviewers.
    reviewer_data = []
    total = 0
    core_total = 0
    for k, v in reviewers:
        in_core_team = False
        for project in projects:
            if v in project['core-team']:
                in_core_team = True
                break
        name = '%s%s' % (v, ' **' if in_core_team else '')
        plus = float(k['votes']['2'] + k['votes']['1'])
        minus = float(k['votes']['-2'] + k['votes']['-1'])
        ratio = ((plus / (plus + minus)) * 100) if plus + minus > 0 else 0
        r = (k['total'], k['votes']['-2'],
            k['votes']['-1'], k['votes']['1'],
            k['votes']['2'], k['votes']['A'], "%5.1f%%" % ratio)
        dratio = ((float(k['disagreements']) / plus) * 100) if plus else 0.0
        d = (k['disagreements'], "%5.1f%%" % dratio)
        sratio = ((float(k['total']) / k['received']) * 100
                  if k['received'] else 0)
        s = (k['received'], "%5.1f%%" % sratio if k['received'] else '∞')
        reviewer_data.append((name, r, d, s))
        total += k['total']
        if in_core_team:
            core_total += k['total']
    # And output.
    writers = {
        'csv': write_csv,
        'txt': write_pretty,
        }
    if options.output == '-':
        if len(options.outputs) != 1:
            raise Exception("Can only output one format to stdout.")
    for output in options.outputs:
        if options.output == '-':
            file_obj = sys.stdout
            on_done = None
        else:
            file_obj = open(options.output + '.' + output, 'wt')
            on_done = file_obj.close
        try:
            writer = writers[output]
            if options.all:
                file_obj.write(
                    'Reviews for the last %d days in projects: %s\n' %
                    (options.days, [project['name'] for project in projects]))
            else:
                file_obj.write('Reviews for the last %d days in %s\n'
                    % (options.days, projects[0]['name']))
            if options.all:
                file_obj.write(
                    '** -- Member of at least one core reviewer team\n')
            else:
                file_obj.write(
                    '** -- %s-core team member\n' % projects[0]['name'])
            writer(reviewer_data, file_obj)
            file_obj.write('\nTotal reviews: %d (%.1f/day)\n' % (total,
                float(total) / options.days))
            file_obj.write('Total reviewers: %d\n' % len(reviewers))
            file_obj.write('Total reviews by core team: %d (%.1f/day)\n' % (
                core_total, float(core_total) / options.days))
            file_obj.write('Core team size: %d\n' % len(project['core-team']))
            file_obj.write(
                'New patch sets in the last %d days: %d (%.1f/day)\n'
                % (options.days, patches_created,
                   float(patches_created) / options.days))
            file_obj.write(
                '\n(*) Disagreements are defined as a +1 or +2 vote on a ' \
                'patch where a core team member later gave a -1 or -2 vote' \
                ', or a negative vote overridden with a positive one ' \
                'afterwards.\n')
            file_obj.write(
                '\n(***) Received - the number of reviews that this person '
                'received on their patches in this time period. The given '
                'ratio is the number of reviews given over the number '
                'received.\n')

        finally:
            if on_done:
                on_done()
    return 0


if __name__ == '__main__':
    sys.exit(main())
