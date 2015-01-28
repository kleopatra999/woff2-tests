woff2-tests
===========

Test suite for WOFF 2.0

The test cases here are generated by the Python scripts in the generators directory.

* `AuthoringToolTestCaseGenerator.py`
* `FormatTestCaseGenerator.py`
* `UserAgentTestCaseGenerator.py`

The scripts are dependent on the following packages:

* FontTools https://github.com/behdad/fonttools
* Brotli (Python bindings) https://github.com/google/brotli

To compile a particular test suite, simply run the relevant script:

    >>> python AuthoringToolTestCaseGenerator.py

    >>> python FormatTestCaseGenerator.py

    >>> python UserAgentTestCaseGenerator.py
