#!/bin/bash

projects=projects/*.json

if [ -n "${GERRIT_USER}" ] ; then
	EXTRA_ARGS="-u ${GERRIT_USER}"
fi

if [ -n "${GERRIT_KEY}" ] ; then
	EXTRA_ARGS="${EXTRA_ARGS} -k ${GERRIT_KEY}"
fi

if [ -n "${GERRIT_SERVER}" ] ; then
	EXTRA_ARGS="${EXTRA_ARGS} --server ${GERRIT_SERVER}"
fi

metadata() {
	date -u
	echo -n "reviewstats HEAD: "
	git rev-parse HEAD
	echo
}

for project in ${projects} ; do
	project_base=$(basename $(echo ${project} | cut -f1 -d'.'))
	(metadata && reviews_for_bugs -p ${project} ${EXTRA_ARGS}) > results/${project_base}-reviews-for-bugs.txt
done
