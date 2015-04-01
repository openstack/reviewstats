===========
reviewstats
===========

Utility scripts for generating stats about OpenStack development.

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/reviewstats

Features
--------

* `openreviews.py` - Get some stats on the number and age of open reviews.
* `reviewers.py` - See how many reviews each person has done over a period of time.

Usage
-----

Clone the git repository, then install the library::

    pip install .

Run the scripts.

Project definitions
-------------------

Each project has a JSON file describing what reviews, bugs and so on will count
towards that projects statistics. The JSON file should have a single top level
object containing the following keys:

* name: The project name.
* subprojects: A list of Gerrit projects to include.
* core-team: A list of Gerrit usernames to consider as core reviewers across
  subprojects.
* lp_projects: A list of Launchpad project ids to include.
