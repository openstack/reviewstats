#!/bin/bash

projects=$1
all=0

if [ "$projects" = "" ] ; then
	projects=*.json
	all=1
fi

mkdir -p results

for project in ${projects} ; do
	project_base=$(echo ${project} | cut -f1 -d'.')
	(date -u && echo && ./openreviews.py -p ${project}) > results/${project_base}-openreviews.txt
	for time in 30 90 180 ; do
		(date -u && echo && ./reviewers.py -p ${project} -d ${time}) > results/${project_base}-reviewers-${time}.txt
	done
done

if [ "${all}" = "1" ] ; then
	(date -u && echo && ./openreviews.py -a) > results/all-openreviews.txt

	for time in 30 90 180 ; do
		(date -u && echo && ./reviewers.py -a -d ${time}) > results/all-reviewers-${time}.txt
	done
fi
