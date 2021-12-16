import rospy


class Acceptor():
    def __init__(self, uid, promise_pub, accepted_pub, refuse_prepare_pub):
        self.uid = uid
        self.promise_pub = promise_pub
        self.accepted_pub = accepted_pub
        self.refuse_prepare_pub = refuse_prepare_pub

        self.promised_id = (-1, '')
        self.accepted_proposal_num = -1
        self.accepted_proposer_id = ''
        self.accepted_value = None

    def handle_prepare(self, prepare):
        proposal_id = (prepare.proposal_num, prepare.proposer_id)
        if proposal_id > self.promised_id:
            self.promised_id = proposal_id
            self.promise_pub.publish(
                instance=prepare.instance,
                proposal_num=prepare.proposal_num,
                proposer_id=prepare.proposer_id,
                acceptor_id=self.uid,
                accepted_proposal_num=self.accepted_proposal_num,
                accepted_proposer_id=self.accepted_proposer_id,
                accepted_value=self.accepted_value
            )
        else:
            promised_proposal_num, promised_proposer_id = self.promised_id
            self.refuse_prepare_pub.publish(
                instance=prepare.instance,
                proposal_num=promised_proposal_num,
                proposer_id=promised_proposer_id
            )

    def handle_accept(self, accept):
        proposal_id = (accept.proposal_num, accept.proposer_id)
        if proposal_id >= self.promised_id:
            rospy.loginfo(f'{self.uid} accepted proposal {accept.proposal_num} '
                          f'with value {accept.proposed_value} '
                          f'from {accept.proposer_id} at instance {accept.instance}')
            self.promised_id = proposal_id
            self.accepted_proposal_num, self.accepted_proposer_id = proposal_id
            self.accepted_value = accept.proposed_value
            self.accepted_pub.publish(
                instance=accept.instance,
                acceptor_id=self.uid,
                proposal_num=self.accepted_proposal_num,
                proposer_id=self.accepted_proposer_id,
                accepted_value=self.accepted_value
            )
