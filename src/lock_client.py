import rospy
import uuid
from msg import ClientRequest, ClientResponse


def handle_reponse(response):
    print('Successs', response.success)


if __name__ == '__main__':
    num_locks = rospy.get_param('num_locks')
    client_id = str(uuid.uuid4())
    request_pub = rospy.Publisher('client_request', ClientRequest, queue_size=10)
    response_sub = rospy.Subscriber('client_response', ClientResponse, handle_reponse)
    request = input()
    while request:
        command, lock_no = request.split()
        value = int(lock_no) if command == 'lock' else int(lock_no) + num_locks
        request_pub.publish(value)
        request = input()
