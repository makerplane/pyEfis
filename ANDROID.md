## Running Android inside pyEFIS
The following instructions are specific to the latest 64bit Raspbian bullseye and may not work on other versions or operating systems.


### Install the latest updates
Open a terminal window and run:
```
sudo apt update
sudo apt dist-upgrade -y
```

### Install required software
This is likely already installed:
```
sudo apt install -y weston raspi-config 
```

### Change some settings
Disable wayland and use x11:
```
sudo raspi-config nonint do_wayland W1
```

If you are running on a Raspberry PI 5, you need to enable 4k pages.<br>
This is NOT needed on other versions of the PI:
```
echo '# 4k pages
kernel=kernel8.img
'| sudo tee -a /boot/firmware/config.txt >/dev/null
```

This just removes the desktop notifications, we do not need to be informed of an update being avaliable while landing...
```
sudo apt remove lxplug-updater -y
```

Enable PSI in the kernel:
```
sudo sed --follow-symlinks -i 's/quiet/psi=1 quiet/g' /boot/firmware/cmdline.txt
```

Enable Apparmor:
```
sudo sed --follow-symlinks -i 's/quiet/apparmor=1 security=apparmor quiet/g' /boot/firmware/cmdline.txt
```

### Reboot
Reboot before proceeding

### Install waydroid
Install the waydroid repository and install waydroid:
```
sudo apt install curl ca-certificates -y
curl https://repo.waydro.id | sudo bash
sudo apt install -y libglibutil libgbinder python3-gbinder waydroid
```

#### Install lineago OS
NOTE: Remove the `-s GAPPS` if you do not want google play
This will download and install Lineage OS:

```
sudo waydroid init -s GAPPS
```

#### Fix apparmor 
This is related to this bug: https://github.com/waydroid/waydroid/issues/631
```
cd /etc/apparmor.d/
sudo ln -s lxc/lxc-waydroid .
```

#### Fix permissions errors
This is related to this bug: https://github.com/waydroid/waydroid/issues/1065
```
sudo sed --follow-symlinks -i 's/lxc.console.path/lxc.mount.entry = none acct cgroup2 rw,nosuid,nodev,noexec,relatime,nsdelegate,memory_recursiveprot 0 0\n\nlxc.console.path/g' /var/lib/waydroid/lxc/waydroid/config
```

#### Self Certify Play Store:
If you installed the google play store you will need to self certify this installation before google Play will work.
First you need to start waydroid, to do that we first run weston:
```
weston &
```

Then we run the command to start android:
```
WAYLAND_DISPLAY=wayland-1 waydroid show-full-ui
```

In another terminal window or tab open up the waydroid shell:
```
sudo waydroid shell
```

Once the shell is open run this command:
```
ANDROID_RUNTIME_ROOT=/apex/com.android.runtime ANDROID_DATA=/data ANDROID_TZDATA_ROOT=/apex/com.android.tzdata ANDROID_I18N_ROOT=/apex/com.android.i18n sqlite3 /data/data/com.google.android.gsf/databases/gservices.db "select * from main where name = \"android_id\";"
```

Use the string of numbers printed by the command to register the device on your Google Account navigate to [https://www.google.com/android/uncertified](https://www.google.com/android/uncertified) login with you Google Account and enter in the code that was output in the previous command.

After registering the Play store will work once you log into it with your account.

#### Reboot
Reboot before proceeding

### Install required services
After you have installed the pyefis snap you need to copy a file and run a few commands
How to install pyefis can be found [Here](INSTALLING.md)

 
#### Copy the systemd unit file to start android
You might need to first create a directory:
```
mkdir -p ~/.config/systemd/user/
```

Then copy the file:
```
ln -s /snap/pyefis/current/extras/waydroid-monitor.service ~/.config/systemd/user/waydroid-monitor.service
```

#### Enable and start the monitor
Enable the systemd user service so it starts automatically when you reboot:
```
systemctl --user enable waydroid-monitor.service
```

Start the service:
```
systemctl --user start waydroid-monitor.service
```

With the service running you can start pyEFIS and navigate to a page that includes an Android window. You should see it start up a few seconds after visiting the page.
