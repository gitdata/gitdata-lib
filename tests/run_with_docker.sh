#
# run_with_docker.sh
#
# Use to verify that the unittests can run successfully in a container.  Useful
# for debugging CD process changes.
#

docker run \
   -it \
   -v $(pwd):/builds/gitdata/gitdata-lib:ro \
   -v $(pwd)/tmp:/builds/gitdata/gitdata-lib/tmp \
   python:3.9 \
   bash -c "cd /builds/gitdata/gitdata-lib && bash tests/run_in_docker.sh"
