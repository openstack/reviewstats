#!/bin/bash

projects=projects/*.json

if [ -n "${GERRIT_USER}" ] ; then
	EXTRA_ARGS="-u ${GERRIT_USER}"
fi

metadata() {
	date -u
	echo -n "reviewstats HEAD: "
	git rev-parse HEAD
	echo
}

for project in ${projects} ; do
	project_base=$(basename $(echo ${project} | cut -f1 -d'.'))
	(metadata && ./reviews_for_bugs.py -p ${project} ${EXTRA_ARGS}) > results/${project_base}-reviews-for-bugs.txt
done
