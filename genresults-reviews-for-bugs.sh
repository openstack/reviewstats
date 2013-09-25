#!/bin/bash

projects=projects/*.json

for project in ${projects} ; do
	project_base=$(basename $(echo ${project} | cut -f1 -d'.'))
	(date -u && echo && ./reviews_for_bugs.py -u russellb -p ${project}) > results/${project_base}-reviews-for-bugs.txt
done
