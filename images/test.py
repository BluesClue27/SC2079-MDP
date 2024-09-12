import picamera
import time

camera=picamera.PiCamera()
camera.vflip=True
#camera.capture('example.jpg')
camera.start_recording('examplevid.h264')
time.sleep(5)
camera.stop_recording()
