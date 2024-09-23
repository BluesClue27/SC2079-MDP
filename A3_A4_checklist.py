#!/usr/bin/env python3
import json
import queue
import time
from multiprocessing import Process, Manager
from typing import Optional
import os
import requests
from communication.stm32 import STMLink
from logger import prepare_logger


class PiAction:
    """
    Class that represents an action that the RPi needs to take.    
    """     

    def __init__(self, cat, value):
        """
        :param cat: The category of the action. Can be 'info', 'mode', 'path', 'snap', 'obstacle', 'location', 'failed', 'success'
        :param value: The value of the action. Can be a string, a list of coordinates, or a list of obstacles.
        """
        self._cat = cat
        self._value = value

    @property
    def cat(self):
        return self._cat

    @property
    def value(self):
        return self._value


class RaspberryPi:
    """
    Class that represents the Raspberry Pi.
    """

    def __init__(self):
        """
        Initializes the Raspberry Pi.
        """
        self.logger = prepare_logger()
        self.stm_link = STMLink()

        self.manager = Manager()

        self.unpause = self.manager.Event()
        self.movement_lock = self.manager.Lock()

        # self.rpi_action_queue = self.manager.Queue()
        # Messages that need to be processed by STM32, as well as snap commands
        self.command_queue = self.manager.Queue()
        # X,Y,D coordinates of the robot after execution of a command
        self.path_queue = self.manager.Queue()

        self.proc_recv_stm32 = None
        self.proc_command_follower = None
        self.rs_flag = False

    def start(self):
        """Starts the RPi orchestrator"""
        try:
            ### Start up initialization ###
            self.stm_link.connect()
     
            # Define child processes
            self.proc_recv_stm32 = Process(target=self.recv_stm)
            self.proc_command_follower = Process(target=self.command_follower)
            # self.proc_rpi_action = Process(target=self.rpi_action)

            # Start child processes
            self.proc_recv_stm32.start()
            self.proc_command_follower.start()
            # self.proc_rpi_action.start()

            self.logger.info("Child Processes started")

            self.manual_command_loop()
            
            ### Start up complete ###
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stops all processes on the RPi and disconnects gracefully with STM32"""
        self.stm_link.disconnect()
        self.logger.info("Program exited!")

    def recv_stm(self) -> None:
        """
        [Child Process] Receive acknowledgement messages from STM32, and release the movement lock
        """
        while True:
            message: str = self.stm_link.recv()
            if message.startswith("ACK"):
                try:
                    self.movement_lock.release()
                    self.logger.debug(
                        "ACK from STM32 received, movement lock released.")
                    self.unpause.set()

                except Exception as e:
                    #self.logger.warning("Tried to release a released lock!")
                    self.logger.error(e)

            else:
                self.logger.warning(
                    f"Ignored unknown message from STM: {message}")
                

    def command_follower(self) -> None:
        """
        [Child Process] 
        """
        while True:
            # Retrieve next movement command
            command: str = self.command_queue.get()
            self.logger.debug("wait for movelock")
            # Acquire lock first (needed for both moving, and snapping pictures)
            self.movement_lock.acquire()
            # STM32 Commands - Send straight to STM32
            stm32_prefixes = ("FS", "BS", "FW", "BW", "FL", "FR", "BL",
                              "BR", "TL", "TR", "A", "C", "DT", "STOP", "ZZ", "RS")
            if command.startswith(stm32_prefixes):
                self.stm_link.send(command)
                self.logger.debug(f"Sending to STM32: {command}")

            # Wait for unpause event before continuing
            self.logger.debug("Waiting for unpause")
            self.unpause.wait()


    def manual_command_loop(self):
        """
        Allows manual command input into STM32
        """
        print("Enter manual commands for the STM32. Type 'exit' to stop.")
        while True:
            commands = input('Command: ')
            if commands.lower() == 'exit':
                print('stop')
                self.stop()
                break
            else:
                command_list = commands.split()
                for command in command_list:
                    if command == 'FIN':
                        self.logger.info("FIN command received. Ending run")
                        self.stop()
                        return
                    else:
                            self.command_queue.put(command)

if __name__ == "__main__":
    rpi = RaspberryPi()
    rpi.start()
