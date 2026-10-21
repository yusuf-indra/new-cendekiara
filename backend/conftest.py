"""The environment of every test: the dev profile, set before anything is imported.

The settings are read once, when `cendekiara.core.config` is imported, and the
API refuses to start without an explicit APP_ENV. So the environment is set
here: this file is loaded before tests/conftest.py and before any test module.
"""

import os

os.environ["APP_ENV"] = "dev"
os.environ["SITE"] = "id"
os.environ["STORE"] = "memory"
os.environ["AUTH_MODE"] = "dev"
os.environ["JOBS"] = "inline"
