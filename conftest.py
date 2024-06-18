import pytest
# Patch pyavtools.fix so it can run in memory without a fix server
import sys
import tests.mock_db.client
import tests.mock_db.scheduler

sys.modules["pyavtools.fix.client"] = tests.mock_db.client
sys.modules["pyavtools.scheduler"] = tests.mock_db.scheduler



@pytest.fixture
def fix():
    # import fix
    import pyavtools.fix as fix

    # Init database
    fix.initialize({"main": {"FixServer": "localhost", "FixPort": "3490"}})

    # TODO Add example setting aux values since needed on many tests
    # Define some fix db items we can use in tests
    # Define a key:
    # key,desc, dtype(as a string), min, max, units, tol, aux
    fix.db.define_item("TEST", "Testing key", "float", 0, 100, "", 50000, "")
    # Set initial Value
    fix.db.set_value("TEST", 50.19)
    # Bad and fail are true by default to set them False
    fix.db.get_item("TEST").bad = False
    fix.db.get_item("TEST").fail = False


    def create_numbers(key, value, old=False, bad=False, fail=False, annunciate=False):
        fix.db.define_item(
            key,
            "Number",
            "float",
            0,
            100,
            "degC",
            50000,
            "Min,Max,highWarn,highAlarm,lowWarn,lowAlarm",
        )
        fix.db.set_value(key, value)
        fix.db.get_item(key).old = old
        fix.db.get_item(key).bad = bad
        fix.db.get_item(key).fail = fail
        fix.db.get_item(key).annunciate = annunciate
        fix.db.get_item(key).set_aux_value("Min", 0)
        fix.db.get_item(key).set_aux_value("lowAlarm", 10)
        fix.db.get_item(key).set_aux_value("lowWarn", 20)
        fix.db.get_item(key).set_aux_value("highWarn", 80)
        fix.db.get_item(key).set_aux_value("highAlarm", 90)
        fix.db.get_item(key).set_aux_value("Max", 100)


    create_numbers("NUMOK", 50.91)
    create_numbers("NUMOLD", 51.82, old=True)
    create_numbers("NUMBAD", 48.73, bad=True)
    create_numbers("NUMFAIL", 65.64, fail=True)
    create_numbers("NUMANNUNCIATE", 62.55, annunciate=True)
    create_numbers("NUMLOWWARN", 18.46)
    create_numbers("NUMLOWALARM", 5.37)
    create_numbers("NUMHIGHWARN", 81.28)
    create_numbers("NUMHIGHALARM", 95.19)

    # Number with no Aux
    fix.db.define_item("NUM", "NUM", "float", 0.0, 100.0, "degC", 50000, "")

    fix.db.define_item("GS", "GS", "float", 0.0, 2000.0, "knots", 50000, "")
    fix.db.set_value("GS", 100)
    fix.db.get_item("GS").bad = False
    fix.db.get_item("GS").fail = False

    fix.db.define_item("TAS", "TAS", "float", 0.0, 2000.0, "knots", 50000, "")
    fix.db.set_value("TAS", 105)
    fix.db.get_item("TAS").bad = False
    fix.db.get_item("TAS").fail = False

    fix.db.define_item(
        "IAS",
        "Number",
        "float",
        0,
        2000.0,
        "knots",
        50000,
        "Min,Max,V1,V2,Vne,Vfe,Vmc,Va,Vno,Vs,Vs0,Vx,Vy",
    )
    fix.db.set_value("IAS", "110")
    fix.db.get_item("IAS").bad = False
    fix.db.get_item("IAS").fail = False
    fix.db.get_item("IAS").set_aux_value("Vs", 45.0)
    fix.db.get_item("IAS").set_aux_value("Vs0", 40.0)
    fix.db.get_item("IAS").set_aux_value("Vno", 125.0)
    fix.db.get_item("IAS").set_aux_value("Vne", 140.0)
    fix.db.get_item("IAS").set_aux_value("Vfe", 70.0)

    fix.db.define_item(
        "ALT",
        "Indicated Altitude",
        "float",
        -2000.0,
        60000.0,
        "ft",
        50000,
        ""
    )
    fix.db.set_value("ALT", 0)
    fix.db.get_item("ALT").bad = False 
    fix.db.get_item("ALT").fail = False


    fix.db.define_item(
        "LAT",
        "Latitude",
        "float",
        -90.0,
        90.0,
        "deg",
        50000,
        ""
    )
    fix.db.set_value("LAT", 0)
    fix.db.get_item("LAT").bad = False
    fix.db.get_item("LAT").fail = False

    fix.db.define_item(
        "LONG",
        "Longitude",
        "float",
        -180.0,
        180.0,
        "deg",
        50000,
        ""
    )
    fix.db.set_value("LONG", 0)
    fix.db.get_item("LONG").bad = False
    fix.db.get_item("LONG").fail = False

    fix.db.define_item(
        "PITCH",
        "Pitch Angle",
        "float",
        -90.0,
        90.0,
        "deg",
        50000,
        ""
    )
    fix.db.set_value("PITCH", 0)
    fix.db.get_item("PITCH").bad = False
    fix.db.get_item("PITCH").fail = False

    fix.db.define_item(
        "ROLL",
        "Roll Angle",
        "float",
        -180.0,
        180.0,
        "deg",
        50000,
        ""
    )
    fix.db.set_value("ROLL", 0)
    fix.db.get_item("ROLL").bad = False
    fix.db.get_item("ROLL").fail = False

    fix.db.define_item(
        "ALAT",
        "Lateral Acceleration",
        "float",
        -30.0,
        30.0,
        "g",
        50000,
        ""
    )
    fix.db.set_value("ALAT", 0)
    fix.db.get_item("ALAT").bad = False
    fix.db.get_item("ALAT").fail = False

    fix.db.define_item(
        "HEAD",
        "Current Aircraft Magnetic Heading",
        "float",
        0.0,
        359.9,
        "deg",
        50000,
        ""
    )
    fix.db.set_value("HEAD", 0)
    fix.db.get_item("HEAD").bad = False
    fix.db.get_item("HEAD").fail = False

    fix.db.define_item(
        "GSI",
        "Glideslope Indicator",
        "float",
        -1.0,
        1.0,
        "",
        50000,
        ""
    )
    fix.db.set_value("GSI", 0)
    fix.db.get_item("GSI").bad = False
    fix.db.get_item("GSI").fail = False

    fix.db.define_item(
        "CDI",
        "Course Deviation Indicator",
        "float",
        -1.0,
        1.0,
        "",
        50000,
        "" 
    )
    fix.db.set_value("GSI", 0)
    fix.db.get_item("GSI").bad = False
    fix.db.get_item("GSI").fail = False

    fix.db.define_item(
        "COURSE",
        "Selected Course",
        "float",
        0.0,
        359.9,
        "deg",
        50000,
        ""
    )
    fix.db.set_value("COURSE", 0)
    fix.db.get_item("COURSE").bad = False
    fix.db.get_item("COURSE").fail = False

    fix.db.define_item(
        "ROT",
        "Rate of Turn",
        "float",
        -3000,
        3000,
        "Deg/sec",
        50000,
        ""
    )
    fix.db.set_value("ROT", 0)
    fix.db.get_item("ROT").bad = False
    fix.db.get_item("ROT").fail = False

    fix.db.define_item(
        "VS",
        "Vertical Speed",
        "float",
        -30000,
        30000,
        "ft/min",
        50000,
        "Min,Max" 
    )
    fix.db.set_value("ROT", 0)
    fix.db.get_item("ROT").bad = False
    fix.db.get_item("ROT").fail = False

    fix.db.define_item(
        "HIDEBUTTON",
        "Hide or show buttons",
        "bool",
        None,
        None,
        '',
        50000,
        ''
    )
    fix.db.set_value("HIDEBUTTON", False)
    fix.db.get_item("HIDEBUTTON").bad = False
    fix.db.get_item("HIDEBUTTON").fail = False

    for i in range(5):
        fix.db.define_item(
            f"TSBTN1{i}",
            f"Touch Button {i}",
            "bool",
            None,
            None,
            '',
            50000,
            ''
        )
        fix.db.set_value(f"TSBTN1{i}", False)
        fix.db.get_item(f"TSBTN1{i}").bad = False
        fix.db.get_item(f"TSBTN1{i}").fail = False


    fix.db.define_item(
        "MAVREQADJ",
        "",
        "bool",
        None,
        None,
        '',
        50000,
        ''
    )
    fix.db.set_value("MAVREQADJ", False)
    fix.db.get_item("MAVREQADJ").bad = False
    fix.db.get_item("MAVREQADJ").fail = False


    fix.db.define_item(
        "MAVADJ",
        "",
        "bool",
        None,
        None,
        '',
        50000,
        ''
    )
    fix.db.set_value("MAVADJ", False)
    fix.db.get_item("MAVADJ").bad = False
    fix.db.get_item("MAVADJ").fail = False


    fix.db.define_item(
        "MAVSTATE",
        "",
        "str",
        None,
        None,
        '',
        50000,
        ''
    )
    fix.db.set_value("MAVSTATE", "INIT")
    fix.db.get_item("MAVSTATE").bad = False
    fix.db.get_item("MAVSTATE").fail = False

    fix.db.define_item(
        "MAVMODE",
        "",
        "str",
        None,
        None,
        '',
        50000,
        ''
    )
    fix.db.set_value("MAVMODE", "TRIM")
    fix.db.get_item("MAVMODE").bad = False
    fix.db.get_item("MAVMODE").fail = False

    fix.db.define_item(
        "BARO",
        "",
        "float",
        0,
        35.0,
        'inHg',
        50000,
        ''
    )
    fix.db.set_value("BARO", 29.92)
    fix.db.get_item("BARO").bad = False
    fix.db.get_item("BARO").fail = False

    return fix
