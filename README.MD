## ROS Paxos
Used ROS to handle multi-instance and communication

### Prerequisite
Ubuntu 20.04; ROS Noetic

### How to run the code
1. `mkdir /paxos_ws/src`
2. `cd /paxos_ws/src`
3. clone this repo
4. `cd ..`
5. `catkin build`
6. `source devel/setup.bash`
7. `roslaunch paxos_essential paxos.launch`