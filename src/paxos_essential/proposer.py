#!/usr/bin/env python
# license removed for brevity
import rospy
import uuid
from paxos_essential.msg import Prepare, Promise, Accept

class Proposer:
    def __init__(self):
        self.proposer_id = str(uuid.uuid4())
        self.proposal_number = 0
        self.prepare_responses = 0
        self.window_start = None
        self.acceptors = rospy.get_param('/acceptors')
        rospy.init_node('proposer {}'.format(self.proposer_id), anonymous=True)
        self.prepare_pub = rospy.Publisher('prepare', Prepare, queue_size=10, latch=True)
        self.accept_pub = rospy.Publisher('accept', Accept, queue_size=10, latch=True)
        self.promise_sub = rospy.Subscriber('promise', Promise, self.promise_callback)

    def prepare(self):
        self.proposal_number += 1
        rospy.loginfo("{} Propose {}".format(self.proposer_id, self.proposal_number))
        prepare_message = Prepare()
        prepare_message.proposer_id = self.proposer_id
        prepare_message.proposal_number = self.proposal_number
        # while self.prepare_pub.get_num_connections() < self.acceptors:
        #     rospy.spin()
        self.prepare_pub.publish(prepare_message)
        self.window_start = rospy.get_time()
        self.prepare_responses = 0
    
    def promise_callback(self, promise):
        if promise.proposer_id == self.proposer_id and \
                promise.accepted_number == self.proposal_number:
            rospy.loginfo('Prepare {} from {} accepted by {}'
                .format(promise.accepted_number, promise.proposer_id, promise.acceptor_id))
            self.prepare_responses += 1
            if self.prepare_responses > self.acceptors / 2:
                accept_message = Accept()
                accept_message.proposer_id = self.proposer_id
                accept_message.proposal_number = self.proposal_number
                self.accept_pub.publish(accept_message)
            else:
                now = rospy.get_time()
                if now - self.window_start >= 10:
                    # Time out
                    # Send another prepare
                    self.prepare()


if __name__ == '__main__':
    try:
        proposer = Proposer()
        rate = rospy.Rate(10)
        proposer.prepare()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass