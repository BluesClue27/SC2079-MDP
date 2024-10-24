#!/usr/bin/env python3
import json
import io
import picamera
import queue
import signal
import time
from multiprocessing import Process, Manager
from typing import Optional
import os
import requests
from communication.android import AndroidLink, AndroidMessage
from communication.stm32 import STMLink
from consts import SYMBOL_MAP
from logger import prepare_logger
from settings import API_IP, API_PORT


class PiAction:
    def __init__(self, cat, value):
        self._cat = cat
        self._value = value

    @property
    def cat(self):
        return self._cat

    @property
    def value(self):
        return self._value


class RaspberryPi:
    def __init__(self):
        # Initialize logger and communication objects with Android and STM
        self.logger = prepare_logger()
        self.android_link = AndroidLink()
        self.stm_link = STMLink()

        # For sharing information between child processes
        self.manager = Manager()

        # Set robot mode to be 1 (Path mode)
        self.robot_mode = self.manager.Value('i', 1)

        # Events
        self.android_dropped = self.manager.Event()  # Set when the android link drops
        # commands will be retrieved from commands queue when this event is set
        self.unpause = self.manager.Event()

        # Movement Lock
        self.movement_lock = self.manager.Lock()

        # Queues
        self.android_queue = self.manager.Queue() # Messages to send to Android
        self.rpi_action_queue = self.manager.Queue() # Messages that need to be processed by RPi
        self.command_queue = self.manager.Queue() # Messages that need to be processed by STM32, as well as snap commands

        # Define empty processes
        self.proc_recv_android = None
        self.proc_recv_stm32 = None
        self.proc_android_sender = None
        self.proc_command_follower = None
        self.proc_rpi_action = None

        self.ack_count = 0
        self.near_flag = self.manager.Lock()

    def start(self):
        """Starts the RPi orchestrator"""
        try:
            # Establish Bluetooth connection with Android
            self.android_link.connect()
            self.android_queue.put(AndroidMessage('info', 'You are connected to the RPi!'))

            # Establish connection with STM32
            self.stm_link.connect()

            # Check Image Recognition and Algorithm API status
            self.check_api()
            
            """
            Already commented out in original seniors' code
            """
            #self.small_direction = self.snap_and_rec("Small")
            #self.logger.info(f"PREINFER small direction is: {self.small_direction}")

            # Define child processes
            self.proc_recv_android = Process(target=self.recv_android)
            self.proc_recv_stm32 = Process(target=self.recv_stm)
            self.proc_android_sender = Process(target=self.android_sender)
            self.proc_command_follower = Process(target=self.command_follower)
            self.proc_rpi_action = Process(target=self.rpi_action)

            # Start child processes
            self.proc_recv_android.start()
            self.proc_recv_stm32.start()
            self.proc_android_sender.start()
            self.proc_command_follower.start()
            self.proc_rpi_action.start()

            self.logger.info("Child Processes started")

            ### Start up complete ###

            # Send success message to Android
            self.android_queue.put(AndroidMessage('info', 'Robot is ready!'))
            self.android_queue.put(AndroidMessage('mode', 'path' if self.robot_mode.value == 1 else 'manual'))
            
            # Handover control to the Reconnect Handler to watch over Android connection
            self.reconnect_android()

        except KeyboardInterrupt:
            self.stop()
        
        except Exception as e:
            self.logger.error(f"An error occurred in the start process: {str(e)}")
            self.stop()


    def stop(self):
        """Stops all processes on the RPi and disconnects gracefully with Android and STM32"""
        self.android_link.disconnect()
        self.stm_link.disconnect()
        self.logger.info("Program exited!")

    def reconnect_android(self):
        """Handles the reconnection to Android in the event of a lost connection."""
        self.logger.info("Reconnection handler is watching...")

        while True:
            # Wait for android connection to drop
            self.android_dropped.wait()

            self.logger.error("Android link is down!")

            # Kill child processes
            self.logger.debug("Killing android child processes")
            self.proc_android_sender.kill()
            self.proc_recv_android.kill()

            # Wait for the child processes to finish
            self.proc_android_sender.join()
            self.proc_recv_android.join()
            assert self.proc_android_sender.is_alive() is False
            assert self.proc_recv_android.is_alive() is False
            self.logger.debug("Android child processes killed")

            # Clean up old sockets
            self.android_link.disconnect()

            # Reconnect
            self.android_link.connect()

            # Recreate Android processes
            self.proc_recv_android = Process(target=self.recv_android)
            self.proc_android_sender = Process(target=self.android_sender)

            # Start previously killed processes
            self.proc_recv_android.start()
            self.proc_android_sender.start()

            self.logger.info("Android child processes restarted")
            self.android_queue.put(AndroidMessage("info", "You are reconnected!"))
            self.android_queue.put(AndroidMessage('mode', 'path' if self.robot_mode.value == 1 else 'manual'))

            self.android_dropped.clear()
                
    def recv_android(self) -> None:
        """
        [Child Process] Processes the messages received from Android
        """
       
        while True:
            msg_str: Optional[str] = None
            try:
                msg_str = self.android_link.recv()
            except OSError:
                self.android_dropped.set()
                self.logger.debug("Event set: Android connection dropped")

            # If an error occurred in recv()
            if msg_str is None:
                continue

            message: dict = json.loads(msg_str)

            ## Command: Start Moving ##
            if message['cat'] == "control":
                if message['value'] == "start":
        
                    if not self.check_api():
                        self.logger.error("API is down! Start command aborted.")

                    self.clear_queues()
                    self.command_queue.put("RS00") # ack_count = 1

                    self.logger.info("Start command received, starting robot on Week 9 task!")
                    self.android_queue.put(AndroidMessage('status', 'running'))
                    self.android_queue.put(AndroidMessage('info','Clearing first obstacle...'))
                    # Commencing path following | Main trigger to start movement #
                    self.unpause.set()                    

                    # elif self.small_direction == None or self.small_direction == 'None':
                    #     self.logger.info("Acquiring near_flag log")
                    #     self.near_flag.acquire()             
                    
    def recv_stm(self) -> None:
        """
        [Child Process] Receive acknowledgement messages from STM32, and release the movement lock
        """
        while True:

            message: str = self.stm_link.recv()
            # Acknowledgement from STM32
            if message.startswith("ACK"):

                self.ack_count += 1

                # Release movement lock
                try:
                    self.movement_lock.release()
                except Exception:
                    self.logger.warning("Tried to release a released lock!")

                self.logger.debug(f"ACK from STM32 received, ACK count now:{self.ack_count}")

                if self.ack_count == 1:
                    # Moves forward 40cm 
                    self.command_queue.put("FW40") # ack_count = 1            
                elif self.ack_count == 2:
                    # Ensures the robot is 40cm away from the obstacle by 
                    # either moving back or forward
                    self.command_queue.put("FW99") # ack_count = 2 
                # elif self.ack_count == 3:
                #     self.command_queue.put("FW99")
                elif self.ack_count == 3: # Robot has reached first obstacle
                    self.small_direction = self.snap_and_rec("Small")
                    self.logger.info(f"HERE small direction is {self.small_direction}")
                    if self.small_direction == "Left Arrow":
                        self.command_queue.put("SL00") # ack_count = 3   
                    elif self.small_direction == "Right Arrow":
                        self.command_queue.put("SR00") # ack_count = 3  
                    else:
                        self.command_queue.put("SL00") # ack_count = 3 
                        self.logger.debug("Failed first one, going left by default!")

                elif self.ack_count == 4:
                    self.logger.info("First obstacle cleared!")
                    self.logger.info("Moving towards second obstacle")

                    # Moves forward until 35cm away from obstacle    
                    self.command_queue.put("BW10") # ack_count = 5
                elif self.ack_count == 5:
                    self.command_queue.put("FW98") # ack_count = 6
                elif self.ack_count == 6:
                    self.android_queue.put(AndroidMessage('info','Clearing second obstacle...'))
                    self.large_direction = self.snap_and_rec("Large")
                    self.logger.info(f"HERE large direction is {self.large_direction}")
                    if self.large_direction == "Left Arrow":
                        self.command_queue.put("LL00") # ack_count = 7
                    elif self.large_direction == "Right Arrow":
                        self.command_queue.put("LR00") # ack_count = 7
                    else:
                        self.command_queue.put("LR00") # ack_count = 7
                        self.logger.debug("Failed second one, going left by default!")

                elif self.ack_count == 7:
                    self.logger.debug("Second obstacle cleared!")
                    self.android_queue.put(AndroidMessage("status", "finished"))
                    # Move forward until robot is inside carpark
                    # self.command_queue.put("FW40") 
                    self.command_queue.put("FW99") # ack_count = 8
                elif self.ack_count == 8:
                    self.command_queue.put("FW05") # ack_count = 9
                elif self.ack_count == 9:   
                    # kill robot when in carpark, stitch images together
                    self.command_queue.put("FIN") # ack_count = 10
                elif self.ack_count >=9:
                    self.command_queue.put("FIN")

                # except Exception:
                #     self.logger.warning("Tried to release a released lock!")
            else:
                self.logger.warning(
                    f"Ignored unknown message from STM: {message}")

    def android_sender(self) -> None:
        while True:
            try:
                message: AndroidMessage = self.android_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self.android_link.send(message)
            except OSError:
                self.android_dropped.set()
                self.logger.debug("Event set: Android dropped")

    def command_follower(self) -> None:
        while True:
            command: str = self.command_queue.get()
            self.unpause.wait()
            self.movement_lock.acquire()
            stm32_prefixes = ("FS", "BS", "FW", "BW", "FL", "FR", "BL",
                              "BR", "TL", "TR", "A", "C", "DT", "STOP", "ZZ", "RS",
                              "SR", "SL", "LL", "LR", "BK")
            if command.startswith(stm32_prefixes):
                self.stm_link.send(command)
            elif command == "FIN":
                self.unpause.clear()
                self.movement_lock.release()
                self.logger.info("Commands queue finished.")
                self.android_queue.put(AndroidMessage("info", "Commands queue finished."))
                self.android_queue.put(AndroidMessage("status", "finished"))
                self.rpi_action_queue.put(PiAction(cat="stitch", value=""))
            else:
                raise Exception(f"Unknown command: {command}")

    # have to modify this code to ensure concurrency issue
    def rpi_action(self):
        while True:
            action: PiAction = self.rpi_action_queue.get()
            self.logger.debug(f"PiAction retrieved from queue: {action.cat} {action.value}")
            if action.cat == "snap": self.snap_and_rec(obstacle_id=action.value)
            elif action.cat == "stitch": self.request_stitch()

    def snap_and_rec(self, obstacle_id: str) -> None:
    #def snap_and_rec(self, obstacle_id_with_signal: str) -> None:
        """
        RPi snaps an image and calls the API for image-rec.
        The response is then forwarded back to the android
        :param obstacle_id: the current obstacle ID
        """
        # obstacle_id, signal = obstacle_id_with_signal.split("_")
        self.logger.info(f"Capturing image for obstacle id: {obstacle_id}")
        signal = "C"
        self.android_queue.put(AndroidMessage("info", f"Capturing image for obstacle id: {obstacle_id}"))

        image_capture_count = 0
        start = time.time()
        with picamera.PiCamera() as camera:
            camera.start_preview()
            camera.vflip = True  # Vertical flip
            camera.hflip = True  # Horizontal flip
            # time.sleep(1)

            while True: 
                image_capture_count += 1
                print(f"Image Capture Count: {image_capture_count}")
                self.logger.debug("Requesting from image API")
                
                # Reset the stream before capturing a new image
                stream = io.BytesIO()

                # call image-rec API endpoint
                url = f"http://{API_IP}:{API_PORT}/image"
                camera.capture(stream,format='jpeg')
                image_data = stream.getvalue()
                filename = f"{int(time.time())}_{obstacle_id}_{signal}.jpg"

                # notify android
                self.android_queue.put(AndroidMessage("info", "Image captured. Calling image-rec api..."))
                self.logger.info("Image captured. Calling image-rec api...")
                response = requests.post(url, files={"file": (filename, image_data)})
                if response.status_code != 200:
                    self.logger.error("Something went wrong when requesting path from image-rec API. Please try again.")
                    self.android_queue.put(AndroidMessage(
                        "error", "Something went wrong when requesting path from image-rec API. Please try again."))
                    return
                
                results = json.loads(response.content)

                """
                Retrying image capturing again using different configurations
                """
                if results['image_id'] != 'NA' or results['image_id'] !='Bullseye' or image_capture_count > 2:
                    break
                elif image_capture_count <= 0: # 1st try
                    self.logger.info(f"Image recognition results: {results}")
                    self.logger.info("Recapturing with same shutter speed...")
                elif image_capture_count <= 1: # 2nd try
                    self.logger.info(f"Image recognition results: {results}")
                    self.logger.info("Recapturing with higher brightness...")
                    camera.brightness = 60
                    camera.contrast = 90
                elif image_capture_count == 2: # 3rd try
                    self.logger.info(f"Image recognition results: {results}")
                    self.logger.info("Recapturing with lower brightness...")
                    camera.brightness = 30
                    camera.contrast = 100
                    camera.framerate = 70

        time_taken = time.time() - start
        # Print total time taken to 1dp
        print(f"Total time taken: {round(time_taken,1)}")  

        ans = SYMBOL_MAP.get(results['image_id'])
        self.logger.info(f"Image recognition results: {results} ({ans})")
        return ans

    def request_stitch(self):
        url = f"http://{API_IP}:{API_PORT}/stitch"
        response = requests.get(url)
        if response.status_code != 200:
            self.logger.error("Something went wrong when requesting stitch from the API.")
            return
        self.logger.info("Images stitched!")

    def clear_queues(self):
        while not self.command_queue.empty():
            self.command_queue.get()

    def check_api(self) -> bool:
        url = f"http://{API_IP}:{API_PORT}/"
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                self.logger.info("API is up!")
                return True
        except ConnectionError:
            self.logger.warning("API Connection Error")
            return False
        except requests.Timeout:
            self.logger.warning("API Timeout")
            return False
        except Exception as e:
            self.logger.warning(f"API Exception: {e}")
            return False
        
    def movement(self,obstacle: str): 
        """
        Commands to move the robot
        """
        if obstacle == "SL00":
            self.command_queue.put("FL90")
            self.command_queue.put("FR90")
            self.command_queue.put("FR90")
            self.command_queue.put("FL90")
            # ack_count = 2 + 6 = 8 after these 6 commands
        elif obstacle == "SR00":
            self.command_queue.put("FR90")
            self.command_queue.put("FL90")
            self.command_queue.put("FL90")
            self.command_queue.put("FR90")
            # ack_count = 2 + 6 = 8 after these 6 commands
        elif obstacle == "LL00":
            self.command_queue.put("FL90")
            self.command_queue.put("FR90")
            self.command_queue.put("FR90")
            self.command_queue.put("FW40")
            self.command_queue.put("FR90")
            # ack_count = 9 + 7 = 16 after these 7 commands
        elif obstacle == "LR00":
            self.command_queue.put("FR90")
            self.command_queue.put("FL90")
            self.command_queue.put("FL90")
            self.command_queue.put("FW40")
            self.command_queue.put("FL90")
            # ack_count = 9 + 7 = 16 after these 7 commands
        elif obstacle == "FIN":
            self.command_queue.put("FWxx")
            self.command_queue.put("FR90")
            self.command_queue.put("FL90")
            self.command_queue.put("FWxx")
            self.command_queue.put("FIN")
            # ack_count = 16 + 4 = 21 after these 5 commands

if __name__ == "__main__":
    rpi = RaspberryPi()
    rpi.start()
