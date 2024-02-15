"""
Generic Lumencor laser control via HTTP (ethernet connection).
Bogdan 3/19

revised HL 2/2024
"""
import urllib.request
import traceback

def lumencor_httpcommand(command = 'GET IP',ip = '192.168.201.200'):
    """
    Sends commands to the lumencor system via http.
    Plese find commands here:
    http://lumencor.com/wp-content/uploads/sites/11/2019/01/57-10018.pdf
    """
    command_full = r'http://'+ip+'/service/?command='+command.replace(' ','%20')
    with urllib.request.urlopen(command_full) as response:
        message = eval(response.read()) # the default is conveniently JSON so eval creates dictionary
    return message

class CELESTA(object):
    """
    This controls a lumencor object (default: Celesta) using HTTP.
    Please connect the provided cat5e, RJ45 ethernet cable between the PC and Lumencor system.
    """
    def __init__(self, **kwds):
        """
        Connect to the Lumencor system via HTTP and check if you get the right response.
        """
        self.on = False
        self.ip = kwds.get('ip', '192.168.201.200')
        [self.pmin, self.pmax] = 0,1000
        try:
            # See if the system returns back the right IP.
            self.message = self.getIP()
            assert (self.message['message'] == 'A IP '+self.ip)
            self.n_lasers = self.getNumberLasers()
            self.live = True
        except:
            print(traceback.format_exc())
            self.live = False
            print("Failed to connect to Lumencor Laser at ip:", ip)

        if self.live:
            [self.pmin, self.pmax] = self.getPowerRange()
            self.setExtControl(True)
            for i in range(self.n_lasers:)
                if (not self.getLaserOnOff(i)):
                    self.setLaserOnOff(i,False)

    def getNumberLasers(self):
        """Return the number of lasers the current lumencor system can control"""
        self.message = lumencor_httpcommand(command ='GET CHMAP', ip=self.ip)
        if self.message['message'][0]=='A':
            return len(self.message['message'].split(' '))-2
        return 0

    def getColor(self,laser_id):
        """Returns the color of the current laser"""
        self.message = lumencor_httpcommand(command ='GET CHMAP', ip=self.ip)
        colors = self.message['message'].split(' ')[2:]
        print(colors)
        return colors[int(laser_id)]

    def getIP(self):
        self.message = lumencor_httpcommand(command = 'GET IP', ip=self.ip)
        return self.message

    def getExtControl(self):
        """
        Return True/False the lasers can be controlled with TTL.
        """
        self.message = lumencor_httpcommand(command = 'GET TTLENABLE', ip=self.ip)
        response = self.message['message']
        return response[-1]=='1'

    def setExtControl(self, mode):
        """
        Turn on/off external TTL control mode.
        """
        if mode:
            ttl_enable = '1'
        else:
            ttl_enable = '0'
        self.message = lumencor_httpcommand(command = 'SET TTLENABLE '+ttl_enable,ip=self.ip)

    def getLaserOnOff(self,laser_id):
        """
        Return True/False the laser is on/off.
        """
        self.message = lumencor_httpcommand(command = 'GET CH '+laser_id, ip=self.ip)
        response = self.message['message']
        self.on = response[-1]=='1'
        return self.on

    def getPowerRange(self):
        """
        Return [minimum power, maximum power].
        """
        max_int =1000 # default
        self.message = lumencor_httpcommand(command = 'GET MAXINT', ip=self.ip)
        if self.message['message'][0]=='A':
            max_int = float(self.message['message'].split(' ')[-1])
        return [0, max_int]

    def getPower(self,laser_id):
        """
        Return the current laser power.
        """
        self.message = lumencor_httpcommand(command = 'GET CHINT '+laser_id, ip=self.ip)
        response = self.message['message']
        power = float(response.split(' ')[-1])
        return power

    def setLaserOnOff(self, laser_id, on):
        """
        Turn the laser on/off.
        """
        if on:
            self.message = lumencor_httpcommand(command = 'SET CH '+laser_id+' 1', ip=self.ip)
            self.on = True
        else:
            self.message = lumencor_httpcommand(command = 'SET CH '+laser_id+' 0', ip=self.ip)
            self.on = False
        print("Turning On/Off", self.on, self.message)

    def setPower(self, laser_id, power_in_mw):
        """
        power_in_mw - The desired laser power in mW.
        """
        print("Setting Power", power_in_mw, self.message)
        if power_in_mw > self.pmax:
            power_in_mw = self.pmax
        self.message = lumencor_httpcommand(command ='SET CHINT '+laser_id+' '+ str(int(power_in_mw)), ip=self.ip)
        if self.message['message'][0]=='A':
            return True
        return False

    def shutDown(self):
        """
        Turn the laser off.
        """
        if self.live:
            for i in range(self.n_lasers):
                self.setPower(i,0)
                self.setLaserOnOff(i,False)

    def getStatus(self):
        """
        Get the status
        """
        return self.live

#
# The MIT License
#
# Copyright (c) 2013 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
