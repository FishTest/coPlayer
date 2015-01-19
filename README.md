Step 1:Burn image with usb image tools
OS Raspbian 12.24.2014
Download: http://www.raspberrypi.org
Usb Image Tools:
Download: http://www.alexpage.de/usb-image-tool/

Step 2:Enable oled screen driver
Login to your raspberry pi with ssh tools like putty(http://www.putty.org/)
Basic config:Expand you file system,overclock your pi,enable spi.
sudo raspi-config

1 Expand Filesystem -> OK
7 OverClock -> OK -> Medium -> OK
8 Advanced Options -> SPI -> Yes
8 Advanced Options -> I2C -> Yes
8 Advanced Options -> Serial -> No
Finish -> Reboot -> Yes

install newest kernel with fbtft driver builtin
sudo REPO_URI=https://github.com/notro/rpi-firmware BRANCH=builtin rpi-update
sudo nano /boot/cmdline.txt

add below line before rootwait

fbtft_device.name=freetronicsoled128 fbtft_device.speed=20000000 fbcon=map:10

sudo reboot
now you can see system startup from oled screen

Step 3:Enable DAC Driver
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


Step 4:install system require
sudo apt-get update
sudo apt-get install mpd mpc python-dev python-pip python-smbus python-mpd python-netifaces python-mutagen
sudo apt-get install samba samba-common-bin 

git clone https://github.com/adafruit/Adafruit_Python_GPIO.git
cd Adafruit_Python_GPIO
sudo python setup.py install


step : MPD Config

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

change bind_to_address to "0.0.0.0"

bind_to_address         "0.0.0.0"


step Samba Config

Step :install player
git clone https://github.com/FishTest/coplayer.git
cd coplayer
sudo python coplayer.py

Step :How to use








Step optional:
reduce Raspbian 
