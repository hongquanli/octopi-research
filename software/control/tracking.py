import control.utils_.image_processing as image_processing
import numpy as np
from os.path import realpath, dirname, join

try:
	import torch
	from control.DaSiamRPN.code.net import SiamRPNvot
	print(1)
	from control.DaSiamRPN.code import vot
	print(2) 
	from control.DaSiamRPN.code.utils import get_axis_aligned_bbox, cxy_wh_2_rect
	print(3)
	from control.DaSiamRPN.code.run_SiamRPN import SiamRPN_init, SiamRPN_track
	print(4)
except Exception as e:
	print(e)
	# print('Warning: DaSiamRPN is not available!')
from control._def import Tracking
import cv2

class Tracker_Image(object):
	'''
	SLOTS: update_tracker_type, Connected to: Tracking Widget
	'''

	def __init__(self):
		# Define list of trackers being used(maybe do this as a definition?)
		# OpenCV tracking suite
		# self.OPENCV_OBJECT_TRACKERS = {}
		try:
			self.OPENCV_OBJECT_TRACKERS = {
			"csrt": cv2.TrackerCSRT_create,
			"kcf": cv2.TrackerKCF_create,
			"boosting": cv2.TrackerBoosting_create,
			"mil": cv2.TrackerMIL_create,
			"tld": cv2.TrackerTLD_create,
			"medianflow": cv2.TrackerMedianFlow_create,
			"mosse": cv2.TrackerMOSSE_create
			}
		except:
			print('Warning: OpenCV-Contrib trackers unavailable!')
		
		# Neural Net based trackers
		self.NEURALNETTRACKERS = {"daSiamRPN":[]}
		try:
			# load net
			self.net = SiamRPNvot()
			self.net.load_state_dict(torch.load(join(realpath(dirname(__file__)),'DaSiamRPN','code','SiamRPNOTB.model')))
			self.net.eval().cuda()
			print('Finished loading net ...')
		except Exception as e:
			print(e)
			print('No neural net model found ...')
			print('reverting to default OpenCV tracker')

		# Image Tracker type
		self.tracker_type = Tracking.DEFAULT_TRACKER
		# Init method for tracker
		self.init_method = Tracking.DEFAULT_INIT_METHOD
		# Create the tracker
		self.create_tracker()

		# Centroid of object from the image
		self.centroid_image = None # (2,1)
		self.bbox = None
		self.rect_pts = None
		self.roi_bbox = None
		self.origin = np.array([0,0])

		self.isCentroidFound = False
		self.trackerActive = False
		self.searchArea = None
		self.is_color = None
		
	def track(self, image, thresh_image, is_first_frame = False):

		# case 1: initialize the tracker
		if(is_first_frame == True or self.trackerActive == False):
			# tracker initialization - using ROI
			if(self.init_method=="roi"):
				self.bbox = tuple(self.roi_bbox)
				self.centroid_image = self.centroid_from_bbox(self.bbox)
				self.isCentroidFound = True
			# tracker initialization - using thresholded image
			else:
				self.isCentroidFound, self.centroid_image, self.bbox = image_processing.find_centroid_basic_Rect(thresh_image)
				self.bbox = image_processing.scale_square_bbox(self.bbox, Tracking.BBOX_SCALE_FACTOR, square = True)
			# initialize the tracker
			if(self.bbox is not None):
				print('Starting tracker with initial bbox: {}'.format(self.bbox))
				self._initialize_tracker(image, self.centroid_image, self.bbox)
				self.trackerActive = True
				self.rect_pts = self.rectpts_from_bbox(self.bbox)
		
		# case 2: continue tracking an object using tracking
		else:
			# Find centroid using the tracking.
			objectFound, self.bbox = self._update_tracker(image, thresh_image) # (x,y,w,h)
			if(objectFound):
				self.isCentroidFound = True
				self.centroid_image = self.centroid_from_bbox(self.bbox) + self.origin
				self.bbox = np.array(self.bbox)
				self.bbox[0], self.bbox[1] = self.bbox[0] + self.origin[0], self.bbox[1] + self.origin[1]
				self.rect_pts = self.rectpts_from_bbox(self.bbox)
			else:
				print('No object found ...')
				self.isCentroidFound = False
				self.trackerActive = False
		return self.isCentroidFound, self.centroid_image, self.rect_pts

	def reset(self):
		print('Reset image tracker state')
		self.is_first_frame = True
		self.trackerActive = False
		self.isCentroidFound = False

	def create_tracker(self):
		if(self.tracker_type in self.OPENCV_OBJECT_TRACKERS.keys()):
			self.tracker = self.OPENCV_OBJECT_TRACKERS[self.tracker_type]()
		elif(self.tracker_type in self.NEURALNETTRACKERS.keys()):
			print('Using {} tracker'.format(self.tracker_type))
			pass

	def _initialize_tracker(self, image, centroid, bbox):
		# check if the image is color or not
		if(len(image.shape)<3):
			self.is_color = False		
		# Initialize the OpenCV based tracker
		if(self.tracker_type in self.OPENCV_OBJECT_TRACKERS.keys()):
			print('Initializing openCV tracker')
			print(self.tracker_type)
			print(bbox)
			if(self.is_color == False):
				image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
			self.create_tracker() # for a new track, just calling self.tracker.init(image,bbox) is not sufficient, this line needs to be called
			self.tracker.init(image, bbox)
		# Initialize Neural Net based Tracker
		elif(self.tracker_type in self.NEURALNETTRACKERS.keys()):
			# Initialize the tracker with this centroid position
			print('Initializing with daSiamRPN tracker')
			target_pos, target_sz = np.array([centroid[0], centroid[1]]), np.array([bbox[2], bbox[3]])
			if(self.is_color==False):
				image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
			self.state = SiamRPN_init(image, target_pos, target_sz, self.net)
			print('daSiamRPN tracker initialized')
		else:
			pass

	def _update_tracker(self, image, thresh_image):
		# Input: image or thresh_image
		# Output: new_bbox based on tracking
		new_bbox = None
		# tracking w/ openCV tracker
		if(self.tracker_type in self.OPENCV_OBJECT_TRACKERS.keys()):
			self.origin = np.array([0,0])
			# (x,y,w,h)\
			if(self.is_color==False):
				image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
			ok, new_bbox = self.tracker.update(image)
			return ok, new_bbox
		# tracking w/ the neural network-based tracker
		elif(self.tracker_type in self.NEURALNETTRACKERS.keys()):
			self.origin = np.array([0,0])
			if(self.is_color==False):
				image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
			self.state = SiamRPN_track(self.state, image)
			ok = True
			if(ok):
				# (x,y,w,h)
				new_bbox = cxy_wh_2_rect(self.state['target_pos'], self.state['target_sz'])
				new_bbox = [int(l) for l in new_bbox]
				# print('Updated daSiamRPN tracker')
			return ok, new_bbox
		# tracking w/ nearest neighbhour using the thresholded image 
		else:
			# If no tracker is specified, use basic thresholding and
			# nearest neighbhour tracking. i.e Look for objects in a search region 
			# near the last detected centroid

			# Get the latest thresholded image from the queue
			# thresh_image = 
			pts, thresh_image_cropped = image_processing.crop(thresh_image, self.centroid_image, self.searchArea)
			self.origin = pts[0]
			isCentroidFound, centroid, new_bbox = image_processing.find_centroid_basic_Rect(thresh_image_cropped)
			return isCentroidFound, new_bbox
		# @@@ Can add additional methods here for future tracker implementations

	# Signal from Tracking Widget connects to this Function
	def update_tracker_type(self, tracker_type):
		self.tracker_type = tracker_type
		print('set tracker set to {}'.format(self.tracker_type))
		# self.create_tracker()

	def update_init_method(self, method):
		self.init_method = method
		print("Tracking init method set to : {}".format(self.init_method))

	def centroid_from_bbox(self, bbox):
		# Coordinates of the object centroid are taken as the center of the bounding box
		assert(len(bbox) == 4)
		cx = int(bbox[0] + bbox[2]/2)
		cy = int(bbox[1] + bbox[3]/2)
		centroid = np.array([cx, cy])
		return centroid

	def rectpts_from_bbox(self, bbox):
		if(self.bbox is not None):
			pts = np.array([[bbox[0], bbox[1]],[bbox[0] + bbox[2], bbox[1] + bbox[3]]], dtype = 'int')
		else:
			pts = None
		return pts

	def update_searchArea(self, value):
		self.searchArea = value

	def set_roi_bbox(self, bbox):
		# Updates roi bbox from ImageDisplayWindow
		self.roi_bbox = bbox
		print('Rec bbox from ImageDisplay: {}'.format(self.roi_bbox))
