## ROS Paxos
Multi-instance Paxos Replicated State machine with ROS as communication interface.

### Prerequisite
Ubuntu 20.04; ROS Noetic

### Simple setup using [ROS docker image](http://wiki.ros.org/docker/Tutorials/Docker):
1. Install [docker](https://docs.docker.com/get-docker);
2. Pull ROS-noetic docker image `docker pull ros:noetic`;
3. Clone this repo `git clone https://github.com/MakinoharaShouko/paxos_essential.git paxos_essential`;
4. Start docker image `docker run --rm --network=host -v paxos_essential:/home/paxos_ws/src -it ros:noetic`;
5. Install dependencies `apt-get update && apt-get install -y build-essential net-tools tmux`.

### How to run the code
1. `catkin_make`;
2. `source devel/setup.bash`;
3. Launch server `roslaunch paxos_essential lock_server.launch`;
4. Launch client `roslaunch paxos_essential lock_client.launch`;
5. Publish requests like `rostopic pub /terminal_input std_msgs/String "/lock_client_1 lock 0"`. Format for the message (last argument) is `[client_node_name] [lock | unlock] [lock_id]`. Ctrl-C afterwards as we don't need to latch the terminal input.

### Leader election
1. Kill default leader by `rosnode kill /lock_server_0`;
2. A new leader will be elected as shown in the command line logs.

### Node failure
1. Run `rosnode list` to see all the nodes;
2. Run `rosnode kill [node_name]` to kill any node. The RSM will work as long as the number of nodes alive is greater than `majority_size` in `launch/lock_server.launch`.

### Concurrent requests
1. Set `buffer_size` in `launch/lock_client.launch` to some integer greater than 1;
2. Publish multiple requests to the command line;
3. Once the requests for a single client exceeds `buffer_size`, all buffered requests will be sent concurrently to the server using python's `Threadpool`.

### Inter-machine communication
1. Find the IP addresses of the machines using `ifconfig`;
2. Set `ROS_MASTER_URI` and `ROS_IP` on all machines. `ROS_MASTER_URI=http://[master_ip]:11311` should be the same on all machines. `ROS_IP=[ip]` should be equal to the IP of each individual machine;
3. Launch servers and clients just like you are using a single machine.

### Recovery from network failure
1. Launch a set of servers and clients and send some requests;
2. Launch another set of servers e.g. `roslaunch paxos_essential lock_server_2.launch`. This emulates a set of servers previously disconnected from the network;
3. The new servers will catch up with the values of the existing servers as shown in the command line logs.
