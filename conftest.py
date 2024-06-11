# Patch pyavtools.fix so it can run in memory without a fix server
import sys
import mock_db.client
import mock_db.scheduler
sys.modules["pyavtools.fix.client"] = mock_db.client
sys.modules["pyavtools.scheduler"] = mock_db.scheduler

# import fix
import pyavtools.fix as fix
# Init database
fix.initialize({"main":{"FixServer":"localhost","FixPort":"3490"}})

# TODO Add example setting aux values since needed on many tests
# Define some fix db items we can use in tests
# Define a key:
# key,desc, dtype(as a string), min, max, units, tol, aux
fix.db.define_item("TEST", "Testing key", 'float', 0, 100, '', 50000, "")
# Set initial Value
fix.db.set_value("TEST", 50)
# Bad and fail are true by default to set them False
fix.db.get_item("TEST").bad = False
fix.db.get_item("TEST").fail = False

