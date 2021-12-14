
# simulate a pip installation
docker run -it \
    -v $(pwd):/tmp/gitdata-lib:ro \
    python:3.9 \
    bash -c 'pip install nose && pip install /tmp/gitdata-lib && python -c "import gitdata.database; print(gitdata.database.__path__)"'
    #bash -c 'pip install nose && pip install -r /tmp/gitdata-lib/requirements.txt && pip install --index-url https://test.pypi.org/simple/ gitdata-lib==0.0.1 && python -c "import gitdata.database; print(gitdata.database.__path__)"'

