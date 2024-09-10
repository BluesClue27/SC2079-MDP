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

            if msg_str is None:
                continue

            message: dict = json.loads(msg_str)

            ## Command: Set obstacles ##
            if message["cat"] == "obstacles":
                self.rpi_action_queue.put(PiAction(**message))
                self.logger.debug(f"Set obstacles PiAction added to queue: {message}")

            ## Command: Start Moving ##
            elif message["cat"] == "control":
                if message["value"] == "start":
                    self.rpi_action_queue.put(PiAction(**message))
                    self.logger.debug(
                        f"Control start PiAction added to queue: {message}"
                    )