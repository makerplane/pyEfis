# Patch pyavtools.fix so it can run in memory without a fix server
import sys
import tests.mock_db.client
import tests.mock_db.scheduler
sys.modules["pyavtools.fix.client"] = tests.mock_db.client
sys.modules["pyavtools.scheduler"] = tests.mock_db.scheduler

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
fix.db.set_value("TEST", 50.19)
# Bad and fail are true by default to set them False
fix.db.get_item("TEST").bad = False
fix.db.get_item("TEST").fail = False


fix.db.define_item("NUMOK", "Number OK", 'float', 0, 100, 'degC', 50000, "")
fix.db.set_value("NUMOK", 50.19)
fix.db.get_item("NUMOK").bad = False
fix.db.get_item("NUMOK").fail = False

fix.db.define_item("NUMOLD", "Number OK", 'float', 0, 100, 'degC', 5, "")
fix.db.set_value("NUMOLD", 50.19)
fix.db.get_item("NUMOLD").old = True
fix.db.get_item("NUMOLD").bad = False
fix.db.get_item("NUMOLD").fail = False

fix.db.define_item("NUMBAD", "Number OK", 'float', 0, 100, 'degC', 50000, "")
fix.db.set_value("NUMBAD", 50.19)
fix.db.get_item("NUMBAD").old = False
fix.db.get_item("NUMBAD").bad = True
fix.db.get_item("NUMBAD").fail = False

fix.db.define_item("NUMFAIL", "Number OK", 'float', 0, 100, 'degC', 50000, "")
fix.db.set_value("NUMFAIL", 50.19)
fix.db.get_item("NUMFAIL").old = False
fix.db.get_item("NUMFAIL").bad = False
fix.db.get_item("NUMFAIL").fail = True

fix.db.define_item("NUMLOWALARM", "Number OK", 'float', 0, 100, 'degC', 50000, "Min,Max,highWarn,highAlarm,lowWarn,lowAlarm")
fix.db.set_value("NUMLOWALARM", 50.19)
fix.db.get_item("NUMLOWALARM").old = False
fix.db.get_item("NUMLOWALARM").bad = False
fix.db.get_item("NUMLOWALARM").fail = False
fix.db.get_item("NUMLOWALARM").set_aux_value("Min",40)
fix.db.get_item("NUMLOWALARM").set_aux_value("lowAlarm",60)
fix.db.get_item("NUMLOWALARM").set_aux_value("lowWarn",70)
fix.db.get_item("NUMLOWALARM").set_aux_value("highWarn",80)
fix.db.get_item("NUMLOWALARM").set_aux_value("highAlarm",90)
fix.db.get_item("NUMLOWALARM").set_aux_value("Max",100)

fix.db.define_item("NUMLOWWARN", "Number OK", 'float', 0, 100, 'degC', 50000, "Min,Max,highWarn,highAlarm,lowWarn,lowAlarm")
fix.db.set_value("NUMLOWWARN", 50.19)
fix.db.get_item("NUMLOWWARN").old = False
fix.db.get_item("NUMLOWWARN").bad = False
fix.db.get_item("NUMLOWWARN").fail = False
fix.db.get_item("NUMLOWWARN").set_aux_value("Min",40)
fix.db.get_item("NUMLOWWARN").set_aux_value("lowAlarm",45)
fix.db.get_item("NUMLOWWARN").set_aux_value("lowWarn",55)
fix.db.get_item("NUMLOWWARN").set_aux_value("highWarn",80)
fix.db.get_item("NUMLOWWARN").set_aux_value("highAlarm",90)
fix.db.get_item("NUMLOWWARN").set_aux_value("Max",100)


fix.db.define_item("NUMMAX", "Number OK", 'float', 0, 100, 'degC', 50000, "Min,Max,highWarn,highAlarm,lowWarn,lowAlarm")
fix.db.set_value("NUMMAX", 50.19)
fix.db.get_item("NUMMAX").old = False
fix.db.get_item("NUMMAX").bad = False
fix.db.get_item("NUMMAX").fail = False
fix.db.get_item("NUMMAX").set_aux_value("Max",40)





