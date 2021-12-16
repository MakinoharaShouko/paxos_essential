## ROS Paxos
Multi-instance Paxos Replicated State machine with ROS as communication interface.

### Prerequisite
Ubuntu 20.04; ROS Noetic

### Simple setup using [ROS docker image](http://wiki.ros.org/docker/Tutorials/Docker):
1. Install [docker](https://docs.docker.com/get-docker)
2. Pull ROS-noetic docker image `docker pull ros:noetic`
3. Clone this repo `git clone https://github.com/MakinoharaShouko/paxos_essential.git paxos_essential`
4. Start docker image `docker run -v paxos_essential:/home/paxos_ws/src -it ros:noetic`
5. Install build essentials `apt-get update -y && apt-get install -y build-essential`

### How to run the code
1. `catkin_make`
2. `source devel/setup.bash`
3. Launch server `roslaunch paxos_essential lock_server.launch`
4. Launch client `roslaunch paxos_essential lock_client.launch`
5. Publish requests e.g. `rostopic pub rostopic pub /terminal_input std_msgs/String "/lock_client_1 lock 0"`. Syntax for the last argument is `[client_node_name] [lock | unlock] [lock_id]`. Ctrl-C afterwards as we don't need to latch the terminal input.

### Test leader election
1. Kill default leader by `rosnode kill /lock_server_0`
2. A new leader will be elected as shown in the command line

### Test concurrent requests
1. Set `buffer_size` in `launch/lock_client.launch` to some integer greater than 1
2. Publish multiple requests to the command line
3. Once the requests for a single client exceeds `buffer_size`, all buffered requests will be sent concurrently to the server using python's `Threadpool`.

### Test inter-machine communication

