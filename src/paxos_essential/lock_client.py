import rospy
import uuid
from paxos_essential.msg import ClientRequest, ClientResponse


def handle_reponse(response):
    if response.client_id == client_id and response.instance not in past_instances:
        past_instances.add(response.instance)
        rospy.loginfo(f'Successs = {response.output}')


if __name__ == '__main__':
    rospy.init_node('lock_client')
    num_locks = rospy.get_param('num_locks')
    client_id = str(uuid.uuid4())
    request_pub = rospy.Publisher('client_request', ClientRequest, queue_size=10)
    response_sub = rospy.Subscriber('client_response', ClientResponse, handle_reponse)
    past_instances = set()
    request = input()
    while request:
        command, lock_no = request.split()
        if command == 'lock':
            value = int(lock_no) + 1
        elif command == 'unlock':
            value = int(lock_no) + num_locks + 1
        else:
            rospy.logwarn(f'Unknown command {command}. Usage: lock/unlock [lock_no]')
        request_pub.publish(client_id, value)
        request = input()
