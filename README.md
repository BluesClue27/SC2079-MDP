<br />
<p align="center">
  <a href="/public/Group_21.jpg">
    <img src="/images/Group_21.jpg" alt="Logo" height=150 >
  </a>
  <h1 align="center">
    SC2079 Multidisciplinary Project - Raspberry Pi
  </h1>
</p>

# Overview

This repository contains the code for the Raspberry Pi component of the SC2079 Multidisciplinary Project. The Raspberry Pi is responsible for the following:

- Communicating with the Android app via Bluetooth
- Communicating with the Algorithm API via HTTP requests
- Communicating with the STM32 microcontroller via serial
- Capturing images and sending them to the algorithm API
  <img src="/images/RPi.png" alt= "Calibration GUI" width="700">

# Communication Protocls

## Android Communication Protocol

### General Format

Messages between the Android app and Raspberry Pi will be in the following format:

```json
{ "cat": "xxx", "value": "xxx" }
```

The `cat` (for category) field with the following possible values:

- `info`: general messages
- `error`: error messages, usually in response of an invalid action
- `location`: the current location of the robot (in Path mode)
- `image-rec`: image recognition results
- `status`: status updates of the robot (`running` or `finished`)
- `obstacle`: list of obstacles
- `control`: movement-related, like starting the run

### Info Messages

Possible info messages:

- `You are connected to the RPi!` => Upon Android successfully connecting to the RPi
- `Robot is ready!` => Once all the initial child processes are ready and running
- `You are reconnected!` => Upon Android successfully reconnecting to the RPi
- `Starting robot on path!` => Upon Android sending the `start` command to the RPi
- `Commands queue finished!` => Upon the RPi finishing executing all the commands in the queue
- `Capturing image for obstacle id: {obstacle_id}` => Upon the RPi capturing an image for a particular obstacle
- `Requesting path from algo...` => Upon the RPi requesting the path from the algorithm
- `Commands and path received Algo API. Robot is ready to move.` => Upon the RPi receiving the commands and path from the algorithm
- `Images stitched!` => Upon the RPi successfully stitching the images

### Error Messages

Possible error messages:

- `API is down, start command aborted.` => If the API is down, the robot will not start moving
- `Command queue is empty, did you set obstacles?` => If the command queue is empty, the robot will not start moving
- `Something went wrong when requesting stitch from the API.` => Upon the RPi failing to request the stitched image from the algorithm
- `Something went wrong when requesting path from Algo API.` => Upon the RPi failing to request the path from the algorithm

### Status Messages

Possible status messages:

- `running` => When the robot is running
- `finished` => When the robot has finished running

### Obstacle Format

The message sent from Android to Raspberry Pi will be in the following format for obstacles:

```json
{
  "cat": "obstacles",
  "value": {
    "obstacles": [{ "x": 5, "y": 10, "id": 1, "d": 2 }],
    "mode": "0"
  }
}
```

### Start Movement

Android will send the following message to Raspberry Pi to start the movement of the robot (assuming obstacles were set).

```json
{ "cat": "control", "value": "start" }
```

If there are no commands in the queue, the RPi will respond with an error:

```json
{ "cat": "error", "value": "Command queue is empty, did you set obstacles?" }
```

### Image Recognition

Raspberry Pi will send the following message to Android, so that Android can update the results of the image recognition:

```json
{ "cat": "image-rec", "value": { "image_id": "A", "obstacle_id": "1" } }
```

### Location Updates

Raspberry Pi will periodically notify Android with the updated location of the robot.

```json
{ "cat": "location", "value": { "x": 1, "y": 1, "d": 0 } }
```

where `x`, `y` is the location of the robot, and `d` is its direction.

## Movement Command Protocol

The following are the possible commands related to movement. The commands will come from either the algorithm or Raspberry Pi, to be execued or passed along by the Raspberry Pi to STM32. For example, commands like SNAP and FIN are for Raspberry Pi to execute, while commands like FWxx are for Raspberry Pi to pass along to STM32.

### Task 1 Commands

`RS00` - Gyro Reset - Reset the gyro before starting movement
`FWxx` - Forward - Robot moves forward by xx units
`FR00` - Forward Right - Robot moves forward right by 3x1 squares
`FL00` - Forward Left - Robot moves forward left by 3x1 squares
`BWxx` - Backward - Robot moves backward by xx units
`BR00` - Backward Right - Robot moves backward right by 3x1 squares
`BL00` - Backward Left - Robot moves backward left by 3x1 squares

### Task 2 Commands

`OB01` - Small Obstacle - Robot moves from starting position to obstacle and stops
`UL00` - Go Around Left for Small Obstacle - Robot moves around obstacle to the left
`UR00` - Go Around Right for Small Obstacle- Robot moves around obstacle to the right
`PL01` - Go Around Left for Large Obstacle - Robot moves around obstacle to the left
`PR01` - Go Around Right for Large Obstacle - Robot moves around obstacle to the right

### Misc Commands

`STOP` - Stop - Robot stops moving
`SNAP` - Snap - Robot takes a picture and sends it for inference
`FIN` - Finish - Robot stops moving and sends a message to the server to signal end of command queue

### Acknowledgement from STM32

`ACK` - Acknowledgement - Robot sends this message to acknowledge receipt and execution of a command

# Setup

1. Follow the guide provided on NTULearn first, to set up the Raspberry Pi properly. This includes turning it into a wireless access point, communicating with the STM32, and Android tablet. Make sure all connections with all the necessary components are working properly.

2. Run either `task1.py` or `task2.py` depending on which task you are doing.

# Disclaimer

I am not responsible for any errors, mishaps, or damages that may occur from using this code. Use at your own risk.

# Acknowledgements

I heavily referenced pyesonekyaw's code, but made some modifications. I only worked on the RPi components and the links to the repositories for the other components are listeed as follows:

- [pyesonekyaw](https://github.com/pyesonekyaw/CZ3004-SC2079-MDP-RaspberryPi)
- [Algorithm BE](https://github.com/timothychangke/MDP_AlgorithmBE)
- [Algorithm FE](https://github.com/timothychangke/MDP_AlgorithmFE)
- [Android](https://github.com/xaynezz/MDP_Android)
