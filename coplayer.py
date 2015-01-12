# coding=UTF-8
import os
import re
import time
import threading
import subprocess
import mpd
import random
import pygame
import netifaces
import Adafruit_GPIO          as     GPIO
import Adafruit_GPIO.MCP230xx as     Raspi_MCP230XX
from   pygame.locals          import *
from   time                   import sleep
from   mutagen                import File

# exit function
def exitSystem(n):
    global screenMode
    print "Exiting..."
    print "Bye..."
    if   n == 0:
        raise SystemExit
    elif n == 1:
        os.system('sudo halt -h')
    elif n == 2:
        os.system('sudo reboot')
    elif n == 3:
        screenMode = 0

# init control keys
def initMcp():
    global mcp
    mcp = Raspi_MCP230XX.MCP23008(address = 0x20)
    for i in range(0,8):
        mcp.setup(i,GPIO.IN)
        mcp.pullup(i,True)
    
# init MPD socket,one for read settings,another for change settings
def initMPDConnection():
    global MPDClient,MPDClientW
    MPDClient = mpd.MPDClient() #use_unicode=True
    MPDClient.connect("localhost", 6600)
    
# Disconnect MPD socket
def disconnectMPD():
    global MPDClient
    MPDClient.disconnect()

# Remove invalid string or AD string
def removeAD(s):
    s = s.strip()
    s.replace('\n','')
    s.replace('[www.51ape.com]','')
    s.replace('[51ape.com]','')
    s.replace('Ape.Com]','')
    s.replace('file: USB//','')
    return s
    
# Unicode encoding
def u(s):
    return unicode(s,'utf-8')
    
# get CurrentPlaying():
def getCurrentPlaying():
    global MPDClient,theTitle,theArtist,theAlbum,prevSong,fileName,hdFileNames,isHD,imgCoverRender,hasCover,rndCoverNum
    lock.acquire()
    try:
        cs    =  MPDClient.currentsong()
    finally:
        lock.release()
    theTitle  = removeAD(cs.get('title',''))
    theArtist = removeAD(cs.get('artist',''))
    theAlbum  = removeAD(cs.get('album',''))
    fileName  = cs.get('file','')
    if theTitle == "":
        theTitle = fileName

    if ( fileName is not '' ) and ( fileName[-4:].lower() in hdFileNames ):
        isHD = True
    else:
        isHD = False
    # judge if new song be playing (by checking filename).
    if prevSong != fileName:
        initEventTime()
        print "now playing:" + theTitle
        getCoverImage(fileName)
        if hasCover:
            imgCoverRender =  pygame.transform.scale(pygame.image.load("cover.jpg").convert(), (128,128))
        else:
            rndCoverNum = random.randint(0, len(imgCovers) - 1)
    prevSong = fileName

# init event time
def initEventTime():
    global lastEventTime
    lastEventTime = time.time()
    
# init menu countdown time
def initMenuTime():
    global lastMenuTime
    lastMenuTime = time.time()
    
# Get playlist
def getPlaylist():
    global MPDClient,playList,curMenuItem
    lock.acquire()
    try:
        playList = MPDClient.playlist()
    finally:
        lock.release()
    #if there's no music file jump to update playlist menu
    #if len(playList) == 0:
    # screenMode = 2
    # curMenuItem = 6

# Get playlist for displaying
def getScreenList():
    global pageCount,curPage,playList,screenList,actualScreenLines
    screenList = []
    #print playList
    if (curPage > 1) and (curPage == pageCount):
        actualScreenLines = len(playList) - ( pageCount -1) * maxScreenLines
    elif pageCount == 1:
        actualScreenLines = len(playList)
    else:
        actualScreenLines = maxScreenLines
    for i in range(0,actualScreenLines):
        screenList.append((playList[maxScreenLines * (curPage - 1) + i]).strip("file: USB//"))

# Jump to playlist screen
def gotoPlaylist():
    global screenMode,playList,pageCount
    getPlaylist()
    pageCount = (len(playList) + maxScreenLines - 1) / maxScreenLines
    initMenuTime()
    screenMode = 1
    
# Jump to the specified page
def setPage(n):
    global pageCount,curPage,cursorPosition,maxScreenLines
    if n:
        if curPage < pageCount:
            curPage = curPage + 1
            cursorPosition = 1
    else:
        if curPage > 1:
            curPage = curPage - 1
            cursorPosition = maxScreenLines

# Get MPD Status
def getPlayerStates():
    global isRepeat,isRandom,isSingle,isConsume,theVolume,theVolumeIcon,playState,theTime,theVolume,s,menuMPDSettings
    lock.acquire()
    try:
        s = MPDClient.status()
    finally:
        lock.release()
    #print s
    menuMPDSettings[0][1] = int(s.get('repeat',0))
    menuMPDSettings[1][1] = int(s.get('random',0))
    menuMPDSettings[2][1] = int(s.get('single',0))
    menuMPDSettings[3][1] = int(s.get('consume',0))
    isRepeat  = bool(menuMPDSettings[0][1])
    isRandom  = bool(menuMPDSettings[1][1])
    isSingle  = bool(menuMPDSettings[2][1])
    isConsume = bool(menuMPDSettings[3][1])
    if s.get('state') == 'play':
        playState = True
    else:
        playState = False
    theTime   = s.get('time','0:1')
    theVolume = int(s.get('volume','80'))
    theVolumeIcon = int(int(s.get('volume','80')) / 80.0 * 6)

# Set MPD status
def setMPDStatus(i,v):
    global theVolume,pageCount,curPage,maxScreenLines
    lock.acquire()
    try:
        if i == 'single' or i == 3:
            MPDClient.single(v)
        elif i == 'random' or i == 2:
            MPDClient.random(v)
        elif i == 'consume' or i == 4:
            MPDClient.consume(v)
        elif i == 'repeat' or i == 1:
            MPDClient.repeat(v)
        elif i == 'previous':
            MPDClient.previous()
        elif i == 'next':
            MPDClient.next()
        elif i == 'toggle':
            if playState:
                MPDClient.pause()
            else:
                MPDClient.play()
        elif i == 'volume':
            if v:
                if theVolume <= 78:
                    theVolume = int(theVolume) + 2
            else:
                if theVolume >= 10:
                    theVolume = int(theVolume) - 2
            MPDClient.setvol(str(theVolume))
        elif i == 'update':
            MPDClient.clear()
            MPDClient.update()
            MPDClient.findadd("any","")
        elif i == 'songid':
            if pageCount == 1:
                MPDClient.play(str(v-1))
            else:
                MPDClient.play(str((curPage - 1) * maxScreenLines + v -1))
    finally:
        lock.release()
        
# check string if there are chinese char
def checkCharChinese(s):
    for ch in s.decode('utf-8'):
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False

# specified screen do specified operation
# 0:home,1:playlist,2:menu,3:exit
# Main Screen key parse
def k_Main(b):
    global screenMode,menu,menuMain,menuTitle,cursorPosition,menuOffset,showMessage,cursorPosition
    if showMessage:
        return
    if b is k_up:
        setMPDStatus('volume',True)
    elif b is k_down:
        setMPDStatus('volume',False)
    elif b is k_left:
        setMPDStatus('previous',True)
    elif b is k_right:
        setMPDStatus('next',True)
    elif b is k_middle:
        initMenuTime()
        initMenu(menuMain,'系统设置')
    elif b is k_ok:
        setMPDStatus('toggle',True)
    elif b is k_cancel:
        cursorPosition = 1
        gotoPlaylist()
    elif b is k_exit:
        initMenu(menuExit,'退出系统')
            
# Playlist key parse
def k_PlayList(b):
    global screenMode,curPage,pageCount,cursorPosition,maxScreenLines,actualScreenLines,shouldUpdate,menuExit
    shouldUpdate = True
    if b is k_up:
        initMenuTime()
        if cursorPosition > 1:
            cursorPosition = cursorPosition - 1
        elif curPage > 1:
            cursorPosition = maxScreenLines
            setPage(0)
    elif b is k_down:
        initMenuTime()
        if cursorPosition < actualScreenLines:
            cursorPosition = cursorPosition + 1
        elif curPage < pageCount:
            cursorPosition = 1
            setPage(1)
    elif b is k_left:
        initMenuTime()
        setPage(0)
    elif b is k_right:
        initMenuTime()
        setPage(1)
    elif b is k_middle:
        initMenuTime()
        initMenu(menuMain,'系统设置')
    elif b is k_ok:
        initMenuTime()
        setMPDStatus('songid',cursorPosition)
    elif b is k_cancel:
        screenMode = scr_Main
    elif b is k_exit:
        initMenuTime()
        initMenu(menuExit,'退出系统')
        
         
# Network infomation key_parse screenMode is 6
def k_NetworkInfo(b):
    global screenMode,scr_Main,showMessage
    if showMessage:
        return
    if b is k_ok or ok_cancel:
        initMenuTime()
        initMenu(menuNetwork,'网络管理')
    elif b is k_exit:
        initMenuTime()
        screenMode = scr_Main

# InputBox key parse
def k_InputBox(b):
    global screenMode,curPosY,curPosX,curKeyboardX,maxKeys,password,curTyping,showMessage
    if showMessage:
        return
    if b is k_up:
        if curPosY > 0:
            curPosY = curPosY - 1
        elif curPosY == 0:
            curPosY = 3
    elif b is k_down:
        if curPosY < 3:
            curPosY = curPosY + 1
        elif curPosY == 3:
            curPosY = 0
    elif b is k_left:
        if curPosX == 0:
            if curKeyboardX > 0:
                curKeyboardX = curKeyboardX - 1
        elif curPosX > 0:
            curPosX = curPosX - 1
    elif b is k_right:
        if curPosX == maxKeys - 1:
            if curKeyboardX < actualKeys - 9:
                curKeyboardX = curKeyboardX + 1
        elif curPosX < maxKeys - 1:
            curPosX = curPosX + 1
    elif b is k_ok:
        curTyping = curTyping + getCurrentKey()
    elif b is k_cancel:
        curTyping = curTyping[0:-1]
    elif b is k_exit:
        password = curTyping
        dispInfoBox('正在应用新的Wifi设置')
        applyNewNetworkConfig('wifi')


# handle ip address input
def k_InputBoxIP(b):
    global screenMode,curPosXIP,curPosYIP,curTypingIP,kbdNum,curAdpater,showMessage
    if showMessage:
        return
    if b is k_up:
        if curPosYIP > 0:
            curPosYIP = curPosYIP - 1
        elif curPosYIP is 0:
            curPosYIP = 3
    elif b is k_down:
        if curPosYIP < 3:
            curPosYIP = curPosYIP + 1
        elif curPosYIP is 3:
            curPosYIP = 0
    elif b is k_left:
        if curPosXIP > 0:
            curPosXIP = curPosXIP - 1
        elif curPosXIP is 0:
            curPosXIP = 2
    elif b is k_right:
        if curPosXIP < 2:
            curPosXIP = curPosXIP + 1
        elif curPosXIP is 2:
            curPosXIP = 0
    elif b is k_middle:
        if curOp is 'ip':
            initMenu(menuAdpater,curAdpater + '设置')
        elif curOp is 'mask':
            initMenu(menuAdpater,curAdpater + '设置')
        elif curOp is 'gw':
            initMenu(menuAdpater,curAdpater + '设置')
        elif curOp is 'dns1':
            initMenu(menuNetwork,'网络管理')
        elif curOp is 'dns2':
            initMenu(menuNetwork,'网络管理')
    elif b is k_cancel:
        curTypingIP = curTypingIP[:-1] 
    elif b is k_ok:
        curTypingIP = curTypingIP + kbdNum[curPosYIP][curPosXIP]
    elif b is k_exit:
        if curOp is 'ip':
            curIP = curTypingIP
            initMenu(menuAdpater,curAdpater + '设置')
        elif curOp is 'mask':
            curMask = curTypingIP
            initMenu(menuAdpater,curAdpater + '设置')
        elif curOp is 'gw':
            curGW = curTypingIP
            initMenu(menuAdpater,curAdpater + '设置')
        elif curOp is 'dns1':
            applyNewNetworkConfig('dns1')
            initMenu(menuNetwork,'网络管理')
        elif curOp is 'dns2':
            applyNewNetworkConfig('dns2')
            initMenu(menuNetwork,'网络管理')

# applay typing content
def applyNewNetworkConfig(act):
    global screenMode,curIP,curMask,curGW,curPosXIP,curPosYIP,menuNetwork,selectedWifi,password,showMessage
    cmdList = []
    if act is 'manual':
        cmdList.append("ifconfig " + curAdpater + " " + curIP + " netmask " + curMask)
        cmdList.append("route add default gw " + curGW)
    elif act is 'auto':
        cmdList.append("sudo ifconfig " + curAdpater + " auto")
    elif act is 'dns1' or act is 'dns2':
        dnsFile = open('/etc/resolv.conf','w')
        dnsFile.write('nameserver ' + curDNS1 + '\n')
        dnsFile.write('nameserver ' + curDNS2 + '\n')
        dnsFile.close()
    elif act is 'wifi':
        wifiFile = open('/etc/wpa_supplicant/wpa_supplicant.conf','w')
        wifiFile.write("#ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n")
        wifiFile.write("#update_config=1\n")
        wifiFile.write("network={\n")
        wifiFile.write('ssid="' + selectedWifi + '"\n')
        wifiFile.write("proto=RSN\n")
        wifiFile.write("key_mgmt=WPA-PSK\n")
        wifiFile.write("pairwise=CCMP TKIP\n")
        wifiFile.write("group=CCMP TKIP\n")
        wifiFile.write('psk="' + password + '"\n')
        wifiFile.write('}\n')
        wifiFile.close()
        cmdList.append("sudo /etc/init.d/networking restart")
        showMessage = False
        initMenu(menuNetwork,'网络管理')
    for cmd in cmdList:
        print cmd
        os.system(cmd)
    print 'cmd executed complete!' 
    
# check KeyPress
def checkKeyPress():
    global screenMode
    for b in range(0,8):
        if mcp.input(b) is GPIO.LOW:
            if screenMode is scr_Main:
                k_Main(b)
            elif screenMode is scr_Playlist:
                k_PlayList(b)
            elif screenMode is scr_Menu:
                k_Menu(b)
            elif screenMode is scr_MenuNetworkInfo:
                k_NetworkInfo(b)
            elif screenMode is scr_InputBoxIP:
                k_InputBoxIP(b)
            elif screenMode is scr_InputBox:
                k_InputBox(b)
            sleep(0.2)

# get cover image from music file
def getCoverImage(f):
    global hasCover
    imgFile = File('/var/lib/mpd/music/' + f)
    if imgFile.has_key('APIC:e'):
        hasCover = True
        imgCover = imgFile.tags['APIC:e'].data
        with open('cover.jpg', 'wb') as img:
            img.write(imgCover) # write artwork to new image
    else:
        hasCover = False
        
# display basic infomation
def dispInfo():
    global isRepeat,isRandom,isSingle,isConsume,theVolume,playState,theTime,s
    global MPDClient,theTitle,theArtist,theAlbum,prevSong,fileName,hdFileNames,isHD
    global hasCover,rndCoverNum
    getPlayerStates()
    getCurrentPlaying()
    #render background
    screen.fill(0)
    #render cover
    if hasCover:
        screen.blit(imgCoverRender,(0,0))
    else:
        screen.blit(imgCovers[rndCoverNum],(0,0))
    # render status icon
    screen.blit(imgMenu,(1,1))
    if isRepeat:
        screen.blit(imgRepeat,(15,1))
    if isRandom:
        screen.blit(imgRandom,(29,1))
    else:
        screen.blit(imgOrdinal,(29,1))
    if isSingle:
        screen.blit(imgSingle,(43,1))
    if isConsume:
        screen.blit(imgConsume,(57,1))
    if isHD:
        screen.blit(imgHD,(71,1))
    if playState:
        screen.blit(imgPause,(115,1))
    else:
        screen.blit(imgPlay,(115,1))
    if theVolume > -1:
        imgStatus = pygame.image.load("images/volume" + str(theVolumeIcon - 1) + ".png").convert()
        screen.blit(imgStatus,(101,1))
    #render song info
    # Artist
    lblInfo = fontMain.render(" " + u(theArtist), True, (0, 0, 0))
    for x in range(0,3):
        for y in range(0,3):
            screen.blit(lblInfo,(2+x,20+y))
    lblInfo = fontMain.render(" " + u(theArtist), True, (255, 255, 255))
    for x in range(-1,2):
        for y in range(-1,2):
            screen.blit(lblInfo,(2+x,20+y))
    lblInfo = fontMain.render(" " + u(theArtist), True, (255, 0, 0))
    screen.blit(lblInfo,(2,20))
    # Title
    if theTitle == "":
        theTitle = fileName
    lenTitle = len(u(theTitle))
    if checkCharChinese(theTitle):
        maxChar = 6
    else:
        maxChar = 12
    pTitle = lenTitle / maxChar + 1
    for z in range(0,pTitle):
        lblTitle  = fontTitle.render(u(theTitle)[z*maxChar:z*maxChar+maxChar], True, (0, 0, 0))
        for x in range(0,3):
            for y in range(-0,3):
                screen.blit(lblTitle,(5 + x,z * 20 + 42 + y))
        lblTitle  = fontTitle.render(u(theTitle)[z*maxChar:z*maxChar+maxChar], True, (255, 255, 255))
        for x in range(-1,2):
            for y in range(-1,2):
                screen.blit(lblTitle,(5 + x,z * 20 + 42 + y))
        lblTitle  = fontTitle.render(u(theTitle)[z*maxChar:z*maxChar+maxChar], True, (255, 0, 0))
        screen.blit(lblTitle,(5,z * 20 + 42))
    #draw percent
    if ':' in theTime:
        percent = float(theTime.split(":")[0]) / float(theTime.split(":")[1])
    else:
        percent = 0
    #pygame.draw.line(screen, (0,0,255), (28,125), (int(100 * percent),125), 2) 
    #Draw the time
    if int(time.time()) % 2 is 1:
        fmtTime = '%H:%M'
    else:
        fmtTime = '%H %M'
    lblTime = fontSmall.render(time.strftime(fmtTime,time.gmtime()) + '(' + str(int(percent * 100)) + '%)', True, (255, 255, 255))
    screen.blit(lblTime,(1,116))

    pygame.display.update()

# display infobox
def dispInfoBox(info):
    global screenMode,showMessage
    showMessage = True
    screen.fill(0)

    lenInfo = len(u(info))
    if checkCharChinese(info):
        maxChar = 6
    else:
        maxChar = 12
    pInfo = lenInfo / maxChar + 1
    
    for z in range(0,pInfo):
        lblInfo  = fontTitle.render(u(info)[z*maxChar:z*maxChar+maxChar], True, (255, 255, 255))
        screen.blit(lblInfo,(5,z * 20 + 42))
    pygame.display.update()

# display the playlist 
def dispPlayList():
    global screenMode,lastMenuTime,countDownTime,shouldUpdate
    global pageCount,curPage,playList,screenList,actualScreenLines,cursorPosition
    if time.time() - lastMenuTime > countDownTime:
        screenMode = 0
    if shouldUpdate is False:
        return
    getScreenList()
    screen.fill(0)
    #display current page of playlist
    screen.blit(imgMenu,(1,1))
    lblPLStatus = fontSmall.render(' Playlist (' + str(curPage) + '/' + str(pageCount) + ')',1,(255,255,255))
    screen.blit(lblPLStatus,(18,1))
    #render playlist
    for i in range(0,actualScreenLines):
        if cursorPosition is i + 1:
            lblFileName = fontMain.render(u(screenList[i]),1,(  0,255,  0))
        else:
            lblFileName = fontMain.render(u(screenList[i]),1,(255,255,255))
        screen.blit(lblFileName,(5,(i+1) * 16 - 1))
    #draw triangle on the left
    pygame.draw.rect(screen,(0,255,0),Rect((1,(cursorPosition) * 16 + 3),(3,8)))
    pygame.display.update()
    shouldUpdate = False
    
# get ip address
def getNetworkInfo():
    global hasEth0,hasWlan0,eth0IP,wlan0IP,menuNetwork
    try:
        if netifaces.interfaces().index('eth0') > -1:
            hasEth0 = True
    except:
        hasEth0 = False
    if hasEth0:
        try:
            eth0IP = netifaces.ifaddresses('eth0')[netifaces.AF_INET][0]['addr']
        except:
            eth0IP = "none"
    else:
        menuNetwork[3][1] = 0
    # Judge if ther's wlan0        
    try:
        if netifaces.interfaces().index('wlan0') > -1:
            hasWlan0 = True
    except:
        hasWlan0 = False
    if hasWlan0:
        try:
            eth0IP = netifaces.ifaddresses('eth0')[netifaces.AF_INET][0]['addr']
        except:
            wlan0IP = "none"
    else:
        menuNetwork[1][1] = 0
        menuNetwork[2][1] = 0
        
            
# get adpater info
def getAdpaterAddress(adp):
    global curIP,curMask,curGW,curDNS1,curDNS2
    try:
        curIP = netifaces.ifaddresses(adp)[netifaces.AF_INET][0]['addr']
    except:
        curIP = ''
    try:
        curMask = netifaces.ifaddresses(adp)[netifaces.AF_INET][0]['netmask']
    except:
        curMask = ''
    try:
        curGW = netifaces.gateways()['default'][netifaces.AF_INET][0]
    except:
        curGW = ''
    curDNS1 = ''
    curDNS2 = ''
    dnsFile = open("/etc/resolv.conf") 
    line = dnsFile.readline()
    i = 1
    while line:
        line = line.replace('nameserver','')
        line = line.replace(' ','')
        line = line.replace('\n','')
        if isIpAddr(line):
            if i is 1:
                curDNS1 = line
            elif i is 2:
                cruDNS2 = line
            i = i +1
        line = dnsFile.readline()
    dnsFile.close()

# get consle content after executed command
def getConsoleTextCommon():
    global busy,popen,cmd,consoleResult
    global cmd,consoleResult
    consoleResult = []
    popen = subprocess.Popen(cmd.split(' '), stdout = subprocess.PIPE)
    while busy is True :
        cmdLine = popen.stdout.readline()
        if cmdLine <> "":
            consoleResult.append(cmdLine.replace('\n',''))
        else:
            busy = False
    busy = False
    popen.kill()
    print "subProcess over!"
    
# get wifi essid list
def getWifiList():
    global wifiList,cmd,consoleResult,busy
    wifiList = []
    consoleResult = []
    cmd = 'iwlist wlan0 scan'
    busy = True
    t = threading.Thread(target=getConsoleTextCommon)
    t.start()
    while busy is True:
        pass
    for line in consoleResult:
        if line.find('ESSID') > -1:
            wifiItem = []
            wifiItem.append(line[line.find('"') + 1:-1])
            wifiItem.append(-1)
            wifiItem.append('essid')
            wifiList.append(wifiItem)

# test if obj is an ip address
def isIpAddr(varObj):
    rule = r"\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    match = re.match( rule , varObj )
    if match:
        return True
    return False
    
# 显示IP地址信息
def dispCurrentNetworkInfo():
    global screenMode,hasEth0,hasWlan0,wlan0IP,eth0IP,realCountDownTime,countDownTime
    
    realCountDownTime = int(time.time() - lastMenuTime)
    if realCountDownTime > countDownTime:
        initMenuTime()
        screenMode = 5    
        
    screen.fill(0)
    screen.blit(imgMenu,(1,1))
    lblTitle = fontMain.render(u"查看IP地址",1,(255,255,255))
    screen.blit(lblTitle,((128 - lblTitle.get_width()) / 2,0))
    lblTitle = fontSmall.render(str(abs(realCountDownTime - countDownTime)),1,(255,255,255))
    screen.blit(lblTitle,(108,108))
    pygame.draw.rect(screen,(255,255,255),Rect((0,16),(128,2)))
    i = 0
    if hasEth0:
        lblIP = fontSmall.render('Eth0 :' + eth0IP,1,(255,255,255))
        screen.blit(lblIP,(5,(i+1)*16 + 4))
        i = i +1
    if hasWlan0:
        lblIP = fontSmall.render('Wlan0:' + wlan0IP,1,(255,255,255))
        screen.blit(lblIP,(5,(i+1)*16 + 4))
        
    pygame.display.update()
    
# init inputbox of ip input
def initInputBoxIP(op):
    global screenMode,scr_InputBoxIP,curAdpater,curTypingIP,curIP,curMask,curGW,curDNS1,curDNS2,curPosXIP,curPosYIP
    getAdpaterAddress(curAdpater)
    if op is 'ip':
        curTypingIP = curIP
    elif op is 'mask':
        curTypingIP = curMask
    elif op is 'gw':
        curTypingIP = curGW
    elif op is 'dns1':
        curTypingIP = curDNS1
    elif op is 'dns2':
        curTypingIP = curDNS2
    curPosXIP = 0
    curPosYIP = 0
    screenMode = scr_InputBoxIP
# Display Input Box
def dispInputBoxIP():
    global screenMode
    global kbdNum,curPosXIP,curPosYIP
    global curOp,curTypingIP,curAdpater
    global curIP,curMask,curGW,curDNS1,curDNS2
    screen.fill(0)
    #draw curInfomation
    if curOp is 'ip':
        lblInfo = fontSmall.render(curOp + ':' + curIP,  1,(255,255,255))
    elif curOp is 'mask':
        lblInfo = fontSmall.render(curOp + ':' + curMask,1,(255,255,255))
    elif curOp is 'gw':
        lblInfo = fontSmall.render(curOp + ':' + curGW,  1,(255,255,255))
    elif curOp is 'dns1':
        lblInfo = fontSmall.render(curOp + ':' + curDNS1,1,(255,255,255))
    elif curOp is 'dns2':
        lblInfo = fontSmall.render(curOp + ':' + curDNS2,1,(255,255,255))
    screen.blit(lblInfo,(1,1))
    lblInfo = fontSmall.render('New:' + curTypingIP ,1,(255,255,255))
    screen.blit(lblInfo,(1,20))
    pygame.draw.rect(screen,(5,5,5),Rect((0,63),(43,64)))
    pygame.draw.rect(screen,(55,55,55),Rect((2 + 14 * curPosXIP,64 + 16 * curPosYIP),(14,14)))
    for y in range(0,4):
        for x in range(0,3):
            lblKey = fontMain.render(kbdNum[y][x],1,(255,255,255))
            screen.blit(lblKey,(5 + (x * 14), 64 + (y * 16)))
    pygame.display.update()

# init inputbox
def initInputBox():
    global screenMode,scr_InputBox,selectedWifi,curTyping
    curTyping = ''
    screenMode = scr_InputBox
    
# Display Input Box
def dispInputBox():
    global screenMode,kbdDisplay,curPosX,curPosY,curTyping,selectedWifi
    getCurrentKeys()
    screen.fill(0)
    #draw curInfomation
    lblInfo = fontSmall.render(selectedWifi + ':',1,(255,255,255))
    screen.blit(lblInfo,(1,14))
    lblInfo = fontSmall.render(curTyping  ,1,(255,255,255))
    screen.blit(lblInfo,(2,28))
    pygame.draw.rect(screen,(55,55,55),Rect((2 + 14 * curPosX,64 + 16 * curPosY),(14,14)))
    for y in range(0,4):
        for x in range(0,9):
            lblKey = fontMain.render(kbdDisplay[y][x],1,(255,255,255))
            screen.blit(lblKey,(5 + (x * 14), 64 + (y * 16)))
    pygame.display.update()

# get Current Keyboard Keys
# init vars
def getCurrentKeys():
    global curKeyboardX,kbdDisplay,kbdFull
    kbdDisplay = []
    for i in range(0,4):
        kbdDisplay.append(kbdFull[i][curKeyboardX:curKeyboardX + 9])
    
def getCurrentKey():
    global curPosX,curPosY,curKeyboardX,kbdFull,curKey
    curKey = kbdFull[curPosY][curKeyboardX + curPosX]
    return curKey
    
# display SSID list
def dispWifiList():
    global screenMode,wifiList,curWifilistCursor,curWifilistPos
    
    screen.fill(0)
    screen.blit(imgMenu,(1,1))
    lblTitle = fontMain.render(u"选择无线网络",1,(255,255,255))
    screen.blit(lblTitle,((128 - lblTitle.get_width()) / 2,0))
    lblTitle = fontSmall.render(str(abs(realCountDownTime - countDownTime)),1,(255,255,255))
    screen.blit(lblTitle,(108,108))
    pygame.draw.rect(screen,(255,255,255),Rect((0,16),(128,2)))
    curWifilistCursor= 1
    curWifilistPos = 0
    
    tempWifiList = wifiList[curWifilistPos,curWifilistPos + 6]
    
    for i in range(0,len(tempWifiList)):
        lblWifi = fontMain.render(u(tempWifiList[i]),1,(255,255,255))
        screen.blit(lblWifi,(5,(i+1)*16 + 4))
        
    pygame.draw.rect(screen,(255,0,0),Rect((1,(curWifiListY) * 16 + 8),(3,8)))
    pygame.display.update()
    
    
# init menu cursor position m:menu t:title of menu
def initMenu(m,t):
    global screenMode,scr_Menu,menu,menuTitle,menuExit,menuOffset,cursorPosition,shouldUpdate
    menu           = m
    menuTitle      = t
    menuOffset     = 0
    cursorPosition = 0
    shouldUpdate   = True
    screenMode = scr_Menu
    
#dispLay Menu
#struct of Menu
#[[str title,boolean display,str function]
def dispMenu():
    global screenMode,scr_Main,menu,menuTitle,tempMenu,cursorPositon,menuOffset,shouldUpdate,lastMenuTime
    if time.time() - lastMenuTime > countDownTime:
        screenMode = scr_Main
    if shouldUpdate is False:
        return
    #clear screen
    screen.fill(0)
    #blit menu icon
    screen.blit(imgMenu,(1,1))
    #blit menu title
    lblTitle = fontMain.render(u(menuTitle),1,(255,255,255))
    screen.blit(lblTitle,((128 - lblTitle.get_width()) / 2,0))
    #blit top&bottom split line
    pygame.draw.rect(screen,(255,255,255),Rect((0, 16),(128,2)))
    #pygame.draw.rect(screen,(255,255,255),Rect((0,112),(128,2)))
    #blit menu max 6
    tempMenu = menu[menuOffset:menuOffset + maxMenuItems]
    #print tempMenu
    #blit menu items
    for i in range(0, len(tempMenu)):
        if cursorPosition is i:
            lblMenuItem = fontMain.render('[' + u(menu[i][0]) + ']',1,(255,255,0))
        else:
            lblMenuItem = fontMain.render(u(menu[i][0]),1,(255,255,255))
        screen.blit(lblMenuItem,(5,(i+1)*16 + 4))
        if menu[i][1] is 1:
            screen.blit(imgOn ,(110,(i+1)*16 + 4))
        elif menu[i][1] is 0:
            screen.blit(imgOff,(110,(i+1)*16 + 4))
    #update screen
    pygame.display.update()
    #set shouldUpdate to false to avoid repeat screen refresh
    shouldUpdate = False

# parse key function of menu 
# !before display menu should set menuOffset and cursorPosition to 0
def k_Menu(b):
    global screenMode,scr_Main,cursorPosition,menu,tempMenu,menuOffset,shouldUpdate,maxMenuItems,menuOffset,showMessage
    initMenuTime()
    if showMessage:
        return
    totalMenuLength = len(menu)
    tempMenuLength  = len(tempMenu)
    if b is k_up:
        if totalMenuLength > tempMenuLength:
            if cursorPosition is 0:
                if menuOffset is 0:
                    cursorPosition = maxMenuItems - 1
                    menuOffset = totalMenuLength - maxMenuItems -1
                else:
                    menuOffset = menuOffset - 1
            else:
                cursorPosition = cursorPosition - 1
        else:
            if cursorPosition is 0:
                cursorPosition = tempMenuLength - 1
            else:
                cursorPosition = cursorPosition - 1
    elif b is k_down:
        if totalMenuLength > tempMenuLength:
            if cursorPosition is maxMenuItems - 1:
                if menuOffset is totalMenuLength - maxMenuItems - 1:
                    cursorPosition = 0
                    menuOffset = 0
                else:
                    menuOffset = menuOffset + 1
            else:
                cursorPosition = cursorPosition + 1
        else:
            if cursorPosition < tempMenuLength - 1:
                cursorPosition = cursorPosition + 1
            else:
                cursorPosition = 0
    elif b is k_left:
        if menu is menuMain:
            screenMode = scr_Main
        elif menu is menuMPDSettings or menuNetwork or menuExit:
            initMenu(menuMain,'系统设置')
        elif menu is menuAdpater or wifiList:
            initMenu(menuNetwork,'网络管理')
    elif b is k_right:
        parseMenuFunction()
    elif b is k_ok:
        parseMenuFunction()
    elif b is k_cancel:
        if menu is menuMain:
            screenMode = scr_Main
        elif menu is menuMPDSettings or menuNetwork or menuExit:
            initMenu(menuMain,'系统设置')
        elif menu is menuAdpater or wifiList:
            initMenu(menuNetwork,'网络管理')
    elif b is k_exit:
        screenMode = scr_Main
    shouldUpdate = True
    
# parse menuitem function
def parseMenuFunction():
    global screenMode,scr_Main,scr_MenuNetworkInfo,showMessage
    global menu,menuNetworkcursorPosition,menuOffset,shouldUpdate
    global hasWlan0,hasEth0,curOp,curAdpater,selectedWifi
    global menuMPDSettings,isRepeat,isRandom,isSingle,isConsume
    
    menuItemIndex = menuOffset + cursorPosition
    action = menu[menuItemIndex][2] 
    # MenuMain
    if action is 'mpdSetting':
        initMenu(menuMPDSettings,'播放器设置')
    elif action is 'networkSetting':
        getNetworkInfo()
        initMenu(menuNetwork,'网络管理')
    elif action is 'exitSystem':
        initMenu(menuExit,'退出系统')
    # MPD Settings
    elif action is 'repeat':
        getPlayerStates()
        if isRepeat:
            v = 0
        else:
            v = 1
        setMPDStatus('repeat',v)
        menuMPDSettings[0][1] = v
    elif action is 'random':
        getPlayerStates()
        if isRandom:
            v = 0
        else:
            v = 1
        setMPDStatus('random',v)
        menuMPDSettings[1][1] = v
    elif action is 'single':
        getPlayerStates()
        if isSingle:
            v = 0
        else:
            v = 1
        setMPDStatus('single',v)
        menuMPDSettings[2][1] = v
    elif action is 'consume':
        getPlayerStates()
        if isConsume:
            v = 0
        else:
            v = 1
        setMPDStatus('consume',v)
        menuMPDSettings[3][1] = v
    # menu network setting
    elif action is 'viewNetworkSetting':
        screenMode = scr_MenuNetworkInfo
    elif action is 'joinWifi':
        dispInfoBox('正在获取Wifi列表，请等候！')
        getWifiList()
        showMessage = False
        initMenu(wifiList,'Wifi列表')
    elif action is 'wlanSetting':
        if hasWlan0:
            curAdpater = 'wlan0'
            initMenu(menuAdpater,'wlan0设置')
    elif action is 'ethSetting':
        if hasEth0:
            curAdpater = 'eth0'
            initMenu(menuAdpater,'eth0设置')
    elif action is 'dns1Setting':
        curOp = 'dns1'
        initInputBoxIP(curOp)
    elif action is 'dns2Setting':
        curOp = 'dns2'
        initInputBoxIP(curOp)
    # menu adpater setting
    elif action is 'ipSetting':
        curOp = 'ip'
        initInputBoxIP(curOp)
    elif action is 'maskSetting':
        curOp = 'mask'
        initInputBoxIP(curOp)
    elif action is 'gwSetting':
        curOp = 'gw'
        initInputBoxIP(curOp)
    elif action is 'applyAdpaterSetting':
        applyAdpaterSetting('manual')
    elif action is 'applyAdpaterAuto':
        applyAdpaterSetting('auto')
    elif action is 'menuAdpaterReturn':
        initMenu(menuNetwork,'网络管理')
    # menu exit
    elif action is 'halt':
        exitSystem(1)
    elif action is 'reboot':
        exitSystem(2)
    elif action is 'exit':
        exitSystem(0)
    elif action is 'main':
        screenMode = scr_Main
    # connect wifi
    elif action is 'essid':
        selectedWifi = menu[menuItemIndex][0] 
        initInputBox()
   
#getIPAddr()
#exit()
# Print Version Info
print "__________________________"
print "Coled Player V1.0"
print "based on MPD"
print "by FishX"
print "__________________________"
print "loading settings..."

# Gloable Settings
screenMode          = 0      # Current screen mode; default = HOME

scr_Main            = 0
scr_Playlist        = 1
scr_Menu            = 2
scr_InfoBox         = 4
scr_MenuNetworkInfo = 6
scr_WifiList        = 8
scr_InputBoxIP      = 9
scr_InputBox        = 10

# Button Settings
k_up        = 0
k_down      = 1
k_left      = 2
k_right     = 3
k_middle    = 4
k_cancel    = 5
k_ok        = 6
k_exit      = 7

# MPD Status
isRepeat    = False
isRandom    = False
isSingle    = False
isConsume   = False
theVolume   = "50"
playState   = False
theTime     = "0:1"

# Song Info
theTitle    = ""
theArtist   = ""
theAlbum    = ""
prevSong    = "" # prevSong
fileName    = "" # fileName
isHD        = False
hasCover    = False
rndCoverNum = 1
lastEventTime = time.time()

# Other Vars
hdFileNames = ['flac','.ape','.wav']
imgSplash   = pygame.image.load("images/splash.png")
imgWorking  = pygame.image.load("images/bg.png")
imgCovers   = []
for i in range(1,11):
    imgCover = pygame.image.load("images/cover" + str(i) + ".png")
    imgCovers.append(imgCover)

lock        = threading.Lock()

# initSystem Font
print "loading font..."
pygame.font.init()
try:
    fontTitle = pygame.font.Font("/home/pi/coplayer/SourceHanSansCN-Medium.otf",19)
    fontMain  = pygame.font.Font("/home/pi/coplayer/SourceHanSansCN-Light.otf", 14)
    fontSmall = pygame.font.Font("/home/pi/coplayer/DejaVuSansMono.ttf", 10)
except pygame.error, e:
    print e
    exit()

#Playlist settings
actualScreenLines = 7
curPage           = 1
playList          = []
screenList        = []
pageCount         = 0
maxScreenLines    = 7
cursorPosition    = 1

#Menu Settings
countDownTime     = 15

menuMain          = [['播放器设置',-1,'mpdSetting'],
                    ['网络管理',-1,'networkSetting'],
                    ['退出系统',-1,'exitSystem']]

menuMPDSettings   = [['循环播放',-1,'repeat'],
                    ['随机播放',-1,'random'],
                    ['单曲播放',-1,'single'],
                    ['播完即删',-1,'consume']]
                    
menuNetwork       = [['查看网络设置',-1,'viewNetworkSetting'],
                    ['加入无线网络',-1,'joinWifi'],
                    ['无线网络设置',-1,'wlanSetting'],
                    ['有线网络设置',-1,'ethSetting'],
                    ['DNS1设置',-1,'dns1Setting'],
                    ['DNS2设置',-1,'dns2Setting']]

menuAdpater       = [['IP地址设置',-1,'ipSetting'],
                    ['子网掩码设置',-1,'maskSetting'],
                    ['网关设置',-1,'gwSetting'],
                    ['应用以上设置',-1,'applyAdpaterSetting'],
                    ['应用自动获取',-1,'applyAdpaterAuto'],
                    ['返回',-1,'menuAdpaterReturn']]
                    
menuExit          = [['关机',-1,'halt'],
                    ['重启',-1,'reboot'],
                    ['退出程序',-1,'exit'],
                    ['返回主界面',-1,'main']]

menu              = []
menuTitle         = ''
menuOffset        = 0
maxMenuItems      = 6
cursorPosition    = 0
showMessage       = False

shouldUpdate      = True
curMenuItem       = 1            #current menu item (default:halt)
curMenuOptions    = []           #current menu options of current menu
curMenuOptionsPosition = 1       #the position of current menu options

curMenuExitPosition    = 1
lastMenuTime      = time.time()
#Menu Network Settings
hasEth0           = False
hasWlan0          = False

curMenuNetworkPosition = 1
eth0IP            = 'none'
wlan0IP           = 'none'

curAdpater        = ''
curMenuAdpaterPosition = 1
curIP             = ''
curMask           = ''
curGW             = ''
curDNS1           = ''
curDNS2           = ''

#Virtual Keyboard Settings
kbdFull           = [
     ['~','1','2','3','4','5','6','7','8','9','0','!','@','#','$','%','^','&','*','(',')','+','=','|']
    ,['`','q','w','e','r','t','y','u','i','o','p','Q','W','E','R','T','Y','U','I','O','P','"',"'",'\\']
    ,['-',' ','a','s','d','f','g','h','j','k','l',';','A','S','D','F','G','H','J','K','L',';','[',']']
    ,['_','z','x','c','v','b','n','m',',','.','/','Z','X','C','V','B','N','M','<','>','?',':','{','}']]
    
kbdNum            = [
     ['1','2','3']
    ,['4','5','6']
    ,['7','8','9']
    ,['.','0',' ']]

curKeyboardX      = 0
maxKeys           = 9
actualKeys        = len(kbdFull[0])
curPosX           = 0
curPosY           = 0
curPosXIP         = 0
curPosYIP         = 0
curKey            = ''
curTyping         = ''
curTypingIP       = ''

# Init framebuffer/touchscreen environment variables
print "initting video device..."
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV'      , '/dev/fb1')

# Init pygame and screen
print "initting Pygame&Screen..."
pygame.init()
pygame.mouse.set_visible(False)
try:
    screen = pygame.display.set_mode((128,128), FULLSCREEN, 16) # HWSURFACE | 
except pygame.error, e:
    print e
    exit()
    
# load status icons
print "loading icons..."
imgMenu    = pygame.image.load("images/menu.png"      ).convert()
imgRepeat  = pygame.image.load("images/repeat.png"    ).convert()
imgRandom  = pygame.image.load("images/random.png"    ).convert()
imgOrdinal = pygame.image.load("images/ordinal.png"   ).convert()
imgSingle  = pygame.image.load("images/single.png"    ).convert()
imgConsume = pygame.image.load("images/consume.png"   ).convert()
imgHD      = pygame.image.load("images/hd.png"        ).convert()
imgPause   = pygame.image.load("images/pause.png"     ).convert()
imgPlay    = pygame.image.load("images/play.png"      ).convert()
imgOn      = pygame.image.load("images/switch_on.png" ).convert()
imgOff     = pygame.image.load("images/switch_off.png").convert()

# init MCP23008
print "initting keys..."
initMcp()

# Start KeyChecking thread
#tKeyChecking = threading.Thread(target=checkKeyPress)
#tKeyChecking.start()

# init Music Player Daemon
print "initting MPD connection..."
initMPDConnection()

# Display Splash Screen
print "display splash..."
screen.blit(imgSplash,(0, 0))
pygame.display.update()

# get music info before draw them to the screen
getCurrentPlaying()

# Main loop
print "starting..."
#screenMode = 7
#getWifiList()
while(True):
    if screenMode is scr_Main:
        dispInfo()
    elif screenMode is scr_Playlist:
        dispPlayList()
    elif screenMode is scr_Menu:
        dispMenu()
    elif screenMode is scr_MenuNetworkInfo:
        dispCurrentNetworkInfo()
    elif screenMode is scr_InputBoxIP:
        dispInputBoxIP()
    elif screenMode is scr_InputBox:
        dispInputBox()
    checkKeyPress()
