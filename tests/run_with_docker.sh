#
# run_with_docker.sh
#
# Use to verify that the unittests can run successfully in a container.  Useful
# for debugging CD process changes.
#

docker run \
   -it \
   -v $(pwd):/builds/gitdata/gitdata-lib:ro python:3.9 \
   bash -c "cd /builds/gitdata/gitdata-lib && source tests/setup_container.sh && nosetests -vx --with-doctest tests/unittests gitdata/utils.py"
