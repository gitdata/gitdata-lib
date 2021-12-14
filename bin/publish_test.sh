
export $(grep -v '^#' .env | xargs) && env | grep PY

python3.7 -m twine upload --verbose --repository testpypi -u $PYPI_TEST_USERNAME -p $PYPI_TEST_PASSWORD dist/*
