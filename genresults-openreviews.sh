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
	(metadata && ./openreviews.py -p ${project} ${EXTRA_ARGS}) > results/${project_base}-openreviews.txt
	./openreviews.py -p ${project} --html ${EXTRA_ARGS} > results/${project_base}-openreviews.html
	(metadata && ./openapproved.py -p ${project} ${EXTRA_ARGS}) > results/${project_base}-openapproved.txt
done

if [ "${all}" = "1" ] ; then
	(metadata && ./openreviews.py -a ${EXTRA_ARGS}) > results/all-openreviews.txt.tmp
	for f in results/*-openreviews.txt ; do
		(echo && cat $f) >> results/all-openreviews.txt.tmp
	done
	mv results/all-openreviews.txt.tmp results/all-openreviews.txt
	./openreviews.py -a --html ${EXTRA_ARGS} | grep -v '</html>' > results/all-openreviews.html.tmp
	for f in results/*-openreviews.html ; do
		cat $f | grep -v 'html>' | grep -v 'head>' >> results/all-openreviews.html.tmp
	done
	echo "</html>" >> results/all-openreviews.html.tmp
	mv results/all-openreviews.html.tmp results/all-openreviews.html

	(metadata && ./openapproved.py -a ${EXTRA_ARGS}) > results/all-openapproved.txt
fi
