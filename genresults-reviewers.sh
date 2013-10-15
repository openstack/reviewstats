#!/bin/bash

projects=$1
all=0

if [ "$projects" = "" ] ; then
	projects=projects/*.json
	all=1
fi

mkdir -p results

rm -f results/*-reviewers-*

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
	for time in 30 60 90 180 ; do
		(metadata && ./reviewers.py -p ${project} -d ${time} ${EXTRA_ARGS}) -o results/${project_base}-reviewers-${time} --outputs txt --outputs csv
	done
done

if [ "${all}" = "1" ] ; then
	for time in 30 60 90 180 ; do
		(metadata && ./reviewers.py -a -d ${time} ${EXTRA_ARGS}) -o results/all-reviewers-${time} --outputs txt --outputs csv
	done
fi
