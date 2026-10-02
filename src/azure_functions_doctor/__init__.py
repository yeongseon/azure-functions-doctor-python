"""Init for azure_function_doctor package.

This module initializes the Azure Functions Doctor package and defines the version string.
"""

import sys
import warnings

__version__ = "0.21.2"


if sys.version_info < (3, 11):
    warnings.warn(
        "azure-functions-doctor will drop support for Python 3.10 in its next minor release. "
        "Python 3.10 reaches end of life in October 2026; upgrade to Python 3.11 "
        "or newer to keep receiving updates.",
        FutureWarning,
        stacklevel=2,
    )
