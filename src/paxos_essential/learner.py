#!/usr/bin/env python
# license removed for brevity
import rospy
from paxos_essential.msg import Accepted

class Learner():
    def __init__(self):
        self.acceptors = {}
        self.accepted_pairs = {}
        self.acceptor_num = rospy.get_param('/acceptors')
        rospy.init_node('learner', anonymous=True)
        self.accepted_sub = \
            rospy.Subscriber('accepted', Accepted, self.accepted_callback)

    def accepted_callback(self, accepted):
        if accepted.acceptor_id in self.acceptors:
            prev = self.acceptors[accepted.acceptor_id]
            self.accepted_pairs[prev] -= 1
            if not self.accepted_pairs[prev]:
                self.accepted_pairs.pop(prev)
        pair = (accepted.proposer_id, accepted.accepted_number)
        self.acceptors[accepted.acceptor_id] = pair
        if pair not in self.accepted_pairs:
            self.accepted_pairs[pair] = 0
        self.accepted_pairs[pair] += 1
        if self.accepted_pairs[pair] > self.acceptor_num / 2:
            rospy.loginfo("Final value {} from {}"\
                .format(accepted.accepted_number, accepted.proposer_id))
            self.accepted_sub.unregister()

if __name__ == '__main__':
    try:
        learner = Learner()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass