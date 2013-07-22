"""
@brief A set of functions performing actuation topology reduction. 
"""
from numpy import *
from grasp_sorting_utils import *
import copy as cp

def ATR_hand(grasp_list, hand):    
    """
    @brief Modify the joint ranges of the hand to reflect the actual usage of those joints to
    perform the grasps in the grasp list. Joint ranges may be expanded or decreased.

    @param grasp_list - A list of grasps for this hand
    @param hand - The Hand whose joints to shrink.
    """

    def flatten(it):
        """
        @brief Helper funtion to take an iterable that may contain iterables and make it a single layer

        i.e. flatten([[1],[2]]) = [1,2]

        @param it - Iterable to flatten

        @returns a flattened version of the iterable, with one layer of nested iterables expanded.
        """
        ret_list = []
        for i in it:
            ret_list.extend(i)
            
        return ret_list
    """For each finger, get range of the joint in degrees, because it's just easier for me to think that way
    """
    joint_extreme_list = flatten([f.joint_range_list for f in hand.fingers])
    
    joint_range_size_list = array([(joint_extreme_list[2*i + 1] - joint_extreme_list[2*i])/2 for i in range(len(joint_extreme_list)/2)])    
    
    joint_angle_mat = array([g.grasp_grasp_joints[1:] for g in grasp_list])*(180.0/pi)

    """
    Calculate the 'grasp utility' of each joint, which is a measure of how much of it's
    joint range is used in achieving the final pose of the grasp. We measure this as the standard
    deviation of the joint over the range of the joint
    """
    
    joint_mean = mean(joint_angle_mat,0)
    joint_stdev = std(joint_angle_mat,0)

    
    g_util = divide(joint_stdev,joint_range_size_list)

    """
    Now figure out which joints to demote or expand.    
    """

    #Set the threshold on the grasp utility function to use to chose to expand or reduce the joint
    #range.  These are currently ignored. 
    reduction_threshold = .25
    expansion_threshold = .75

    #Instead, we currently always demote the two worst and promote the two best joints. 
    #Find the two lowest and highest gutils.
    #demotion_indices = [i for i in range(len(g_util)) if g_util[i] <= reduction_threshold
    demotion_indices = argsort(g_util)[:2]
    expansion_indices = argsort(g_util)[-2:]#[[i for i in range(len(g_util)) if g_util[i] > expansion_threshold]])[-4:]

    # The joint range is modified discretely in steps of 15, with a maximum range of 45
    # The range is +/- the center joint, so a joint range of 45 actually carves out 90 degrees
    # and a minimum range of 0
    max_angle = 45    
    angle_step = 15

    new_joint_range_size_list = cp.deepcopy(joint_range_size_list)

    new_joint_range_size_list[demotion_indices] = [min(max_angle,floor(j/angle_step)*angle_step) for j in joint_range_size_list[demotion_indices]]
    
    new_joint_range_size_list[expansion_indices] = [min(max_angle, (floor(j/angle_step)+1) * angle_step) for j in joint_range_size_list[expansion_indices]]

    # Calculate the joint ranges for each finger    

    """
    The joint means were calculated for all joints in one giant vector.
    To get the joint mean of each finger, we will have to track the number of joints processed
    by the proceeding fingers so we know the offset in to the joint vector to start from
    """    
    j_offset = 0

    """
    Copy the hand old hand, then go through the fingers of the new hand and set the joint ranges
    to the newly calculated ones.  To do this we get the mean for each joint, and then add mean-range and mean+range
    to the joint range list of the finger. 
    """
    new_hand = cp.deepcopy(hand)
    for f in new_hand.fingers:
        for j in range(len(f.link_length_list)):
            f.joint_range_list[2*j] = joint_mean[j + j_offset] - new_joint_range_size_list[j + j_offset]
            f.joint_range_list[2*j + 1] = joint_mean[j + j_offset] + new_joint_range_size_list[j + j_offset]
        j_offset += len(f.link_length_list)
        
    #Set the parent of the new hand to the id of the old hand.
    new_hand.parents = [hand.hand_id]

    #Add the new generation to the list of hand generations
    new_hand.generation.append(hand.generation[-1] + 1)    
    return new_hand


def ATR_generation(grasp_list, hand_list):
    """
    @brief Run ATR on a list of hands

    @param grasp_list - The list of grasps to use for ATR
    @param hand_list - The list of hands to use.

    @returns a new set of hands, with reduced or expanded joint ranges. 
    """
    grasp_dict = get_grasps_by_hand(grasp_list)
    new_hand_list = list()
    for hand in hand_list:
        try:
            new_hand_list.append(ATR_hand(grasp_dict[hand.hand_id], hand))
        except:
            print "error on hand %s"%(hand.hand_id)
    return new_hand_list




def test_next_atr(gm):
    """
    @brief unit test for atr, using a generation manager

    @param gm - generation manager interfacing with a prebuilt generation
    """
    
    gm.load_hands()
    gm.generation += 1
    grasp_list = gm.get_all_grasps()
    new_hand_list = ATR_generation(grasp_list, gm.hands)
    for hand in new_hand_list:
                db_hand_list = interface.get_data_obj_from_table(Hand, "hand")
                db_finger_list = interface.get_data_obj_from_table(Finger, "finger")
                insert_unique_hand(interface, hand, db_hand_list, db_finger_list)
