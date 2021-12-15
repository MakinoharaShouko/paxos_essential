#!/usr/bin/env python
# license removed for brevity
import rospy
import uuid
from paxos_essential.msg import Prepare, Promise, Accept, Accepted

class Acceptor:
    def __init__(self):
        self.acceptor_id = str(uuid.uuid4())
        self.accepted_number = None
        self.accepted_id = None
        self.proposers = rospy.get_param('/proposers')
        rospy.init_node('acceptor' + self.acceptor_id, anonymous=True)
        self.prepare_sub = rospy.Subscriber('prepare', Prepare, self.prepare_callback)
        self.accept_sub = rospy.Subscriber('accept', Accept, self.accept_callback)
        self.promise_pub = rospy.Publisher('promise', Promise, queue_size=10, latch=True)
        self.accepted_pub = rospy.Publisher('accepted', Accepted, queue_size=10, latch=True)

    def prepare_callback(self, prepare):
        if not self.accepted_number or self.accepted_number < prepare.proposal_number:
            self.accepted_number = prepare.proposal_number
            self.accepted_id = prepare.proposer_id
            promise = Promise()
            promise.accepted_number = self.accepted_number
            promise.acceptor_id = self.acceptor_id
            promise.proposer_id = self.accepted_id
            self.promise_pub.publish(promise)

    def accept_callback(self, accept):
        if not self.accepted_number or self.accepted_number <= accept.proposal_number:
            self.accepted_number = accept.proposal_number
            self.accepted_id = accept.proposer_id
            rospy.loginfo("{} from {} accepted by {}"
                .format(self.accepted_number,
                self.accepted_id,
                self.acceptor_id))
            accepted = Accepted()
            accepted.accepted_number = self.accepted_number
            accepted.acceptor_id = self.acceptor_id
            accepted.proposer_id = self.accepted_id
            self.accepted_pub.publish(accepted)


if __name__ == '__main__':
    try:
        acceptor = Acceptor()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass