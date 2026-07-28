"What `open_app` does before it opens anything, since launching an application is not a test."

import pytest

from macmage import open_app


def test_open_app_unknown_name():
    "An unknown name fails at once, rather than silently opening nothing"
    with pytest.raises(ValueError): open_app('NoSuchApplicationExists')
