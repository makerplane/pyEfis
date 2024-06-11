import sys
import mock_db.client
import mock_db.scheduler
sys.modules["pyavtools.fix.client"] = mock_db.client
sys.modules["pyavtools.scheduler"] = mock_db.scheduler


import pyavtools.fix as fix
fix.initialize({"main":{"FixServer":"localhost","FixPort":"3490"}})

# stop waiting
fix.db.init_event.set()
# Define itms:
fix.db.define_item("TEST", "Testing key", 'float', 0, 100, '', 50000, "")
fix.db.set_value("TEST", 50)
