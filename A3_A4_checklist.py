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

        self.movement_lock = self.manager.Lock()

        # self.rpi_action_queue = self.manager.Queue()
        # Messages that need to be processed by STM32, as well as snap commands
        self.command_queue = self.manager.Queue()
        # X,Y,D coordinates of the robot after execution of a command
        self.path_queue = self.manager.Queue()

        self.proc_recv_stm32 = None
        self.proc_command_follower = None
        # self.proc_rpi_action = None
        self.rs_flag = False
        # self.success_obstacles = self.manager.list()
        # self.failed_obstacles = self.manager.list()
        # self.obstacles = self.manager.dict()
        self.current_location = self.manager.dict()
        # self.failed_attempt = False

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
                if self.rs_flag == False:
                    self.rs_flag = True
                    self.logger.debug("ACK for RS00 from STM32 received.")
                    continue
                try:
                    self.movement_lock.release()
                    self.logger.debug(
                        "ACK from STM32 received, movement lock released.")

                    cur_location = self.path_queue.get_nowait()
                    print(f"Current Location from path queue {cur_location}")
                    self.current_location['x'] = cur_location['x']
                    self.current_location['y'] = cur_location['y']
                    self.current_location['d'] = cur_location['d']
                    self.logger.info(
                        f"self.current_location = {self.current_location}")
                  
                except Exception:
                    self.logger.warning("Tried to release a released lock!")
            else:
                self.logger.warning(
                    f"Ignored unknown message from STM: {message}")

    def command_follower(self) -> None:
        """
        [Child Process] 
        """
        while True:
            command: str = self.command_queue.get()
            self.movement_lock.acquire()
            # STM32 Commands - Send straight to STM32
            stm32_prefixes = ("FS", "BS", "FW", "BW", "FL", "FR", "BL",
                              "BR", "TL", "TR", "A", "C", "DT", "STOP", "ZZ", "RS")
            if command.startswith(stm32_prefixes):
                self.stm_link.send(command)
                self.logger.debug(f"Sending to STM32: {command}")

    def manual_command_loop(self):
        """
        Allows manual command input into STM32
        """
        print("Enter manual commands for the STM32. Type 'exit' to stop.")
        while True:
            command = input("Command: ")
            if command.lower() == 'exit':
                self.stop()
                break
            self.command_queue.put(command)

    def print_current_location(self):
        """
        Helper function to print the current location of the robot
        """


if __name__ == "__main__":
    rpi = RaspberryPi()
    rpi.start()
