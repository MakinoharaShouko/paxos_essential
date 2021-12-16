import os
import rospy
from threading import Lock


class Learner():
    def __init__(self, uid, accepted_pub, finalized_pub):
        self.uid = uid
        self.majority = rospy.get_param('majority')
        self.proposal_counts = {} # proposal_id -> [acceptor_ids, accepted_value]
        self.accepted_proposals = {} # acceptor_id -> proposal_id
        self.final_acceptors = set()
        self.final_value = None
        self.accepted_pub = accepted_pub
        self.finalized_pub = finalized_pub
        self.lock = Lock()

    @property
    def complete(self):
        return self.final_value is not None

    def handle_accepted(self, accepted):
        with self.lock:
            if self.final_value is not None:
                if accepted.accepted_value == self.final_value:
                    self.final_acceptors.add(accepted.acceptor_id)
                return

            proposal_id = (accepted.proposal_num, accepted.proposer_id)
            accepted_proposal_id = self.accepted_proposals.get(accepted.acceptor_id)
            if accepted_proposal_id is not None and accepted_proposal_id >= proposal_id:
                return

            self.accepted_proposals[accepted.acceptor_id] = proposal_id
            if accepted_proposal_id is not None:
                self.proposal_counts[accepted_proposal_id][0].remove(accepted.acceptor_id)
            if proposal_id not in self.proposal_counts:
                self.proposal_counts[proposal_id] = [set(), accepted.accepted_value]
            self.proposal_counts[proposal_id][0].add(accepted.acceptor_id)

            if len(self.proposal_counts[proposal_id][0]) == self.majority:
                rospy.loginfo(f'{self.uid} learned value {accepted.accepted_value} '
                            f'from {self.proposal_counts[proposal_id][0]} '
                            f'at instance {accepted.instance}')
                self.final_acceptors, self.final_value = self.proposal_counts[proposal_id]
                self.finalized_pub.publish(instance=accepted.instance, value=self.final_value)
