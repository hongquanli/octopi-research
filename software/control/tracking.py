class Tracker_XY(object):
	def __init__(self):
		pass

	def track(self,image):
		pass

class Tracker_Z(object):
	def __init__(self):
		pass

	def track(self,image):
		pass


class PID_Controller(object):
	def __init__(self):
		self.P = 0
		self.I = 0
		self.D = 0

	def get_actuation(self,error):
		pass

	def set_P(self,P):
		self.P = P
	def set_I(self,I):
		self.I = I
	def set_D(self,D):
		self.D = D

