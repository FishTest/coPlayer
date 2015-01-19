Step 1:Burn image with usb image tools

OS Raspbian 12.24.2014
Download: http://www.raspberrypi.org

Usb Image Tools:
Download: http://www.alexpage.de/usb-image-tool/

Step 2:Basic setting

Login to your raspberry pi with ssh tools like putty(http://www.putty.org/)
Basic config:Expand you file system,overclock your pi,enable spi.

sudo raspi-config

1 Expand Filesystem -> OK
7 OverClock -> OK -> Medium -> OK
8 Advanced Options -> SPI -> Yes
8 Advanced Options -> I2C -> Yes
8 Advanced Options -> Serial -> No

Finish -> Reboot -> Yes

Step 3:install newest kernel with fbtft driver builtin

sudo REPO_URI=https://github.com/notro/rpi-firmware BRANCH=builtin rpi-update
sudo nano /boot/cmdline.txt

add below line before rootwait

fbtft_device.name=freetronicsoled128 fbtft_device.speed=20000000 fbcon=map:10

sudo reboot
now you can see system startup from oled screen

Step 4:Enable DAC Driver

sudo nano /etc/modules

#snd-bcm2835
i2c-dev
snd_soc_bcm2708
bcm2708_dmaengine
snd_soc_hifiberry_dacplus

sudo nano /etc/modprobe.d/raspi-blacklist.conf

#blacklist spi-bcm2708
#blacklist i2c-bcm2708
#blacklist snd-soc-pcm512x
#blacklist snd-soc-wm8804

sudo reboot

aplay -l

your should see this:
**** List of PLAYBACK Hardware Devices ****
card 0: sndrpihifiberry [snd_rpi_hifiberry_dacplus], device 0: HiFiBerry DAC+ HiFi pcm512x-hifi-0 []
  Subdevices: 1/1
  Subdevice #0: subdevice #0


Step 5:install system require

sudo apt-get update
sudo apt-get install mpd mpc python-dev python-pip python-smbus python-mpd python-netifaces python-mutagen
sudo apt-get install samba samba-common-bin 
sudo pip install python-mpd2

git clone https://github.com/adafruit/Adafruit_Python_GPIO.git
cd Adafruit_Python_GPIO
sudo python setup.py install

step 6:MPD Config

sudo service mpd stop
sudo chown pi:pi /var/lib/mpd/music
sudo nano /etc/mpd.conf

add and keep below 2 output type

audio_output {
        type            "alsa"
        name            "My ALSA Device"
        device          "hw:0,0"        # optional
        format          "44100:16:2"    # optional
        mixer_device    "default"       # optional
        mixer_control   "Playback Digital"              # optional
        mixer_index     "0"             # optional
}

audio_output {
        type    "fifo"
        name    "my_fifo"
        path    "/tmp/mpd.fifo"
        format  "44100:16:2"
}

change bind_to_address from 'localhost' to "0.0.0.0"

bind_to_address         "0.0.0.0"

sudo service mpd start

step 7:Samba Config
sudo service samba stop
sudo smbpasswd -a pi (add user pi then you should type new passowrd for twice)
sudo nano /etc/samba/smb.conf
use this settings

[global]
    workgroup = WORKGROUP
    #usershare allow guests = yes
    #security=share
    security=user
    follow symlinks = yes
    wide links = no
    unix extensions = no
    lock directory = /var/cache/samba
[pi]
    browsable = yes
    read only = no
    #guest ok = yes
    valid users = pi
    path = /home/pi
    #force user = pi (no longer needed)
[devices]
    browsable = yes
    read only = no
    #guest ok = yes
    valid users = pi
    path = /media
[Music]
    browsable = yes
    read only = no
    valid users = pi
    path = /var/lib/mpd/music

sudo service start samba

Step 8:install player
git clone https://github.com/FishTest/coplayer.git
cd coplayer
sudo python coplayer.py

Step 9:How to use

Main:
up    :volume up
down  :volume down
left  :previous song
right :next song
middle:Menu
red:  :pause/play
black :playlist
top   :exit

Menu:
up    :up
down  :down
middle:close menu
red   :enter setting
black :return

playlist:
up    :up
down  :down
left  :previous page
right :next page
red   :play
balck :return
top   :exit

InputBox:
up    :up
down  :down
left  :left
right :right
middle:return
red   :input selected char
black :backspace
top   :confirm


step last:oh no !!!!!!!!!!!!!!!!!!!!!!!!!!
the simple:
i've put all modified config file into config folder
you can just stop the service and cp these file to there folder