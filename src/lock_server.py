import argparse
import rospy
from functools import partial
from paxos import PaxosRSM


def acquire_lock(lock_no, available):
    if available[lock_no]:
        available[lock_no] = 0
        success = True
    else:
        success = False
    return available, success


def return_lock(lock_no, avaialble):
    avaialble[lock_no] = 1
    return avaialble, True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--leader', action='store_true')
    args = parser.parse_args()

    num_locks = rospy.get_param('num_locks')
    init_state = [1 for _ in range(num_locks)]
    transitions = [partial(acquire_lock, i) for i in range(num_locks)] + \
        [partial(return_lock, i) for i in range(num_locks)]

    PaxosRSM(init_state, transitions, leader=args.leader)
    rospy.spin()
