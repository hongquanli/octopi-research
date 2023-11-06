from datetime import datetime

def print_message(msg):
	print(datetime.now().strftime('%m/%d %H:%M:%S') + ' : '  + msg )

def timestamp():
	return datetime.now().strftime('%Y/%m/%d %H:%M:%S') + ' : '