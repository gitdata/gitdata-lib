
export $(grep -v '^#' .env | xargs) && env | grep PY

python3.7 -m twine upload --verbose -u $PYPI_USERNAME -p $PYPI_PASSWORD dist/*
