def rpi_action(self):
        """
        [Child Process]
        """
        while True:
            action: PiAction = self.rpi_action_queue.get()
            self.logger.debug(
                f"PiAction retrieved from queue: {action.cat} {action.value}"
            )

            if action.cat == "obstacles":
                for obs in action.value["obstacles"]:
                    self.obstacles[obs["id"]] = obs
                self.request_algo(action.value)
            elif action.cat == "snap":
                self.snap_and_rec(obstacle_id_with_signal=action.value)
            elif action.cat == "stitch":
                self.request_stitch()
            elif action.cat == "control" and action.value == "start":
                # Check API
                if not self.check_api():
                    self.logger.error("API is down! Start command aborted.")
                    self.android_queue.put(
                        AndroidMessage("error", "API is down, start command aborted.")
                    )

                # Commencing path following
                if not self.command_queue.empty():
                    self.logger.info("Gryo reset!")
                    self.stm_link.send("RS00")
                    # Main trigger to start movement #
                    self.unpause.set()
                    self.logger.info("Start command received, starting robot on path!")
                    self.android_queue.put(
                        AndroidMessage("info", "Starting robot on path!")
                    )
                    self.android_queue.put(AndroidMessage("status", "running"))
                else:
                    self.logger.warning(
                        "The command queue is empty, please set obstacles."
                    )
                    self.android_queue.put(
                        AndroidMessage(
                            "error", "Command queue is empty, did you set obstacles?"
                        )
                    )