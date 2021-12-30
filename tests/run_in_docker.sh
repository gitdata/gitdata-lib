
source tests/setup_container.sh

nosetests -vx $(ls tests/unittests/test_* | grep -v test_database)

