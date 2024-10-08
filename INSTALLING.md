## Installing pyEFIS and FIX-Gateway
The following instructions are specific to the latest 64bit Raspbian bullseye and may not work on other versions or operating systems.

### Install the latest updates
Open a terminal window and run:
```
sudo apt update
sudo apt dist-upgrade -y
```

### Install snapd
Install snapd
```
sudo apt install -y snapd
```

Enable hotplug option in snapd:
```
sudo snap set system experimental.hotplug=true
```

Enable user-daemon mode:
```
sudo snap set system experimental.user-daemons=true
```

### Reboot
You must reboot before proceeding
```
sudo reboot
```

### Install snap core
Install core snap to update snapd
```
sudo snap install core
```

### Install FIX-Gateway
Install the fixgateway snap
```
sudo snap install fixgateway
```

### Install pyEFIS
Install the pyefis snap
```
sudo snap install pyefis
```

### Requirements for some hardware
Depending on what hardware you will be interfacing you may need to perform the steps in this section. It will not hurt to do them even if you don't use this hardware so you might just want to do them anyway and have your system prepared for future changes.
<br>
Snaps run in an isolated container and do not have un-restricted access to your system. Depending on what hardware you are using you might need to grant the fixgateway snap permissions to access the hardware.
<br>

#### CAN bus
If you are using CAN, allow fixgateway access to CAN:
```
sudo snap connect fixgateway:can-bus snapd
```

#### Serial ports
If you are using serial ports to access your hardware, allow fixgateway to access serial ports.

Add yourself to the dialout group:
```
sudo usermod -a -G dialout ${USER}
newgrp dialout
```

These next few steps are specific to your system so you will need to run commands to get some data and then use that data in other commands.

List serial port slots/plugs:
```
snap interface serial-port --attrs
```

In the output you are looking for the name of your serial port.
Now run command using that name replacing serial-name-here:
```
sudo snap connect fixgateway:serial-port snapd:serial-name-here
```

### Managing auto start
By default fixgateway and pyefis will auto start on reboot.<br>
To disable this edit the config files and change `AUTOSTART` to `false`
```
enabled:
  AUTO_START: true
```

pyefis config:
```
~/makerplane/pyefis/config/preferences.yaml.custom
```

fixgateway config:
```
~/makerplane/fixgw/config/preferences.yaml.custom
```

Below are commands to start/stop pyefis and fixgateway
#### Stop pyefis
```
sudo snap stop pyefis.daemon
```

#### Start pyefis:
```
sudo snap start pyefis.daemon
```

#### Stop fixgateway.daemon
```
sudo snap stop fixgateway.daemon
```

#### Start fixgateway.daemon:
```
sudo snap start fixgateway.daemon
```

### Customizing or using different configuration file
Currently it is not possible to change the configuration filename with the auto start feature.<br>
You can edit the default, your changes will not be overwritten when the system is updated.<br>
In my case I have a `preferences.yaml.custom.left` and `preferences.yaml.custom.right` file for the left and right screens. I simply created a `preferences.yaml.custom` symlink to the correct file on each side.

On the left side I did:
```
cd ~/makerplane/pyefis/config
rm preferences.yaml.custom
ln -s preferences.yaml.custom.left preferences.yaml.custom
```

Now when it auto starts it uses the `preferences.yaml.custom.left` config

If you are starting new or only have a single display just edit the `preferences.yaml.custom` file to make customizations.
<br>
For more information on how to customize the display see [Screen Builder Documentation](https://github.com/makerplane/pyEfis/blob/master/docs/screenbuilder.md)


### Data needed for Virtual VFR
The virtual VFR feature uses FAA CIFP data to display runways and glide slop indicators in the atitude indicator.<br>
When using the snap installation method, outlined above, this data is automatically downloaded and periodically auto updated.

### Important information:
NOTE: Upon starting a folder named makerplane will be created in your home folder and default configs copied into that folder.<br>
It will not overwrite any file that currently exists so your customizations are safe. If you would like to get updated default configs you could delete the old configs and then start pyefis and fixgateway.<br>

Directories you need to know:

  * pyefis configs: ~/makerplane/pyefis/config
  * fixgateway configs: ~/makerplane/fixgw/config
  * flight data recorder logs: ~/makerplane/pyefis/fdr

Commands:

  * stop fixgateway: `sudo snap stop fixgateway.daemon` 
  * start fixgateway: `sudo snap start fixgateway.daemon`
  * stop pyefis: `sudo snap stop pyefis.daemon`
  * start pyefis: `sudo snap start pyefis.daemon`
  * While stopped you can run them manually to see real time debug output:
  * pyefis: `pyefis.server --config-file=$HOME/makerplane/pyefis/config/default.yaml --debug`
  * fixgateway: `fixgateway.server --config-file=$HOME/makerplane/fixgw/config/default.yaml --debug`
  * fixgateway client: `fixgateway.client`
  * running fixgateway in FDR playback mode: `sudo snap start fixgateway.daemon; fixgateway.server --playback-start-time 2024-07-13-18:51:10`
  * CIFP index builder: `pyefis.makecifpindex`

Installing pyefis, FAA CIFP data, and fixgateway updates:
```
snap refresh
```

### Setup Android
If you want to use the Android feature you can find directions to setup Android [Here](ANDROID.md)


