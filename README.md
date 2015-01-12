sudo apt-get install mpd python-dev python-pip python-pygame
sudo pip install python-mpd2 netifaces mutagen

cd ~
git clone https://github.com/Adafruit/Adafruit_GPIO.git
cd Adafruit_GPIO
sudo python setup.py install
cd ~

sudo nano /etc/modprobe.d/raspi-blacklist.conf

#blacklist spi-bcm2708
#blacklist i2c-bcm2708
#blacklist snd-soc-pcm512x
#blacklist snd-soc-wm8804

sudo nano /etc/modules

#snd-bcm2835
i2c-dev
snd_soc_bcm2708
bcm2708_dmaengine
snd_soc_pcm5102a
snd_soc_hifiberry_dac
