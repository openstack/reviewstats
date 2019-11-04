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


import argparse
import calendar
import csv
import datetime
import getpass
import prettytable
import sys

from reviewstats import utils


# NOTE(russellb) This data is tracked but not currently put in the
# output because it needs to be made more accurate.  Right now trivial
# rebases that have reviews automatically re-applied get included, and
# they shouldn't be.
ENABLE_RECEIVED = False


def round_to_day(ts):
    SECONDS_PER_DAY = 60 * 60 * 24
    return (ts / (SECONDS_PER_DAY)) * SECONDS_PER_DAY


def set_defaults(reviewer, reviewers):
    reviewers.setdefault(
        reviewer, {'votes': {'-2': 0, '-1': 0, '1': 0, '2': 0, 'A': 0}})
    reviewers[reviewer].setdefault('disagreements', 0)
    reviewers[reviewer].setdefault('total', 0)
    reviewers[reviewer].setdefault('received', 0)


def process_patchset(project, patchset, reviewers, ts, options):
    latest_core_neg_vote = 0
    latest_core_pos_vote = 0

    submitter = patchset['uploader'].get('username', 'unknown')
    core_team = utils.get_core_team(project, options.server, options.user,
        options.password)

    for review in patchset.get('approvals', []):
        if review['type'] != 'Code-Review':
            # Only count code reviews.  Don't add another for Approved, which
            # is type 'Approved' or 'Workflow'
            continue
        if review['by'].get('username', 'unknown') not in core_team:
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

        if review['type'] not in ('Code-Review', 'Approved', 'Workflow'):
            continue

        reviewer = review['by'].get('username', 'unknown')
        set_defaults(reviewer, reviewers)

        if (review['type'] == 'Approved' or
                (review['type'] == 'Workflow' and int(review['value']) > 0)):
            cur = reviewers[reviewer]['votes']['A']
            reviewers[reviewer]['votes']['A'] = cur + 1
        elif review['type'] != 'Workflow':
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


def write_csv(reviewer_data, file_obj, options, reviewers, projects,
              totals, change_stats):
    """Write out reviewers using CSV."""
    writer = csv.writer(file_obj)
    row = ['Reviewer', 'Reviews', '-2', '-1', '+1', '+2', '+A', '+/- %',
         'Disagreements', 'Disagreement%']
    if ENABLE_RECEIVED:
        row.append('Received')
    writer.writerow(row)
    for i, (name, r_data, d_data, s_data) in enumerate(reviewer_data, start=1):
        row = [name, r_data, d_data]
        if ENABLE_RECEIVED:
            row.append(s_data)
        writer.writerow(row)
        if options.csv_rows and i == options.csv_rows:
            break


def write_pretty(reviewer_data, file_obj, options, reviewers, projects,
                 totals, change_stats):
    """Write out reviewers using PrettyTable."""

    file_obj.write(str(datetime.datetime.utcnow()) + '\n\n')

    if options.all:
        file_obj.write(
            'Reviews for the last %d days in projects: %s\n' %
            (options.days, [project['name'] for project in projects]))
    else:
        project_name = projects[0]['name']
        if options.stable:
            # Handle the wildcare case.
            if options.stable.strip() == 'all':
                project_name = 'all open stable branches'
            else:
                project_name = "stable/%s" % (options.stable)
        file_obj.write(
            'Reviews for the last %d days in %s\n'
            % (options.days, project_name))
    if options.all:
        file_obj.write(
            '** -- Member of at least one core reviewer team\n')
    else:
        file_obj.write(
            '** -- %s-core team member\n' % projects[0]['name'])

    columns = ['Reviewer',
               'Reviews   -2  -1  +1  +2  +A    +/- %',
               'Disagreements*']
    if ENABLE_RECEIVED:
        columns.append('Received***')
    table = prettytable.PrettyTable(columns)
    for (name, r_data, d_data, s_data) in reviewer_data:
        r = '%7d  %3d %3d %3d %3d %3d   %s' % r_data
        d = '%3d (%s)' % d_data
        s = '%3d (%s)' % s_data
        row = [name, r, d]
        if ENABLE_RECEIVED:
            row.append(s)
        table.add_row(row)
    file_obj.write("%s\n" % table)

    file_obj.write(
        '\nTotal reviews: %d (%.1f/day)\n' % (
            totals['all'], float(totals['all']) / options.days))
    num_reviewers = len([rev for rev in reviewers if rev[0]['total']])
    file_obj.write(
        'Total reviewers: %d (avg %.1f reviews/day)\n' % (
            num_reviewers,
            float(totals['all']) / options.days / num_reviewers
            if num_reviewers else 0))
    file_obj.write('Total reviews by core team: %d (%.1f/day)\n' % (
        totals['core'], float(totals['core']) / options.days))
    core_team_size = sum([len(utils.get_core_team(project, options.server,
        options.user, options.password))
                          for project in projects])
    file_obj.write('Core team size: %d (avg %.1f reviews/day)\n' % (
                   core_team_size,
                   (float(totals['core']) / options.days / core_team_size) if
                   core_team_size else 0))
    file_obj.write(
        'New patch sets in the last %d days: %d (%.1f/day)\n'
        % (options.days, change_stats['patches'],
           float(change_stats['patches']) / options.days))
    file_obj.write(
        'Changes involved in the last %d days: %d (%.1f/day)\n'
        % (options.days, change_stats['involved'],
           float(change_stats['involved']) / options.days))
    file_obj.write(
        '  New changes in the last %d days: %d (%.1f/day)\n'
        % (options.days, change_stats['created'],
           float(change_stats['created']) / options.days))
    file_obj.write(
        '  Changes merged in the last %d days: %d (%.1f/day)\n'
        % (options.days, change_stats['merged'],
           float(change_stats['merged']) / options.days))
    file_obj.write(
        '  Changes abandoned in the last %d days: %d (%.1f/day)\n'
        % (options.days, change_stats['abandoned'],
           float(change_stats['abandoned']) / options.days))
    file_obj.write(
        ('  Changes left in state WIP in the last %d days: %d '
         '(%.1f/day)\n')
        % (options.days, change_stats['wip'],
           float(change_stats['wip']) / options.days))
    queue_growth = (change_stats['created'] - change_stats['merged'] -
                    change_stats['abandoned'] - change_stats['wip'])
    file_obj.write(
        ('  Queue growth in the last %d days: %d '
         '(%.1f/day)\n')
        % (options.days, queue_growth,
           float(queue_growth) / options.days))
    file_obj.write(
        '  Average number of patches per changeset: %.1f\n'
        % (float(change_stats['patches']) / change_stats['involved']
           if change_stats['involved'] else 0))
    file_obj.write(
        '\n(*) Disagreements are defined as a +1 or +2 vote on a '
        'patch where a core team member later gave a -1 or -2 vote'
        ', or a negative vote overridden with a positive one '
        'afterwards.\n')
    if ENABLE_RECEIVED:
        file_obj.write(
            '\n(***) Received - number of reviews that this person '
            'received on their patches in this time period. The given '
            'ratio is the number of reviews given over the number '
            'received.\n')


def main(argv=None):
    if argv is None:
        argv = sys.argv

    optparser = argparse.ArgumentParser()
    optparser.add_argument(
        '-p', '--project', default='projects/nova.json',
        help='JSON file describing the project to generate stats for')
    optparser.add_argument(
        '-a', '--all', action='store_true', default=False,
        help='Generate stats across all known projects (*.json)')
    optparser.add_argument(
        '-s', '--stable', default='', metavar='BRANCH',
        help='Generate stats for the specified stable BRANCH ("havana") '
             'across all integrated projects. Specify "all" for all '
             'open stable branches.')
    optparser.add_argument(
        '-o', '--output', default='-',
        help='Where to write output. If - stdout is used and only one output '
             'format may be given. Otherwise the output format is appended to '
             'the output parameter to generate file names.')
    optparser.add_argument(
        '--outputs', default=['txt'], action='append',
        help='Select what outputs to generate. (txt,csv).')
    optparser.add_argument(
        '-d', '--days', type=int, default=14,
        help='Number of days to consider')
    optparser.add_argument(
        '-u', '--user', default=getpass.getuser(), help='gerrit user')
    optparser.add_argument(
        '-P', '--password', default=getpass.getuser(),
        help='gerrit HTTP password')
    optparser.add_argument(
        '-k', '--key', default=None, help='ssh key for gerrit')
    optparser.add_argument(
        '-r', '--csv-rows', default=0, help='Max rows for CSV output',
        type=int)
    optparser.add_argument(
        '--server', default='review.opendev.org',
        help='Gerrit server to connect to')

    options = optparser.parse_args()

    if options.stable:
        projects = utils.get_projects_info('projects/stable.json', False)
    else:
        projects = utils.get_projects_info(options.project, options.all)

    if not projects:
        print("Please specify a project.")
        sys.exit(1)

    reviewers = {}

    now = datetime.datetime.utcnow()
    cut_off = now - datetime.timedelta(days=options.days)
    ts = calendar.timegm(cut_off.timetuple())
    now_ts = calendar.timegm(now.timetuple())

    change_stats = {
        'patches': 0,
        'created': 0,
        'involved': 0,
        'merged': 0,
        'abandoned': 0,
        'wip': 0,
    }

    for project in projects:
        changes = utils.get_changes([project], options.user, options.key,
                                    stable=options.stable,
                                    server=options.server)
        for change in changes:
            patch_for_change = False
            first_patchset = True
            for patchset in change.get('patchSets', []):
                process_patchset(project, patchset, reviewers, ts, options)
                age = utils.get_age_of_patch(patchset, now_ts)
                if (now_ts - age) > ts:
                    change_stats['patches'] += 1
                    patch_for_change = True
                    if first_patchset:
                        change_stats['created'] += 1
                first_patchset = False
            if patch_for_change:
                change_stats['involved'] += 1
                if change['status'] == 'MERGED':
                    change_stats['merged'] += 1
                elif change['status'] == 'ABANDONED':
                    change_stats['abandoned'] += 1
                elif change['status'] == 'WORKINPROGRESS':
                    change_stats['wip'] += 1

    reviewers = [(v, k) for k, v in reviewers.iteritems()
                 if k.lower() not in ('jenkins', 'smokestack')]
    reviewers.sort(reverse=True, key=lambda r: r[0]['total'])
    # Do logical processing of reviewers.
    reviewer_data = []
    totals = {
        'all': 0,
        'core': 0,
    }
    for k, v in reviewers:
        in_core_team = False
        for project in projects:
            if v in utils.get_core_team(project, options.server, options.user,
                    options.password):
                in_core_team = True
                break
        name = '%s%s' % (v, ' **' if in_core_team else '')
        plus = float(k['votes']['2'] + k['votes']['1'])
        minus = float(k['votes']['-2'] + k['votes']['-1'])
        all_reviews = plus + minus
        ratio = ((plus / (all_reviews)) * 100) if all_reviews > 0 else 0
        r = (k['total'], k['votes']['-2'],
             k['votes']['-1'], k['votes']['1'],
             k['votes']['2'], k['votes']['A'], "%5.1f%%" % ratio)
        dratio = (((float(k['disagreements']) / all_reviews) * 100)
                  if all_reviews else 0.0)
        d = (k['disagreements'], "%5.1f%%" % dratio)
        sratio = ((float(k['total']) / k['received']) * 100
                  if k['received'] else 0)
        s = (k['received'], "%5.1f%%" % sratio if k['received'] else 'inf')
        reviewer_data.append((name, r, d, s))
        totals['all'] += k['total']
        if in_core_team:
            totals['core'] += k['total']
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
            writer(reviewer_data, file_obj, options, reviewers, projects,
                   totals, change_stats)
        finally:
            if on_done:
                on_done()
    return 0
