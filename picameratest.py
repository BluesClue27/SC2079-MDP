import picamera
import time
import os
import io

save_folder='images'

if not os.path.exists(save_folder):
    os.makedirs(save_folder)

camera = picamera.PiCamera()

try: 
    camera.resolution = (3280, 2464)
    #camera.resolution=(1024,768)
    camera.framerate = 30
    camera.contrast = 10
    camera.brightness = 50
    camera.sharpness = 100
    camera.saturation = 10
    camera.exposure_mode = 'auto'
    camera.iso = 100 # lower ISO for less noise, but require more light. Can use this setting for outdoor assessment
    camera.awb_mode = 'auto'  # Options: 'auto', 'sunlight', 'cloudy', 'shade', etc.
    # For manual AWB gains:
    camera.awb_gains = (1.5, 1.2)  # Adjust the red and blue gain


    # Flip the camera (set both to True if you want to flip both horizontally and vertically)
    camera.vflip = True  # Vertical flip
    camera.hflip = True  # Horizontal flip

    camera.start_preview()

    print("Press Enter to capture an image. Type 'q' and press Enter to stop.")

    while True:
        # Wait for user input
        command = input("Ready for capture. Press Enter to take a photo or type 'q' to quit: ")

        # If user types 'exit', stop the loop
        if command.lower() == 'q':
            break

        # Capture and save an image with a timestamp as the filename
        timestamp = time.strftime("%Y%m%d-%H%M%S")  # Get current time for the filename
        image_path = os.path.join(save_folder, f'image_{timestamp}.jpg')
        
        # Capture the image and save it to the folder
        camera.capture(image_path,quality=100)

        print(f"Image captured and saved as {image_path}")

     # Stop the camera preview
    camera.stop_preview()
finally:
    camera.close()


"""
---------------------------------------------------------
        ##############
        Code to capture image and store temporarily before sending to image-rec API endpoint via http
        ##############

        # notify android
        self.logger.info(f"Capturing image for obstacle id: {obstacle_id}")
        # have to change obstacle_id_with_signal to obstacle_id
        self.android_queue.put(AndroidMessage("info", f"Capturing image for obstacle id: {obstacle_id}"))

        #capture an image
        stream = io.BytesIO()
        with picamera.PiCamera() as camera:
            camera.start_preview()
            time.sleep(1)
            camera.capture(stream,format='jpeg')

        # notify android
        self.android_queue.put(AndroidMessage("info", "Image captured. Calling image-rec api..."))
        self.logger.info("Image captured. Calling image-rec api...")

        # call image-rec API endpoint
        self.logger.debug("Requesting from image API")
        url = f"http://{API_IP}:{API_PORT}/image"
        filename = f"{int(time.time())}_{obstacle_id}.jpg"
        image_data = stream.getvalue()
        response = requests.post(url, files={"file": (filename, image_data)})

        if response.status_code != 200:
            self.logger.error("Something went wrong when requesting path from image-rec API. Please try again.")
            self.android_queue.put(AndroidMessage(
                "error", "Something went wrong when requesting path from image-rec API. Please try again."))
            return
        
        results = json.loads(response.content)

        # release lock so that bot can continue moving
        self.movement_lock.release()
        try:
            self.retrylock.release()
        except:
            pass

        self.logger.info(f"results: {results}")
        self.logger.info(f"self.obstacles: {self.obstacles}")
        self.logger.info(
            f"Image recognition results: {results} ({SYMBOL_MAP.get(results['image_id'])})")

        if results['image_id'] == 'NA':
            self.failed_obstacles.append(
                self.obstacles[int(results['obstacle_id'])])
            self.logger.info(
                f"Added Obstacle {results['obstacle_id']} to failed obstacles.")
            self.logger.info(f"self.failed_obstacles: {self.failed_obstacles}")
        else:
            self.success_obstacles.append(
                self.obstacles[int(results['obstacle_id'])])
            self.logger.info(
                f"self.success_obstacles: {self.success_obstacles}")
        self.android_queue.put(AndroidMessage("image-rec", results))


-------------------------------------------------------
"""