import rospy
import uuid
from multiprocessing.pool import ThreadPool
from paxos_essential.msg import ClientRequest, ClientResponse, TermInput
from time import sleep
from std_msgs import msg


class LockClient():
    def __init__(self):
        self.num_locks = rospy.get_param('num_locks')
        self.buffer_size = rospy.get_param('buffer_size')
        self.retry_interval = rospy.get_param('retry_interval')
        self.max_retries = rospy.get_param('max_retries')
        self.uid = str(uuid.uuid4())
        self.command_sub = rospy.Subscriber('terminal_input', msg.String, self.handle_term_input)
        self.request_pub = rospy.Publisher('client_request', ClientRequest, queue_size=10)
        self.response_sub = rospy.Subscriber('client_response', ClientResponse, self.handle_reponse)
        self.request_buffer = []
        self.responded_requests = set()
        self.n = 0
        rospy.loginfo(f'{rospy.get_name()} started, uid={self.uid}, buffer_size={self.buffer_size}')

    def handle_term_input(self, term_input):
        name, command, lock_no = term_input.data.split()
        lock_no = int(lock_no)
        if name == rospy.get_name():
            if lock_no > self.num_locks:
                rospy.logwarn(f'Lock {lock_no} exceeds number of locks {self.num_locks}')
                return
            if command == 'lock':
                value = lock_no + 1
            elif command == 'unlock':
                value = lock_no + self.num_locks + 1
            else:
                rospy.logwarn(f'Unknown command {command}. Use lock/unlock')
                return
            request = ClientRequest()
            request.client_id = self.uid
            request.request_id = self.n
            request.value = value
            self.request_buffer.append(request)
            self.n += 1
            if len(self.request_buffer) == self.buffer_size:
                with ThreadPool(self.buffer_size) as pool:
                    pool.map(self.send_request, self.request_buffer)
                self.request_buffer = []

    def handle_reponse(self, response):
        if response.client_id == self.uid:
            if response.request_id not in self.responded_requests:
                self.responded_requests.add(response.request_id)
                lock_no = response.value - 1
                if lock_no < self.num_locks:
                    if response.success:
                        rospy.loginfo(f'{rospy.get_name()} acquired lock {lock_no}')
                    else:
                        rospy.loginfo(f'{rospy.get_name()} failed to acquire lock {lock_no}')
                else:
                    lock_no -= self.num_locks
                    if response.success:
                        rospy.loginfo(f'{rospy.get_name()} released lock {lock_no}')
                    else:
                        rospy.loginfo(f'{rospy.get_name()} failed to release lock {lock_no}')

    def send_request(self, request):
        trial = 0
        while trial < self.max_retries and request.request_id not in self.responded_requests:
            self.request_pub.publish(request)
            trial += 1
            sleep(self.retry_interval)


if __name__ == '__main__':
    rospy.init_node('lock_client', anonymous=False)
    client = LockClient()
    rospy.spin()
    