import rospy


class Proposer():
    def __init__(self, uid, leader, prepare_pub, accept_pub):
        self.uid = uid
        self.leader = leader
        self.prepare_pub = prepare_pub
        self.accept_pub = accept_pub

        self.majority = rospy.get_param('majority')
        self.proposal_num = -1
        self.proposed_value = None
        self.proposal_id = (-1, '')
        self.promise_received = set()
        self.max_accepted_proposal_id = (-1, '')

    def observe_proposal(self, proposal_num, proposer_id):
        proposal_id = (proposal_num, proposer_id)
        if proposal_id >= (self.proposal_num, self.uid):
            self.proposal_num = proposal_num

    def prepare(self, instance, proposed_value=None):
        rospy.loginfo(f'{self.uid} proposed value {proposed_value} for instance {instance}')
        self.promise_received = set()
        self.proposal_num += 1
        self.proposal_id = (self.proposal_num, self.uid)
        self.proposed_value = proposed_value
        if self.leader:
            self.accept_pub.publish(
                instance=instance,
                proposal_num=self.proposal_num,
                proposer_id=self.uid,
                proposed_value=proposed_value
            )
        else:
            self.prepare_pub.publish(
                instance=instance,
                proposal_num=self.proposal_num,
                proposer_id=self.uid
            )

    def handle_promise(self, promise):
        self.observe_proposal(promise.proposal_num, promise.proposer_id)

        proposal_id = (promise.proposal_num, promise.proposer_id)
        # promise not for the current proposal
        if proposal_id != self.proposal_id:
            return
        # promise already received
        if promise.acceptor_id in self.promise_received:
            return

        self.promise_received.add(promise.acceptor_id)
        accepted_proposal_id = (promise.accepted_proposal_num, promise.accepted_proposer_id)
        if accepted_proposal_id > self.max_accepted_proposal_id:
            self.max_accepted_proposal_id = accepted_proposal_id
            self.proposed_value = promise.accepted_value

        if len(self.promise_received) == self.majority:
            self.leader = True
            self.accept_pub.publish(
                instance=promise.instance,
                proposal_num=promise.proposal_num,
                proposer_id=promise.proposer_id,
                proposed_value=self.proposed_value
            )
