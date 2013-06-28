#!/bin/bash

projects=$1
all=0

if [ "$projects" = "" ] ; then
	projects=projects/*.json
	all=1
fi

mkdir -p results

rm -f results/*

for project in ${projects} ; do
	project_base=$(basename $(echo ${project} | cut -f1 -d'.'))
	(date -u && echo && ./openreviews.py -p ${project}) > results/${project_base}-openreviews.txt
	./openreviews.py -p ${project} --html > results/${project_base}-openreviews.html
	for time in 30 90 180 ; do
		(date -u && echo && ./reviewers.py -p ${project} -d ${time}) > results/${project_base}-reviewers-${time}.txt
	done
done

if [ "${all}" = "1" ] ; then
	(date -u && echo && ./openreviews.py -a) > results/all-openreviews.txt.tmp
	for f in results/*-openreviews.txt ; do
		(echo && cat $f) >> results/all-openreviews.txt.tmp
	done
	mv results/all-openreviews.txt.tmp results/all-openreviews.txt
	./openreviews.py -a --html | grep -v '</html>' > results/all-openreviews.html.tmp
	for f in results/*-openreviews.html ; do
		cat $f | grep -v 'html>' | grep -v 'head>' >> results/all-openreviews.html.tmp
	done
	echo "</html>" >> results/all-openreviews.html.tmp
	mv results/all-openreviews.html.tmp results/all-openreviews.html

	for time in 30 90 180 ; do
		(date -u && echo && ./reviewers.py -a -d ${time}) > results/all-reviewers-${time}.txt
	done
fi
