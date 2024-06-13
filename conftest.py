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


def create_numbers(key,value,old=False,bad=False,fail=False,annunciate=False):
    fix.db.define_item(key, "Number", 'float', 0, 100, 'degC', 50000, "Min,Max,highWarn,highAlarm,lowWarn,lowAlarm")
    fix.db.set_value(key, value)
    fix.db.get_item(key).old = old
    fix.db.get_item(key).bad = bad
    fix.db.get_item(key).fail = fail
    fix.db.get_item(key).annunciate = annunciate
    fix.db.get_item(key).set_aux_value("Min",0)
    fix.db.get_item(key).set_aux_value("lowAlarm",10)
    fix.db.get_item(key).set_aux_value("lowWarn",20)
    fix.db.get_item(key).set_aux_value("highWarn",80)
    fix.db.get_item(key).set_aux_value("highAlarm",90)
    fix.db.get_item(key).set_aux_value("Max",100)

create_numbers("NUMOK", 50.91)
create_numbers("NUMOLD", 51.82, old=True)
create_numbers("NUMBAD", 48.73, bad=True)
create_numbers("NUMFAIL", 65.64, fail=True)
create_numbers("NUMANNUNCIATE", 62.55, annunciate=True)
create_numbers("NUMLOWWARN",18.46)
create_numbers("NUMLOWALARM", 5.37)
create_numbers("NUMHIGHWARN", 81.28)
create_numbers("NUMHIGHALARM", 95.19)





