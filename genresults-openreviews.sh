#!/bin/bash

projects=$1
all=0

if [ "$projects" = "" ] ; then
	projects=projects/*.json
	all=1
fi

mkdir -p results

rm -f results/*-openreviews*
rm -f results/*-openapproved*

for project in ${projects} ; do
	project_base=$(basename $(echo ${project} | cut -f1 -d'.'))
	(date -u && echo && ./openreviews.py -p ${project}) > results/${project_base}-openreviews.txt
	./openreviews.py -p ${project} --html > results/${project_base}-openreviews.html
	(date -u && echo && ./openapproved.py -p ${project}) > results/${project_base}-openapproved.txt
	(date -u && echo && ./reviews_for_bugs.py -p ${project}) > results/${project_base}-reviews-for-bugs.txt
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

	(date -u && echo && ./openapproved.py -a) > results/all-openapproved.txt
fi
