===========================
Coding Standards and Ideals
===========================

PyEfis is an open source project, and we welcome contributions from the
community.  There are some guidlines that will help maintain consistency
within the PyEfis codebase as well as the entire MakerPlane ecosystem.

The first thing to understand is how PyEfis fits within the greater MakerPlane
ecosystem.  It is simply a display device.  It is very tempting to add features
that calculate true airspeed, vertical speed or AOA from within the EFIS.  It is
also tempting to add flight director functions or calculate autopilot outputs. I
think this comes from the fact that many of "Big Guys" have done this for years,
so if seems like that is where these features belong. The purpose at MakerPlane
is not to try and sell you a box but rather create a set of tools that make it
easier for you build an avionics suite that exactly matches what you want in
your airplane.  To attain this goal we are trying to adhere as closely as
possible to the Unix Principle of modular tools. Each piece of software or
hardware should do one thing and do it well.  It should have a common interface
that would allow it to operate with other devices.  A user should be able to
replace any part of the system without disrupting anything else.

We believe that open source avionics would be much more approachable to end
users and developers alike, if each project did not have to re-invent all of the
wheels.  If you are interested in graphics and the EFIS then you may not really
want to build airspeed or attitude sensors.  If we define the interfaces well
then each contributor could work on what interests them and not be required to
build the other parts of the system to get their part to function.

PyEfis is the human interface part of the MakerPlane system.  It should do
nothing more than display infomation and allow the user to interface with the
system.  PyEfis should not calculate altitude corrections based on the
barometric altimeter setting.  Rather, it would just give the user a way to
change the altimeter setting and display the result that would be calculated
elsewhere in the system.  Where that calculation happens should not interest
the EFIS programmer at all.

A good question to ask yourself when trying to decide if a feature should be in
PyEfis or offloaded elsewhere is, "Would this be generally useful if someone
replaced the EFIS with their own?" If the answer is "Yes" then it would probably
be best to put the feature in some other piece of software or hardware.  We
don't think that PyEfis is going to be the only EFIS that people would want to
have in their airplane.  If you are adding autopilot calculations to PyEfis then
those users would have to duplicate that in their own EFIS.  If you write
another program, put it in a library or create a hardware device to that
directly and then use the same interfaces into PyEfis that the rest of the
system uses then you will have made you work available to others that may not
like PyEfis and want to build their own.

The main interface that PyEfis uses is a program called FixGateway.  It's a
Python program that is plugin based.  Each of these plugins can be responsible
for all or part of the data.  PyEfis uses a communication protocol to read and
write information to/from FixGateway.  The source of the data is not relevant
to PyEfis.  Indicated airspeed could be coming from a flight simulator via a UDP
connection or from a name brand airdata sensor via RS-232.  The only thing that
changes is that different plugins are loaded and configured within FixGateway.

It may be that the feature that you would like to add would make more sense in
FixGateway.

Now that you know the feature that you would like to add properly belongs in
PyEfis, we have some guildlines on coding and struture.  It helps others to
read and understand your code if you adhere as closely as possible to these
guidlines.

---------------
Code Guidelines
---------------

PyEfis was originally written as a quick hack to showcase some other MakerPlane
technologies.  It was a very rough piece of code that was difficult to maintain
and understand.  It's been refined over the years and is gotten much better but
there are still some remnants of the old code.  Because of this, exceptions to
these guidlines do exist in the code but we fix them as we make changes to those
parts.

PyEfis is written in Python and since Python enforces good indention practices
as part of it's syntax we don't really have to say much other than PyEfis uses
four spaces for indention.  We won't get involved in the tabs vs. spaces
argument.  We just use spaces because we use spaces.

PyEfis uses CamelCase for Class names and pascalCase for member functions.  We
use snake_case for class properties.

PyEfis uses PyQt5 as it's primary development framework.  We don't do everything
exaclty the way that Qt applictions would normally be done but this is not a
normal desktop type application.  We do a lot of absolute placement of widgets
on the screen for better or for worse.  It is probably possible to change most
of the screens to use layouts and get the same results but this is one of
those things that has remained from the original hackiness.  Newer screens are
better than the orignal ones and it all continues to improve.  None of us are
Qt experts and we are all learning as we go.

-------------------
Program Structure
-------------------

There are three main parts of the PyEfis system.  The first is a collection of
"Screens"  These screens are simply Qt Widgets that are shown or hidden when
different displays are required.

The second part is the communication subsytem.  The module that handle s this is
actually in another package called PyAvTools.  FixGateway contains a module that
is very similar so we may move PyEfis to the FixGateway version at some point in
the future to elliminate one dependency.

The third part of the system is the Human Machine Interface.  The menu is part
of the HMI.  This is still under development at this stage.  The purpose of the
menu is to supply an extensible system that allows the  pilot to input data and
interact with the system via touchscreen, buttons or encoders with as little
code duplication as possible.  The menu can be made up of on screen buttons or
lists etc.  The other part of the HMI is a collection of Actions.  These are
similar to the Actions that are included in Qt except that they suit our needs a
little better.

Actions are simply a collection of signals and slots that are contained in one
class called ActionClass.  Actions are  a little confusing at first but they are
very simply a way to decouple user interaction events and functions.  One way to
explain the use is with the menu interactions.  The user may interact with the
menu through either the touch screen events if the system is included with a
touch screen or a  a colleciton of buttons.  Instead of the button interacting
directly with the menu the button is set to activate an action that is
associated with the menu.  The menu activation is basically a slot on the menu
that is called from a signal in the ActionClass.

The main advantage of the ActionClass actions is that it makes configuration
easier. The ultimate goal of the project is for the end user to be able to
completely customize their EFIS with nothing but the configuration files.  Right
now there would be a fair bit of Python programming to customize the system but
we are trying to make these parts more configurable.  This requires a fair bit
of decoupling.

The widgets that we've created for use as instruments and gauges are closely
coupled to the internal database.  Internally these widgets make their own
connections to the internal database of information.  This is probably not
optimal as these widgets couldn't be used outside of PyEfis and 'normal' Qt
Widgets need wrappers to  function like the internal ones
