# coding=UTF-8
# FishX's tool-box for Raspberry PI
# This must run as root (sudo python lapse.py) due to framebuffer, etc.
#
# http://www.adafruit.com/products/998  (Raspberry Pi Model B)
# http://www.adafruit.com/products/1601 (PiTFT Mini Kit)
#
# Prerequisite tutorials: aside from the basic Raspbian setup and PiTFT setup
# http://learn.adafruit.com/adafruit-pitft-28-inch-resistive-touchscreen-display-raspberry-pi
#
# tools.py by FishX (fishx@foxmail.com)
# based on cam.py by Phil Burgess / Paint Your Dragon for Adafruit Industries.
# BSD license, all text above must be included in any redistribution.

import wiringpi2
import atexit
import cPickle as pickle
import errno
import fnmatch
import io
import os
import pygame
import threading
import netifaces
import re
import subprocess
import time
from pygame.locals import *
from subprocess import call  
from time import sleep
from datetime import datetime, timedelta

# UI classes ---------------------------------------------------------------
# Icon is a very simple bitmap class, just associates a name and a pygame
# image (PNG loaded from icons directory) for each.
# There isn't a globally-declared fixed list of Icons.  Instead, the list
# is populated at runtime from the contents of the 'icons' directory.
class Icon:

	def __init__(self, name):
	  self.name = name
	  try:
	    self.bitmap = pygame.image.load(iconPath + '/' + name + '.png')
	  except:
	    pass

# Button is a simple tappable screen region.  Each has:
#  - bounding rect ((X,Y,W,H) in pixels)
#  - optional background color and/or Icon (or None), always centered
#  - optional foreground Icon, always centered
#  - optional single callback function
#  - optional single value passed to callback
# Occasionally Buttons are used as a convenience for positioning Icons
# but the taps are ignored.  Stacking order is important; when Buttons
# overlap, lowest/first Button in list takes precedence when processing
# input, and highest/last Button is drawn atop prior Button(s).  This is
# used, for example, to center an Icon by creating a passive Button the
# width of the full screen, but with other buttons left or right that
# may take input precedence (e.g. the Effect labels & buttons).
# After Icons are loaded at runtime, a pass is made through the global
# buttons[] list to assign the Icon objects (from names) to each Button.

class Button:

	def __init__(self, rect, **kwargs):
	  self.rect     = rect # Bounds
	  self.color    = None # Background fill color, if any
	  self.iconBg   = None # Background Icon (atop color fill)
	  self.iconFg   = None # Foreground Icon (atop background)
	  self.bg       = None # Background Icon name
	  self.fg       = None # Foreground Icon name
	  self.callback = None # Callback function
	  self.value    = None # Value passed to callback
	  for key, value in kwargs.iteritems():
	    if   key == 'color': self.color    = value
	    elif key == 'bg'   : self.bg       = value
	    elif key == 'fg'   : self.fg       = value
	    elif key == 'cb'   : self.callback = value
	    elif key == 'value': self.value    = value

	def selected(self, pos):
	  x1 = self.rect[0]
	  y1 = self.rect[1]
	  x2 = x1 + self.rect[2] - 1
	  y2 = y1 + self.rect[3] - 1
	  if ((pos[0] >= x1) and (pos[0] <= x2) and
	      (pos[1] >= y1) and (pos[1] <= y2)):
	    if self.callback:
	      if self.value is None: self.callback()
	      else:                  self.callback(self.value)
	    return True
	  return False

	def draw(self, screen):
	  if self.color:
	    screen.fill(self.color, self.rect)
	  if self.iconBg:
	    screen.blit(self.iconBg.bitmap,
	      (self.rect[0]+(self.rect[2]-self.iconBg.bitmap.get_width())/2,
	       self.rect[1]+(self.rect[3]-self.iconBg.bitmap.get_height())/2))
	  if self.iconFg:
	    screen.blit(self.iconFg.bitmap,
	      (self.rect[0]+(self.rect[2]-self.iconFg.bitmap.get_width())/2,
	       self.rect[1]+(self.rect[3]-self.iconFg.bitmap.get_height())/2))

	def setBg(self, name):
	  if name is None:
	    self.iconBg = None
	  else:
	    for i in icons:
	      if name == i.name:
	        self.iconBg = i
	        break

# UI callbacks -------------------------------------------------------------
# These are defined before globals because they're referenced by items in
# the global buttons[] list.

############################################################################
#跳转到指定屏幕
def goScreen(n):
	global screenMode
	screenMode = n

#输入输入字符串是否为IP地址
def isIpAddr(varObj):
	rule = r"\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
	match = re.match( rule , varObj )
	if match:
		return True
	return False

#判断是否为域名
def isDomain(hostname):
    if len(hostname) > 255:
        return False
    if hostname.endswith("."): # A single trailing dot is legal
        hostname = hostname[:-1] # strip exactly one dot from the right, if present
    disallowed = re.compile("[^A-Z\d-]", re.IGNORECASE)
    return all( # Split by labels and verify individually
        (label and len(label) <= 63 # length is within proper range
         and not label.startswith("-") and not label.endswith("-") # no bordering hyphens
         and not disallowed.search(label)) # contains only legal characters
        for label in hostname.split("."))

#把字符串转换为Dict
def convTxtToDict():
	global tempText,charList
	charList = []
	for c in range(0, len(tempText)):
		charList.append(tempText[c:c+1])

#应用新的DNS设置
def applyNewDNSCfg():
	global screenMode,dns1,dns2,dns3
	if curOp == 0:
		dns1 = tempText
	elif curOp == 1:
		dns2 = tempText
	elif curOp == 2:
		dns3 = tempText
	dnsFile = open('/etc/resolv.conf','w')
	if isIpAddr(dns1):
		dnsFile.write("nameserver " + dns1 + "\n")
	if isIpAddr(dns2):
		dnsFile.write("nameserver " + dns2 + "\n")
	if isIpAddr(dns3):
		dnsFile.write("nameserver " + dns3 + "\n")
	dnsFile.close()
	viewNetworkSettings()

#在DNS1、2、3之间切换
def chgDNSOp(n):
	global tempText,curOp,dns1,dns2,dns3
	# save current network settings
	#if not isIpAddr(tempText):return
	if curOp == 0:
		dns1 = tempText
	elif curOp == 1:
		dns2 = tempText
	elif curOp == 2:
		dns3 = tempText
	curOp = n
	# switch to selected item
	if n == 0:
		tempText = dns1
	elif n == 1:
		tempText = dns2
	elif n == 2:
		tempText = dns3
	convTxtToDict()
	
	
#主菜单：Change DNS CLick，读取DNS设置并初始化
def chgDnsClick():
	global screenMode,dns1,dns2,dns3,tempText,charList,curOp
	dnsFile = open("/etc/resolv.conf") 
	line = dnsFile.readline()
	dnslist = []
	while line:
		line = line.replace('nameserver','')
		line = line.replace(' ','')
		line = line.replace('\n','')
		if isIpAddr(line):
			dnslist.append(line)
		line = dnsFile.readline()
	dnsFile.close()
	dns1 = "8.8.8.8"
	dns2 = ""
	dns3 = ""
	c = 0
	for l in dnslist:
		if c == 0:
			dns1 = l
		elif c == 1:
			dns2 = l
		elif c == 2:
			dns3 = l
		c = c + 1
	curOp = 0
	tempText = dns1
	convTxtToDict()
	screenMode = 3
	
#主菜单：查看当前的网络设置
def viewNetworkSettings():
	global screenMode,curIPEth0,curMskEth0,curMACEth0,curIPWlan0,curMskWlan0,curMACWlan0,curGWDefault,curDNS1,curDNS2,dnslist
	dnslist = []
	curIPEth0 = netifaces.ifaddresses('eth0').setdefault(netifaces.AF_INET,[{'addr':''}])[0]['addr']
	curMskEth0 = netifaces.ifaddresses('eth0').setdefault(netifaces.AF_INET,[{'netmask':''}])[0]['netmask']
	curMACEth0 = netifaces.ifaddresses('eth0').setdefault(netifaces.AF_LINK,[{'addr':''}])[0]['addr']
	try:
		curIPWlan0 = netifaces.ifaddresses('wlan0').setdefault(netifaces.AF_INET,[{'addr':''}])[0]['addr']
		curMskWlan0 = netifaces.ifaddresses('wlan0').setdefault(netifaces.AF_INET,[{'netmask':''}])[0]['netmask']
		curMACWlan0 = netifaces.ifaddresses('wlan0').setdefault(netifaces.AF_LINK,[{'addr':''}])[0]['addr']
	except:
		curIPWlan0 = ""
		curMskWlan0 = ""
		curMACWlan0 = ""
	gws = netifaces.gateways()
	try:
		curGWDefault = gws['default'][netifaces.AF_INET][0]
	except:
		curGWDefault = ""
	f = open("/etc/resolv.conf") 
	line = f.readline()
	while line:
		line = line.replace('nameserver','')
		line = line.replace(' ','')
		line = line.replace('\n','')
		if isIpAddr(line):
			dnslist.append(line)
		line = f.readline()
	f.close()
	screenMode = 4

#显示网络设置
def dispNetworkInfo():
	myfont = pygame.font.SysFont(fontName,18)
	lblText = myfont.render("eth0(" + curMACEth0 + ")", 1 , (0,255,0))
	screen.blit(lblText,(3,3))
	lblText = myfont.render("IP:" + curIPEth0 , 1 , (255,255,255))
	screen.blit(lblText,(3,23))
	lblText = myfont.render("MSK:" + curMskEth0 , 1 , (255,255,255))
	screen.blit(lblText,(3,43))
	lblText = myfont.render("wlan0(" + curMACWlan0 + ")", 1 , (0,255,0))
	screen.blit(lblText,(3,63))
	lblText = myfont.render("IP:" + curIPWlan0 , 1 , (255,255,255))
	screen.blit(lblText,(3,85))
	lblText = myfont.render("MSK:" + curMskWlan0 , 1 , (255,255,255))
	screen.blit(lblText,(3,103))
	lblText = myfont.render("gateway" , 1 , (0,255,0))
	screen.blit(lblText,(3,123))
	lblText = myfont.render(curGWDefault , 1 , (255,255,255))
	screen.blit(lblText,(3,143))
	lblText = myfont.render("DNS" , 1 , (0,255,0))
	screen.blit(lblText,(3,163))
	cnt = 0
	for dns in dnslist:
		cnt = cnt + 20
		lblText = myfont.render(dns , 1 , (255,255,255))
		screen.blit(lblText,(3,163 + cnt))
			
#更改网络配置功能模块。。。。。。。。
#主菜单：更改网络设置
def changeIPCallback(n):
	global screenMode
	screenMode = 6

#0-修改网络设置之前选择适配器
def selectAdpater(adp):
	global curAdpater,screenMode
	curAdpater = adp
	loadNetworkCfg(curAdpater)
	# if netifaces.ifaddresses(curAdpater).setdefault(netifaces.AF_INET,[{'addr':''}])[0]['addr'] <> "":
	screenMode = 5
	
#1-根据上一步选择的网卡，调入相应的网络参数
def loadNetworkCfg(adp):
	global curOp, tempText, screenMode
	global tempIP, tempMsk, tempGW
	try:
		tempIP = netifaces.ifaddresses(adp).setdefault(netifaces.AF_INET,[{'addr':''}])[0]['addr']
		tempMsk = netifaces.ifaddresses(adp).setdefault(netifaces.AF_INET,[{'netmask':''}])[0]['netmask']
	except:
		tempIP = ""
		tempMsk = ""
	gws = netifaces.gateways()
	try:
		tempGW = gws['default'][netifaces.AF_INET][0]
	except:
		tempGW = ""
	tempText = tempIP
	convTxtToDict()
	curOp = 0

#2-应用新的网络配置
def applyNewNetworkCfg(a):
	global curOp, tempText, screenMode
	global tempIP, tempMsk, tempGW, curAdpater, curOp, screenMode

	if a == "eth0":
		os.system("sudo ifconfig eth0 auto")
		sleep(2)
		viewNetworkSettings()
	elif a == "wlan0":
		os.system("sudo ifconfig wlan0 auto")
		os.system("sudo /etc/init.d/networking restart")
		sleep(2)
		viewNetworkSettings()
	elif isIpAddr(tempIP) and isIpAddr(tempMsk) and isIpAddr(tempGW):
		if curOp == 0:
			tempIP = tempText
		elif curOp == 1:
			tempMsk = tempText
		elif curOp == 2:
			tempGW = tempText
		print "Now change the network settings to new one..."
		tempCmd = "ifconfig " + curAdpater + " " + tempIP + " netmask " + tempMsk
		print tempCmd
		os.system(tempCmd)
		tempCmd = "route add default gw " + tempGW
		print tempCmd
		os.system(tempCmd)
		viewNetworkSettings()
	return

#修改网络配置界面中点击,ip,msk,gw按钮
def chgIPOp(n):
	global tempText,curOp,tempIP,tempMsk,tempGW
	# save current network settings
	if not isIpAddr(tempText):return
	if curOp == 0:
		tempIP = tempText
	elif curOp == 1:
		tempMsk = tempText
	elif curOp == 2:
		tempGW = tempText
	curOp = n
	# switch to selected item
	if n == 0:
		tempText = tempIP
	elif n == 1:
		tempText = tempMsk
	elif n == 2:
		tempText = tempGW
	convTxtToDict()
#主菜单按下Ping按钮后的初始化操作，修改ping界面的有关参数
def pingClick():
	global screenMode,curOp,tempAddr,tempPkg,tempCnt,tempText,theTarget,vkReturnScreen,vkTopBgReturnTarget,consoleReturnScreen
	theTarget = "ping"
	gws = netifaces.gateways()
	curGWDefault = gws['default'][netifaces.AF_INET][0]
	if isIpAddr(curGWDefault):
		tempAddr = curGWDefault
		tempText = tempAddr
	else :
		tempAddr = "192.168.1.1"
		tempText = tempAddr
	convTxtToDict()
	tempPkg = "32"
	tempCnt = "5"
	curOp = 0
	consoleReturnScreen = 7
	vkTopBgReturnTarget = 7
	vkReturnScreen = 7
	screenMode = 7
#
#
#Ping的操作界面点击的相关函数
def chgPingOp(n):
	global screenMode, consoleReturnScreen
	global curOp, tempAddr, tempCnt, tempPkg, tempText
	#保存当前设置
	#if not isIpAddr(curText):return
	if (curOp == 0 or curOp == 4 ) and (isIpAddr(tempText) or isDomain(tempText)):
		tempAddr = tempText
		if curOp == 4:
			consoleReturnScreen = 9
		else:
			consoleReturnScreen = 7
	elif curOp == 1 and tempText.isdigit():
		if tempText.lstrip("0") <> "":
			tempText = tempText.lstrip("0")
		tempCnt = tempText
	elif curOp == 2 and tempText.isdigit():
		if tempText.lstrip("0") <> "":
			tempText = tempText.lstrip("0")
		tempPkg = tempText
	else:
		return
		
	curOp = n

	if n == 0 or n == 4:
		tempText = tempAddr
	elif n == 1:
		tempText = tempCnt
	elif n == 2:
		tempText = tempPkg
	convTxtToDict()
	if n == 4:
		screenMode = 9

#开始Ping
#开始另外一个线程，不断从控制台获取数据，获取后添加到一个队列
#当按下Ping设置界面的OK按钮时执行此操作
def startPing():
	global screenMode,lastVkScreenMode
	global t, busy, popen, isManualRolling
	global tempAddr,tempCnt,tempPkg,curOP,tempText,tempCmd
	if (curOp == 0 or curOp ==4) and (isIpAddr(tempText) or isDomain(tempText)):
		tempAddr = tempText
	elif curOp == 1 and tempText.isdigit():
		if tempText.lstrip("0") <> "":
			tempText = tempText.lstrip("0")
			convTxtToDict()
		tempCnt = tempText
	elif curOp == 2 and tempText.isdigit():
		if tempText.lstrip("0") <> "":
			tempText = tempText.lstrip("0")
			convTxtToDict()
		tempPkg = tempText
	else:
		return
	tempCmd = "ping"
	if tempCnt <> "0":
		tempCmd = tempCmd + " -c " + tempCnt
	if tempPkg <> "0":
		tempCmd = tempCmd + " -s " + tempPkg
	tempCmd = tempCmd + " " + tempAddr
	consoleReturnScreen = lastVkScreenMode
	startSimpleCmd()

#按下虚拟键盘之后增加字符到字符列表
def vkCallback(k):
	global screenMode,charList,tempText
	if k <> "-1":
		charList.append(k)
	elif len(charList) <> 0:
		charList.pop()
	tempText = ''.join(charList)
	#print charList

#display the character intered
def showTextInputed():
	global charList,fontName,tempText
	charTop = 5
	charLeft = 3
	charMax = 26
	charCalc = 0
	charWidth = 10
	charHeight = 16
	charSpace = 2
	charBlank = 4
	curCharLine = 0
	charCount = 0
	maxLine = 3
	myfont = pygame.font.SysFont(fontName, charHeight)
	if tempText == "":
		charList = []
	for c in charList:
		lblChar = myfont.render(c , 1, (255,255,255))
		newCharLeft = charLeft + (charWidth + charSpace) * charCount
		newCharTop = charTop + (charHeight + charBlank) * curCharLine
		screen.blit(lblChar, (newCharLeft,newCharTop ))
		charCount = charCount + 1
		if charCount % charMax == 0:
			curCharLine = curCharLine + 1
			charCount = 0
	
#从控制台获取文本后追加到consoleResult词典（单独线程）
def getConsoleTextCommon():
	global busy,popen,shouldUpdate
	global maxConLinesBuffer,tempCmd,consoleResult
	
	busy = True
	consoleResult = []
	popen = subprocess.Popen(tempCmd.split(' '), stdout = subprocess.PIPE)
	while busy is True :
		cmdLine = popen.stdout.readline()
		if cmdLine <> "":
			if len(consoleResult) > maxConLinesBuffer:
				consoleResult.pop(0)
				consoleResult.append(cmdLine.replace('\n',''))
			else:
				consoleResult.append(cmdLine.replace('\n',''))
			shouldUpdate = True
		else:
			busy = False
	busy = False
	popen.kill()
	print "subProcess over!"
	
#主菜单运行自定义命令点击事件
def runCustomCmdClick():
	global screenMode,theTarget,vkReturnScreen,vkTopBgReturnTarget
	global tempText, charList
	tempText = ""
	convTxtToDict()
	vkTopBgReturnTarget = 9
	theTarget = "console"
	vkReturnScreen = 0
	screenMode = 9
	
#检测虚拟键盘按下OK键后，文本发送的目标。
def checkTarget():
	global theTarget,consoleReturnScreen,vkReturnScreen,screenMode,tempText,tempCmd,lastVkScreenMode
	if theTarget == "console":
		consoleReturnScreen = 9
		tempCmd = tempText
		startSimpleCmd()
	if theTarget == "ping":
		if isIpAddr(tempText) or isDomain(tempText):
			consoleReturnScreen = 7
			screenMode = 7
	if theTarget == "tracert":
		consoleReturnScreen = lastVkScreenMode
		tempCmd = "traceroute " + tempText
		startSimpleCmd()
	if theTarget == "scannetwork":
		consoleReturnScreen = lastVkScreenMode
		tempCmd = "sudo nmap -sS " + tempText
		startSimpleCmd()
	if theTarget == "scanport":
		consoleReturnScreen = lastVkScreenMode
		tempCmd = "nmap -PS " + tempText
		startSimpleCmd()
	if theTarget == "wifi":
		consoleReturnScreen = 2
		enableNewWifiConfig()
		tempCmd = "sudo /etc/init.d/networking restart"
		startSimpleCmd()
	if theTarget == "reset":
		setNetworkSettingsToDefault()
		screenMode = 15

#检测虚拟键盘按下Return键后,应当返回的屏幕
def checkReturnTarget():
	global screenMode, vkReturnScreen
	screenMode = vkReturnScreen

def checkVkTopBgReturnTarget():
	global screenMode, vkTopBgReturnTarget
	screenMode = vkTopBgReturnTarget
	
	
#控制台中绘制给定行数的结果，把指定的lineList绘制到屏幕。
def drawConsoleLines(lineList,leftPos,topPos):
	global fontName, conFontSize, conFontSize, conLineSpace,maxConLines
	lineFont = pygame.font.SysFont(fontName, conFontSize)
	#totalLines为lineList的总行数，actualLines为要绘制的实际行数
	totalLines = len(lineList)
	#print lineList
	if totalLines < maxConLines:
		actualLines = totalLines
	else:
		actualLines = maxConLines
	if actualLines > 0:
		for i in range(0,actualLines):
			#curLine = i + totalLines - actualLines
			lblCurLine = lineFont.render(lineList[i] , 1 , (255,255,255))
			screen.blit(lblCurLine,(leftPos, topPos + (conFontSize + conLineSpace) * i))


#从命令行的所有返回行中选择指定行发送给控制台绘制模块,调用以上功能
def dispConsoleResult():
	global consoleResult,maxRecord,isManualRolling
	totalLines = len(consoleResult)
	linesList = []
	if totalLines > maxConLines:
		actualLines = maxConLines
	else:
		actualLines = totalLines
	if actualLines > 0:
		for i in range(0,actualLines):
			curLine = i + totalLines - actualLines
			linesList.append(consoleResult[curLine])
			drawConsoleLines(linesList,3,3)

#上下滚动显示Console命令行返回结果
def rollingConsoleRows(direction):
	global consoleResult, maxConLines, curTopLine, curBottomLine, isManualRolling, manualLineList, busy
	#print "run Manual rolling",
	manualLineList = []
	totalLines = len(consoleResult)
	if totalLines < maxConLines:
		return
	
	if isManualRolling is not True:
		curBottomLine = totalLines
		curTopLine = totalLines - maxConLines
	else:
		isManualRolling = True
	
	if curTopLine <= 0:
		curTopLine = 0
		isTopLine = True
	else:
		isTopLine = False

	if curBottomLine >= totalLines:
		isBottomLine = True
	else:
		isBottomLine = False
	
	if direction is "up":
		if isTopLine is not True:
			curTopLine = curTopLine - 1
			curBottomLine = curBottomLine - 1
	
	if direction is "down":
		if isBottomLine is not True:
			curTopLine = curTopLine + 1
			curBottomLine = curBottomLine + 1
		
	#print "isBottomLine:" , isBottomLine, "Down Clicked! totalLine:", totalLines , "maxConLines:", maxConLines, "curTopLine:" , curTopLine , "curBottomLine:" , curBottomLine
	for curLine in range(curTopLine,curBottomLine):
		manualLineList.append(consoleResult[curLine])
	#print manualLineList
	drawConsoleLines(manualLineList,3,3)
	isManualRolling = True

#恢复自动滚动信息显示
def continueDrawConsoleRows():
	global isManualRolling
	isManualRolling = False

#从控制台运行命令窗口返回前一个窗口
def returnFromConsole():
	global screenMode,consoleReturnScreen
	global t, busy, popen
	if busy == True:
		popen.terminate()
		t.join()
		print "Return From Console"
	screenMode = consoleReturnScreen	

#执行指定的简单命令
def startSimpleCmd():
	global screenMode
	global t, busy, popen, isManualRolling
	global tempCmd

	print "now run:" + tempCmd

	if busy == True:
		t.join()
	t = threading.Thread(target=getConsoleTextCommon)
	t.start()
	
	isManualRolling = False
	screenMode = 13

#主菜单：路由跟踪
def tracertClick():
	global screenMode,theTarget,vkReturnScreen,tempText,vkTopBgReturnTarget
	vkTopBgReturnTarget = 12
	tempText = ""
	convTxtToDict()
	theTarget = "tracert"
	vkReturnScreen = 0
	screenMode = 12

#主菜单：扫描网络
def scanNetworkClick():
	global screenMode,theTarget,vkReturnScreen,tempText,vkTopBgReturnTarget
	vkTopBgReturnTarget = 12
	tempText = ""
	convTxtToDict()
	theTarget = "scannetwork"
	vkReturnScreen = 0
	screenMode = 12

#主菜单：扫描指定IP的全部端口
def scanPortClick():
	global screenMode,theTarget,vkReturnScreen,tempText,vkTopBgReturnTarget
	vkTopBgReturnTarget = 12
	tempText = ""
	convTxtToDict()
	theTarget = "scanport"
	vkReturnScreen = 0
	screenMode = 12
	
#主菜单：点击Wifi按钮
def wifiClick():
	global screenMode,curWifi,theTarget,vkReturnScreen
	vkReturnScreen = 2
	theTarget = "wifi"
	curWifi = 0
	screenMode = 2
	getWifiList()

#获取iwlist wlan0 scanning信息，全部发送到consoleResult
def getWifiList():
	global screenMode
	global t, busy, popen
	global tempCmd,curWifi
	tempCmd = "iwlist wlan0 scan"
	print "now run:" + tempCmd

	if busy == True:
		t.join()
	t = threading.Thread(target=getConsoleTextCommon)
	t.start()
	sleep(0.5)
	while busy is True:
		sleep(0.5)
	curWifi = 0
	parseWifiList()

#处理获取的consoleResult信息变成Wifi列表
def parseWifiList():
	global consoleResult,wifiList
	tempWifiItem = []
	wifiList = []
	firstMeet = True
	for line in consoleResult:
		if line.find('Cell') > -1:
			if firstMeet is True:
				tempWifiItem = []
				firstMeet = False
			else:
				wifiList.append(tempWifiItem)
				tempWifiItem = []
		tempWifiItem.append(line.strip())
	if tempWifiItem <> []:
		wifiList.append(tempWifiItem)
	
def setCurWifi(n):
	global curWifi
	if n == 1:
		if curWifi == wifiCount - 1:
			curWifi = 0
		else:
			curWifi = curWifi + 1
	else:
		if curWifi == 0:
			curWifi = wifiCount - 1
		else:
			curWifi = curWifi -1
	#print curWifi

#在屏幕上显示Wifi详细信息
def drawWifiOnScreen():
	global screenMode,wifiList,curWifi,wifiCount,fontName
	wifiCount = len(wifiList)
	if wifiCount == 0:
		return
	wifiFont = pygame.font.SysFont(fontName, 16)
	#Wifi:ESSID
	tempList = wifiList[curWifi][1].split('"')
	lblCurLine = wifiFont.render("(" + str(wifiCount) + "/" + str(curWifi + 1) + ")" + tempList[1] , 1 , (255,255,255))
	screen.blit(lblCurLine,(3, 3))
	#Mac
	tempLine = wifiList[curWifi][0][len(wifiList[curWifi][0])-17:len(wifiList[curWifi][0])]
	lblCurLine = wifiFont.render("MAC:" + tempLine , 1 , (255,255,255))
	screen.blit(lblCurLine,(3, 30))
	#Protocol
	tempLine = wifiList[curWifi][2].replace("Protocol:","")
	lblCurLine = wifiFont.render("Protocol:" + tempLine , 1 , (255,255,255))
	screen.blit(lblCurLine,(3, 50))
	#BitRate
	tempLine = wifiList[curWifi][6].replace("Bit Rates:","")
	lblCurLine = wifiFont.render("BitRates:" + tempLine , 1 , (255,255,255))
	screen.blit(lblCurLine,(3, 70))
	#Encrypt
	tempLine = wifiList[curWifi][5].replace("Encryption key:","")
	lblCurLine = wifiFont.render("Encrypt:" + tempLine , 1 , (255,255,255))
	screen.blit(lblCurLine,(3, 90))
	#Quality,signal Level
	if curWifi == wifiCount - 1:
		tempLineCount = len(wifiList[curWifi]) - 2
	else:
		tempLineCount = len(wifiList[curWifi]) - 1
	tempLine = wifiList[curWifi][tempLineCount]
	tempList = tempLine.split("/")
	tempList1 = tempList[0].split("=")
	tempList2 = tempList[1].split("=")
	tempLine = tempList1[1]
	lblCurLine = wifiFont.render("Signal Quality:" + tempLine + "%" , 1 , (255,255,255))
	screen.blit(lblCurLine,(3,110))
	tempLine = tempList2[1]
	lblCurLine = wifiFont.render("Signal Level:" + tempLine + "%", 1 , (255,255,255))
	screen.blit(lblCurLine,(3,130))
	
def reFreshWifiList():
	getWifiList()

#启用新的Wifi设置
#应该判断/etc/network/interface中是否有关于Wifi的以下几行
#auto wlan0
#allow-hotplug wlan0
#iface wlan0 inet manual
#wpa-roam /etc/wpa_supplicant/wpa_supplicant.conf
#iface default inet dhcp
#生成新的/etc/wpa_supplicant/wpa_supplicant.conf文件 
def enableNewWifiConfig():
	global wifiList,curWifi,tempText
	essid = wifiList[curWifi][1].split('"')[1]
	password = tempText
	wifiFile = open('/etc/wpa_supplicant/wpa_supplicant.conf','w')
	wifiFile.write("#ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n")
	wifiFile.write("#update_config=1\n")
	wifiFile.write("network={\n")
	wifiFile.write('ssid="' + essid + '"\n')
	wifiFile.write("proto=RSN\n")
	wifiFile.write("key_mgmt=WPA-PSK\n")
	wifiFile.write("pairwise=CCMP TKIP\n")
	wifiFile.write("group=CCMP TKIP\n")
	wifiFile.write('psk="' + password + '"\n')
	wifiFile.write('}\n')
	wifiFile.close()
	
#主菜单：退出按钮
def exitCallback():
	global screenMode
	screenMode = 1

#执行退出操作
def exitSystem(n):
	global screenMode
	if n == 0:
		raise SystemExit
	elif n == 1:
		os.system('sudo halt -h')
	elif n == 2:
		os.system('sudo reboot')
	elif n == 3:
		screenMode = 0

#主菜单：点击设置
def setClick():
	global screenMode
	screenMode = 15

def resetNetworkClick():
	global screenMode,cfmReturnScreen,theTarget,tempText
	tempText = "Reset Network Settings to Default?"
	convTxtToDict()
	theTarget = "reset"
	cfmReturnScreen = 15
	screenMode = 14

def chkCfmReturnScreen():
	global screenMode,cfmReturnScreen
	screenMode = cfmReturnScreen

def setNetworkSettingsToDefault():
	print "Start changing network configuration to default!"
	netCfgFile = open('/etc/network/interfaces','w')
	netCfgFile.write("auto lo\n")
	netCfgFile.write("\n")
	netCfgFile.write("iface lo inet loopback\n")
	netCfgFile.write("iface eth0 inet dhcp\n")
	netCfgFile.write("\n")
	netCfgFile.write("auto wlan0\n")
	netCfgFile.write("allow-hotplug wlan0\n")
	netCfgFile.write("iface wlan0 inet manual\n")
	netCfgFile.write("wpa-roam /etc/wpa_supplicant/wpa_supplicant.conf\n")
	netCfgFile.write("iface default inet dhcp\n")
	netCfgFile.close()
	wifiFile = open('/etc/wpa_supplicant/wpa_supplicant.conf','w')
	wifiFile.write("#ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n")
	wifiFile.write("#update_config=1\n")
	wifiFile.write("network={\n")
	wifiFile.write('ssid=""\n')
	wifiFile.write("proto=RSN\n")
	wifiFile.write("key_mgmt=WPA-PSK\n")
	wifiFile.write("pairwise=CCMP TKIP\n")
	wifiFile.write("group=CCMP TKIP\n")
	wifiFile.write('psk=""\n')
	wifiFile.write('}\n')
	wifiFile.close()
	os.system("sudo /etc/init.d/networking restart")
	sleep(1)
	print "Complete!"
	
# 全局设置
busy            = False
threadExited    = False
screenMode      =  0      # Current screen mode; default = HOME
screenModePrior = -1      # Prior screen mode (for detecting changes)
iconPath        = 'icons' # Subdirectory containing UI bitmaps (PNG format)
returnScreen   = 0
backlightpin   = 252
shouldUpdate = False
isManualRolling = False
txtBoxMaxLength = 300
charList = []
icons = [] # This list gets populated at startup
maxConLinesBuffer = 300
maxConLines = 20
conFontSize = 9
conFontSpace = 2
conLineSpace = 1
fontName = "Droid Sans Mono"
manualLineList = []
tempText = ""
cfmReturnScreen = 0
# buttons[] is a list of lists; each top-level list element corresponds
# to one screen mode (e.g. viewfinder, image playback, storage settings),
# and each element within those lists corresponds to one UI button.
# There's a little bit of repetition (e.g. prev/next buttons are
# declared for each settings screen, rather than a single reusable
# set); trying to reuse those few elements just made for an ugly
# tangle of code elsewhere.

buttons = [
  # Screen mode 0 is the MainMenu
  [Button(( 15, 14,144, 70), bg='icon_clock', cb=viewNetworkSettings),
   Button((163, 14, 70, 70), bg='icon13', cb=changeIPCallback, value=1),
   Button((237, 14, 70, 70), bg='icon_dns', cb=chgDnsClick),
   Button(( 15, 88, 70, 70), bg='icon12',   cb=pingClick),
   Button(( 89, 88, 70, 70), bg='icon14',   cb=tracertClick),
   Button((163, 88, 70, 70), bg='icon21',   cb=scanNetworkClick),
   Button((237, 88, 70, 70), bg='icon22',   cb=scanPortClick),
   Button(( 15,162, 70, 70), bg='icon_wifi',   cb=wifiClick),
   Button(( 89,162, 70, 70), bg='icon31',   cb=runCustomCmdClick),
   Button((163,162, 70, 70), bg='icon33',   cb=setClick),
   Button((237,162, 70, 70), bg='icon34',   cb=exitCallback)],
  # Screen 1 退出选择界面
  [Button((163, 88, 70, 70), bg='icon_ret',   cb=exitSystem, value=3),
   Button((237, 88, 70, 70), bg='reboot',   cb=exitSystem, value=2),
   Button((163,162, 70, 70), bg='halt',   cb=exitSystem, value=1),
   Button((237,162, 70, 70), bg='icon34',   cb=exitSystem, value=0)],
  # Screen 2 Wifi选择界面
  [Button((  1,  1,318, 24), bg='ws_title'),
   Button((289, 27, 30, 40), bg='ws_refresh',cb=reFreshWifiList),
   Button((289, 69, 30, 40), bg='ws_up',cb=setCurWifi,value = -1),
   Button((289,111, 30, 40), bg='ws_down',cb=setCurWifi,value = 1),
   Button((289,153, 30, 40), bg='ws_return',cb=goScreen,value=0),
   Button((289,196, 30, 40), bg='ws_ok',cb=goScreen,value=9)],
  # Screen 3 改DNS界面
  [Button((  3, 81, 50, 50), bg='ns1',     cb=chgDNSOp, value=0),
   Button((  3,134, 50, 50), bg='ns2',     cb=chgDNSOp, value=1),
   Button((  3,187, 50, 50), bg='ns3',     cb=chgDNSOp, value=2),
   Button(( 56, 81, 50, 50), bg='1',     cb=vkCallback, value="1"),
   Button(( 56,134, 50, 50), bg='4',     cb=vkCallback, value="4"),
   Button(( 56,187, 50, 50), bg='7',     cb=vkCallback, value="7"),
   Button((109, 81, 50, 50), bg='2',     cb=vkCallback, value="2"),
   Button((109,134, 50, 50), bg='5',     cb=vkCallback, value="5"),
   Button((109,187, 50, 50), bg='8',     cb=vkCallback, value="8"),
   Button((162, 81, 50, 50), bg='3',     cb=vkCallback, value="3"),
   Button((162,134, 50, 50), bg='6',     cb=vkCallback, value="6"),
   Button((162,187, 50, 50), bg='9',     cb=vkCallback, value="9"),
   Button((215, 81, 50, 50), bg='dot',     cb=vkCallback, value="."),
   Button((215,134, 50, 50), bg='0',     cb=vkCallback, value="0"),
   Button((215,187,103, 50), bg='ok',     cb=applyNewDNSCfg),
   Button((268, 81, 50, 50), bg='del',     cb=vkCallback, value="-1"),
   Button((268,134, 50, 50), bg='ret',     cb=goScreen, value=0)],
  # Screen 4 is Display IP Address 显示IP界面返回
  [Button((215,188,103, 50), bg='ok',     cb=goScreen, value=0)],
  # Screen 5 is Changing Network settings
  [Button((  3, 81, 50, 50), bg='adr',     cb=chgIPOp, value=0),
   Button((  3,134, 50, 50), bg='msk',     cb=chgIPOp, value=1),
   Button((  3,187, 50, 50), bg='gw',     cb=chgIPOp, value=2),
   Button(( 56, 81, 50, 50), bg='1',     cb=vkCallback, value="1"),
   Button(( 56,134, 50, 50), bg='4',     cb=vkCallback, value="4"),
   Button(( 56,187, 50, 50), bg='7',     cb=vkCallback, value="7"),
   Button((109, 81, 50, 50), bg='2',     cb=vkCallback, value="2"),
   Button((109,134, 50, 50), bg='5',     cb=vkCallback, value="5"),
   Button((109,187, 50, 50), bg='8',     cb=vkCallback, value="8"),
   Button((162, 81, 50, 50), bg='3',     cb=vkCallback, value="3"),
   Button((162,134, 50, 50), bg='6',     cb=vkCallback, value="6"),
   Button((162,187, 50, 50), bg='9',     cb=vkCallback, value="9"),
   Button((215, 81, 50, 50), bg='dot',     cb=vkCallback, value="."),
   Button((215,134, 50, 50), bg='0',     cb=vkCallback, value="0"),
   Button((215,187,103, 50), bg='ok',     cb=applyNewNetworkCfg,value="none"),
   Button((268, 81, 50, 50), bg='del',     cb=vkCallback, value="-1"),
   Button((268,134, 50, 50), bg='ret',     cb=goScreen, value=0)],
  # Screen 6 choosing network adpater
  [Button(( 14, 13,144, 70), bg='eth0_m',     cb=selectAdpater, value="eth0"),
   Button((162, 13,144, 70), bg='wlan0_m',     cb=selectAdpater, value="wlan0"),
   Button(( 14, 87,144, 70), bg='eth0_a',     cb=applyNewNetworkCfg, value="eth0"),
   Button((162, 87,144, 70), bg='wlan0_a',     cb=applyNewNetworkCfg, value="wlan0"),
   Button(( 15,161,291, 70), bg='return_big',     cb=goScreen, value=0)],
  # Screen 7 is Ping settings
  [Button((  3,  2,315, 77), bg='addr_bg',     cb=chgPingOp, value=4),
   Button((  3, 81, 50, 50), bg='adr',     cb=chgPingOp, value=0),
   Button((  3,134, 50, 50), bg='cnt',     cb=chgPingOp, value=1),
   Button((  3,187, 50, 50), bg='pkg',     cb=chgPingOp, value=2),
   Button(( 56, 81, 50, 50), bg='1',     cb=vkCallback, value="1"),
   Button(( 56,134, 50, 50), bg='4',     cb=vkCallback, value="4"),
   Button(( 56,187, 50, 50), bg='7',     cb=vkCallback, value="7"),
   Button((109, 81, 50, 50), bg='2',     cb=vkCallback, value="2"),
   Button((109,134, 50, 50), bg='5',     cb=vkCallback, value="5"),
   Button((109,187, 50, 50), bg='8',     cb=vkCallback, value="8"),
   Button((162, 81, 50, 50), bg='3',     cb=vkCallback, value="3"),
   Button((162,134, 50, 50), bg='6',     cb=vkCallback, value="6"),
   Button((162,187, 50, 50), bg='9',     cb=vkCallback, value="9"),
   Button((215, 81, 50, 50), bg='dot',     cb=vkCallback, value="."),
   Button((215,134, 50, 50), bg='0',     cb=vkCallback, value="0"),
   Button((215,187,103, 50), bg='ok',     cb=startPing),
   Button((268, 81, 50, 50), bg='del',     cb=vkCallback, value='-1'),
   Button((268,134, 50, 50), bg='ret',     cb=goScreen, value=0)],
  # Screen 8 is Pinging
  [Button((  3,  2,262, 25), bg='title_green'),
   Button((268,  2, 50, 25), bg='pause_half'),
   Button((  3,212,103, 25), bg='up_half'),
   Button((109,212,103, 25), bg='down_half'),
   Button((215,212,103, 25), bg='return_half')],
  # Screen 9 小写字母键盘布局
  [Button((  1,  1,318,108), bg='vk_topbg',     cb=checkVkTopBgReturnTarget),
   Button((  1,108, 30, 30), bg='l_q',     cb=vkCallback, value='q'),
   Button(( 33,108, 30, 30), bg='l_w',     cb=vkCallback, value='w'),
   Button(( 65,108, 30, 30), bg='l_e',     cb=vkCallback, value='e'),
   Button(( 97,108, 30, 30), bg='l_r',     cb=vkCallback, value='r'),
   Button((129,108, 30, 30), bg='l_t',     cb=vkCallback, value='t'),
   Button((161,108, 30, 30), bg='l_y',     cb=vkCallback, value='y'),
   Button((193,108, 30, 30), bg='l_u',     cb=vkCallback, value='u'),
   Button((225,108, 30, 30), bg='l_i',     cb=vkCallback, value='i'),
   Button((257,108, 30, 30), bg='l_o',     cb=vkCallback, value='o'),
   Button((289,108, 30, 30), bg='l_p',     cb=vkCallback, value='p'),
   Button((  1,140, 14, 30), bg='vk_halfshuxian',     cb=vkCallback, value='|'),
   Button(( 17,140, 30, 30), bg='l_a',     cb=vkCallback, value='a'),
   Button(( 49,140, 30, 30), bg='l_s',     cb=vkCallback, value='s'),
   Button(( 81,140, 30, 30), bg='l_d',     cb=vkCallback, value='d'),
   Button((113,140, 30, 30), bg='l_f',     cb=vkCallback, value='f'),
   Button((145,140, 30, 30), bg='l_g',     cb=vkCallback, value='g'),
   Button((177,140, 30, 30), bg='l_h',     cb=vkCallback, value='h'),
   Button((209,140, 30, 30), bg='l_j',     cb=vkCallback, value='j'),
   Button((241,140, 30, 30), bg='l_k',     cb=vkCallback, value='k'),
   Button((273,140, 30, 30), bg='l_l',     cb=vkCallback, value='l'),
   Button((305,140, 14, 30), bg='vk_halffenhao',     cb=vkCallback, value=';'),
   Button((  1,172, 30, 30), bg='vk_switch2big',     cb=goScreen, value=10),
   Button(( 33,172, 30, 30), bg='l_z',     cb=vkCallback, value='z'),
   Button(( 65,172, 30, 30), bg='l_x',     cb=vkCallback, value='x'),
   Button(( 97,172, 30, 30), bg='l_c',     cb=vkCallback, value='c'),
   Button((129,172, 30, 30), bg='l_v',     cb=vkCallback, value='v'),
   Button((161,172, 30, 30), bg='l_b',     cb=vkCallback, value='b'),
   Button((193,172, 30, 30), bg='l_n',     cb=vkCallback, value='n'),
   Button((225,172, 30, 30), bg='l_m',     cb=vkCallback, value='m'),
   Button((257,172, 30, 30), bg='vk_fenhao',     cb=vkCallback, value=';'),
   Button((289,172, 30, 30), bg='vk_backspace',     cb=vkCallback, value='-1'),
   Button((  1,204, 30, 30), bg='vk_switch2num',     cb=goScreen, value=12),
   Button(( 33,204, 30, 30), bg='vk_switch2sym',     cb=goScreen, value=11),
   Button(( 65,204, 30, 30), bg='vk_jianhao',     cb=vkCallback, value='-'),
   Button(( 97,204, 94, 30), bg='vk_space',     cb=vkCallback, value=' '),
   Button((193,204, 30, 30), bg='vk_dot',     cb=vkCallback, value='.'),
   Button((225,204, 30, 30), bg='vk_maohao',     cb=vkCallback, value=':'),
   Button((257,204, 30, 30), bg='vk_return',     cb=checkReturnTarget),
   Button((289,204, 30, 30), bg='vk_ok',     cb=checkTarget)],
  # Screen 10 : 大写字母键盘布局
  [Button((  1,  1,318,108), bg='vk_topbg',     cb=checkVkTopBgReturnTarget),
   Button((  1,108, 30, 30), bg='b_q',     cb=vkCallback, value='Q'),
   Button(( 33,108, 30, 30), bg='b_w',     cb=vkCallback, value='W'),
   Button(( 65,108, 30, 30), bg='b_e',     cb=vkCallback, value='E'),
   Button(( 97,108, 30, 30), bg='b_r',     cb=vkCallback, value='R'),
   Button((129,108, 30, 30), bg='b_t',     cb=vkCallback, value='T'),
   Button((161,108, 30, 30), bg='b_y',     cb=vkCallback, value='Y'),
   Button((193,108, 30, 30), bg='b_u',     cb=vkCallback, value='U'),
   Button((225,108, 30, 30), bg='b_i',     cb=vkCallback, value='I'),
   Button((257,108, 30, 30), bg='b_o',     cb=vkCallback, value='O'),
   Button((289,108, 30, 30), bg='b_p',     cb=vkCallback, value='P'),
   Button((  1,140, 14, 30), bg='vk_halfshuxian',     cb=vkCallback, value='|'),
   Button(( 17,140, 30, 30), bg='b_a',     cb=vkCallback, value='A'),
   Button(( 49,140, 30, 30), bg='b_s',     cb=vkCallback, value='S'),
   Button(( 81,140, 30, 30), bg='b_d',     cb=vkCallback, value='D'),
   Button((113,140, 30, 30), bg='b_f',     cb=vkCallback, value='F'),
   Button((145,140, 30, 30), bg='b_g',     cb=vkCallback, value='G'),
   Button((177,140, 30, 30), bg='b_h',     cb=vkCallback, value='H'),
   Button((209,140, 30, 30), bg='b_j',     cb=vkCallback, value='J'),
   Button((241,140, 30, 30), bg='b_k',     cb=vkCallback, value='K'),
   Button((273,140, 30, 30), bg='b_l',     cb=vkCallback, value='L'),
   Button((305,140, 14, 30), bg='vk_halffenhao',     cb=vkCallback, value=';'),
   Button((  1,172, 30, 30), bg='b_shift',     cb=goScreen, value=9),
   Button(( 33,172, 30, 30), bg='b_z',     cb=vkCallback, value='Z'),
   Button(( 65,172, 30, 30), bg='b_x',     cb=vkCallback, value='X'),
   Button(( 97,172, 30, 30), bg='b_c',     cb=vkCallback, value='C'),
   Button((129,172, 30, 30), bg='b_v',     cb=vkCallback, value='V'),
   Button((161,172, 30, 30), bg='b_b',     cb=vkCallback, value='B'),
   Button((193,172, 30, 30), bg='b_n',     cb=vkCallback, value='N'),
   Button((225,172, 30, 30), bg='b_m',     cb=vkCallback, value='M'),
   Button((257,172, 30, 30), bg='vk_fenhao',     cb=vkCallback, value=';'),
   Button((289,172, 30, 30), bg='vk_backspace',     cb=vkCallback, value='-1'),
   Button((  1,204, 30, 30), bg='vk_switch2num',     cb=goScreen, value=12),
   Button(( 33,204, 30, 30), bg='vk_switch2sym',     cb=goScreen, value=11),
   Button(( 65,204, 30, 30), bg='vk_jianhao',     cb=vkCallback, value='-'),
   Button(( 97,204, 94, 30), bg='vk_space',     cb=vkCallback, value=' '),
   Button((193,204, 30, 30), bg='vk_dot',     cb=vkCallback, value='.'),
   Button((225,204, 30, 30), bg='vk_maohao',     cb=vkCallback, value=':'),
   Button((257,204, 30, 30), bg='vk_return',     cb=checkReturnTarget),
   Button((289,204, 30, 30), bg='vk_ok',     cb=checkTarget)],
  # Screen 11 : 符号&数字键盘布局
  [Button((  1,  1,318,108), bg='vk_topbg',     cb=checkVkTopBgReturnTarget),
   Button((  1,108, 30, 30), bg='vk_tanhao',     cb=vkCallback, value='!'),
   Button(( 33,108, 30, 30), bg='vk_at',     cb=vkCallback, value='@'),
   Button(( 65,108, 30, 30), bg='vk_sharp',     cb=vkCallback, value='#'),
   Button(( 97,108, 30, 30), bg='vk_dollar',     cb=vkCallback, value='$'),
   Button((129,108, 30, 30), bg='vk_percent',     cb=vkCallback, value='%'),
   Button((161,108, 30, 30), bg='vk_and',     cb=vkCallback, value='&'),
   Button((193,108, 30, 30), bg='vk_1',     cb=vkCallback, value='1'),
   Button((225,108, 30, 30), bg='vk_2',     cb=vkCallback, value='2'),
   Button((257,108, 30, 30), bg='vk_3',     cb=vkCallback, value='3'),
   Button((289,108, 30, 30), bg='vk_0',     cb=vkCallback, value='0'),
   Button((  1,140, 30, 30), bg='vk_zuoguohao',     cb=vkCallback, value='('),
   Button(( 33,140, 30, 30), bg='vk_youguohao',     cb=vkCallback, value=')'),
   Button(( 65,140, 30, 30), bg='vk_bottomlines',     cb=vkCallback, value='_'),
   Button(( 97,140, 30, 30), bg='vk_equal',     cb=vkCallback, value='='),
   Button((129,140, 30, 30), bg='vk_add',     cb=vkCallback, value='+'),
   Button((161,140, 30, 30), bg='vk_jianhao',     cb=vkCallback, value='-'),
   Button((193,140, 30, 30), bg='vk_4',     cb=vkCallback, value='4'),
   Button((225,140, 30, 30), bg='vk_5',     cb=vkCallback, value='5'),
   Button((257,140, 30, 30), bg='vk_6',     cb=vkCallback, value='6'),
   Button((289,140, 30, 30), bg='vk_dotdark',     cb=vkCallback, value='.'),
   Button((  1,172, 30, 30), bg='vk_fenhao',     cb=vkCallback, value=';'),
   Button(( 33,172, 30, 30), bg='vk_maohao',     cb=vkCallback, value=':'),
   Button(( 65,172, 30, 30), bg='vk_danyinhao',     cb=vkCallback, value="'"),
   Button(( 97,172, 30, 30), bg='vk_shuangyinhao',     cb=vkCallback, value='"'),
   Button((129,172, 30, 30), bg='vk_chenghao',     cb=vkCallback, value='*'),
   Button((161,172, 30, 30), bg='vk_lt2rb',     cb=vkCallback, value='\\'),
   Button((193,172, 30, 30), bg='vk_7',     cb=vkCallback, value='7'),
   Button((225,172, 30, 30), bg='vk_8',     cb=vkCallback, value='8'),
   Button((257,172, 30, 30), bg='vk_9',     cb=vkCallback, value='9'),
   Button((289,172, 30, 30), bg='vk_backspace',     cb=vkCallback, value='-1'),
   Button((  1,204, 30, 30), bg='vk_emptyswitch',     cb=goScreen, value=9),
   Button(( 33,204, 30, 30), bg='vk_ldaguohao',     cb=vkCallback, value='{'),
   Button(( 65,204, 30, 30), bg='vk_rdaguohao',     cb=vkCallback, value='}'),
   Button(( 97,204, 30, 30), bg='vk_lzhongguohao',     cb=vkCallback, value='['),
   Button((129,204, 30, 30), bg='vk_rzhongguohao',     cb=vkCallback, value=']'),
   Button((161,204, 30, 30), bg='vk_lb2rt',     cb=vkCallback, value='/'),
   Button((193,204, 30, 30), bg='vk_xiaoyu',     cb=vkCallback, value='<'),
   Button((225,204, 30, 30), bg='vk_dayu',     cb=vkCallback, value='>'),
   Button((257,204, 30, 30), bg='vk_return',     cb=checkReturnTarget),
   Button((289,204, 30, 30), bg='vk_ok',     cb=checkTarget)],
# Screen 12 : 数字键盘布局
  [Button((  1,  1,318,108), bg='vk_topbg',     cb=checkVkTopBgReturnTarget),
   Button((  1,108, 30, 40), bg='vk_switch2symbig',     cb=goScreen, value=11),
   Button(( 33,108, 62, 40), bg='vk_1big',     cb=vkCallback, value='1'),
   Button(( 97,108, 62, 40), bg='vk_2big',     cb=vkCallback, value='2'),
   Button((161,108, 62, 40), bg='vk_3big',     cb=vkCallback, value='3'),
   Button((225,108, 62, 40), bg='vk_0big',     cb=vkCallback, value='0'),
   Button((289,108, 30, 40), bg='vk_backspacebig',     cb=vkCallback, value='-1'),
   Button((  1,150, 30, 84), bg='vk_switch2letterbig',     cb=goScreen, value=9),
   Button(( 33,150, 62, 40), bg='vk_4big',     cb=vkCallback, value='4'),
   Button(( 97,150, 62, 40), bg='vk_5big',     cb=vkCallback, value='5'),
   Button((161,150, 62, 40), bg='vk_6big',     cb=vkCallback, value='6'),
   Button((225,150, 62, 40), bg='vk_dotbig',     cb=vkCallback, value='.'),
   Button((289,150, 30, 40), bg='vk_returnbig',     cb=checkReturnTarget),
   Button(( 33,192, 62, 42), bg='vk_7big',     cb=vkCallback, value='7'),
   Button(( 97,192, 62, 42), bg='vk_8big',     cb=vkCallback, value="8"),
   Button((161,192, 62, 42), bg='vk_9big',     cb=vkCallback, value='9'),
   Button((225,192, 94, 42), bg='vk_okbig',     cb=checkTarget)],
# Screen 13 : 控制台窗口
  [Button((  0,210,224, 30), bg='con_title',     cb=continueDrawConsoleRows),
   Button((226,210, 30, 30), bg='con_up',     cb=rollingConsoleRows, value='up'),
   Button((258,210, 30, 30), bg='con_down',     cb=rollingConsoleRows, value='down'),
   Button((290,210, 30, 30), bg='con_close',     cb=returnFromConsole)],
# Screen 14:确认对话框
  [#Button(( 14, 13,292, 70), bg='confirm_title'),
   Button(( 14, 87,144, 70), bg='yes',     cb=checkTarget),
   Button((162, 87,144, 70), bg='no',     cb=chkCfmReturnScreen)],
# Screen 15:设置窗口
  [Button(( 15, 14, 70, 70), bg='reset', cb=resetNetworkClick),
   Button((237,162, 70, 70), bg='icon_ret', cb=goScreen,value=0)]
]

# Assorted utility functions -----------------------------------------------

def saveSettings():
	global v
	try:
	  outfile = open('tools.pkl', 'wb')
	  # Use a dictionary (rather than pickling 'raw' values) so
	  # the number & order of things can change without breaking.
	  pickle.dump(v, outfile)
	  outfile.close()
	except:
	  pass

def loadSettings():
	global v
	try:
	  infile = open('tools.pkl', 'rb')
	  v = pickle.load(infile)
	  infile.close()
	except:
	  pass

# Initialization -----------------------------------------------------------

# Init framebuffer/touchscreen environment variables
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV'      , '/dev/fb1')
os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')


# Init pygame and screen
print "X-Pi(NetworkTools) V0.7b1"
print "Initting..."
pygame.init()
print "Setting Mouse invisible..."
pygame.mouse.set_visible(False)
print "Setting fullscreen..."
modes = pygame.display.list_modes(16)
screen = pygame.display.set_mode(modes[0], FULLSCREEN, 16)

print "Loading Icons..."
# Load all icons at startup.
for file in os.listdir(iconPath):
  if fnmatch.fnmatch(file, '*.png'):
    icons.append(Icon(file.split('.')[0]))
# Assign Icons to Buttons, now that they're loaded
print"Assigning Buttons"
for s in buttons:        # For each screenful of buttons...
  for b in s:            #  For each button on screen...
    for i in icons:      #   For each icon...
      if b.bg == i.name: #    Compare names; match?
        b.iconBg = i     #     Assign Icon to Button
        b.bg     = None  #     Name no longer used; allow garbage collection
      if b.fg == i.name:
        b.iconFg = i
        b.fg     = None

#print"Load Settings"
#loadSettings() # Must come last; fiddles with Button/Icon states

print "loading background.."
img    = pygame.image.load("icons/splash.png")
imgworking = pygame.image.load("icons/bg4working.png")
if img is None or img.get_height() < 240: # Letterbox, clear background
  screen.fill(0)
if img:
  screen.blit(img,((320 - img.get_width() ) / 2, (240 - img.get_height()) / 2))
pygame.display.update()
sleep(2)
img    = pygame.image.load("icons/blankbg.png")
# Main loop ----------------------------------------------------------------
print "mainloop.."
while(True):

	# Process touchscreen input
	while True:
		for event in pygame.event.get():
			if(event.type is MOUSEBUTTONDOWN):
				pos = pygame.mouse.get_pos()
				for b in buttons[screenMode]:
					if b.selected(pos): break
		if screenMode >= 0 or screenMode != screenModePrior: break

	if screenMode > 0:
		screen.blit(imgworking,((320 - img.get_width() ) / 2, (240 - img.get_height()) / 2))
	else:
		screen.blit(img,((320 - img.get_width() ) / 2, (240 - img.get_height()) / 2))
	# Overlay buttons on display and update
	for i,b in enumerate(buttons[screenMode]):
		b.draw(screen)

	#显示网络设置信息
	if screenMode == 0:
		myfont = pygame.font.SysFont(fontName,28)
		lblTime = myfont.render(time.strftime('%H:%M:%S',time.localtime(time.time())),1,(255,255,255))
		screen.blit(lblTime,(20,35))
		#myfont = pygame.font.SysFont(fontName,16)
		#lblTime = myfont.render(time.strftime('%y-%m-%d',time.localtime(time.time())),1,(255,255,255))
		#screen.blit(lblTime,(64,66))
	#修改DNS界面
	if screenMode == 2:
		drawWifiOnScreen()
	if screenMode == 3:
		showTextInputed()
	if screenMode == 4:
		dispNetworkInfo()
	#修改网络配置的界面
	if screenMode == 5:
		showTextInputed()
	#Ping命令的设置界面
	if screenMode == 7:
		lastVkScreenMode = screenMode
		showTextInputed()
	#各种虚拟键盘模式
	if screenMode == 9 or screenMode == 10 or screenMode == 11 or screenMode == 12:
		lastVkScreenMode = screenMode
		showTextInputed()
	if screenMode == 13:
		myfont = pygame.font.SysFont(fontName,16)
		if busy is True:
			lblCurText = myfont.render(tempCmd[0:21] , 1 , (255,255,255))
		else:
			lblCurText = myfont.render('Cmd run complete!' , 1 , (255,255,255))
		screen.blit(lblCurText,(3,215))
		#当没有点击手动滚动按钮时，滚动显示文本
		#当点击手动滚动按钮后，停止自动滚动显示文本，显示指定列表的文本。
		if isManualRolling is not True:
			dispConsoleResult()
		else:
			drawConsoleLines(manualLineList,3,3)
	if screenMode == 14:
		showTextInputed()
	#os.system("echo '0' > /sys/class/gpio/gpio252/value")
	pygame.display.update()
	screenModePrior = screenMode
#待完善内容1、退出时增加关机，重启，退出按钮，用Screen1 
#3、修改DNS 用Screen2
#界面排序：
#第一行：时钟*2（点击查看IP），修改IP，修改DNS
#第二行：Ping，Traceroute，ScanIP，ScanPort
#第三行：无线设置，自定义命令，设置，退出
