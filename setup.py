
import os
import setuptools

here = os.path.abspath(os.path.dirname(__file__))

about = {}
with open(os.path.join(here, 'gitdata', '__version__.py'), 'r', encoding='utf-8') as f:
    exec(f.read(), about)  # pylint: disable=exec-used

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as f:
    requires = [l for l in f.read().splitlines() if not l.startswith('#')]

setuptools.setup(
    name='gitdata-lib',
    version=about['__version__'],
    author="DSI Labs",
    author_email="support@gitdata.com",
    description="Data extraction and analysis library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/gitdata/gitdata-lib",
    packages=setuptools.find_packages(include=['gitdata*']),
    entry_points={
        'console_scripts': [
            'gitdata = gitdata.cli:main'
        ]
    },
    install_requires=requires,
    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Database :: Front-Ends',
   ],
   include_package_data=True,
)
