from numpy import *
import itertools
import random as rnd
import copy as cp
import grasp_sorting_utils
import eigenhand_db_objects

hand_permutation_list = [[1,1,0,0],[1,0,1,0],[1,0,0,1],[0,1,1,0],[0,1,0,1],[0,0,1,1]]


def vector_diff(d):
    return diff(array(d))

def GA_pair(h1, h2):
    """
    @brief cross the two hands to produce a new hand that has half of the fingers of each hand

    @param h1 - a parent Hand
    @param h2 - a parent Hand

    Cross the two hands to produce a new hand that has half of the fingers of each hand. The palm is
    randomly selected to be one of the parent's palms. Not all hands can be crossed, because the finger
    offsets going around the palm may set on of the fingers further than the 0th finger, which is
    not allowed.

    @returns new child hand with no valid hand_id or an empty list if the produced hand is illegal.

    """
    parent_vector = [h1, h2]

    #Create a new hand
    new_hand = eigenhand_db_objects.Hand()

    #first create the selector vector for two fingers per hand
    parent_selector_vector = [0,0,1,1]

    #Create vector to store the resulting child vector
    child_angle_vector = []

    #Figure out the angle between each finger's base position around the palm
    p1_finger_angle_vector = vector_diff(h1.finger_base_positions)
    p2_finger_angle_vector = vector_diff(h2.finger_base_positions)

    #Store both lists of finger base angle offsets for extracting child finger offsets later.
    finger_angle_vectors = [p1_finger_angle_vector, p2_finger_angle_vector]


    #try to select a legal finger combination
    #A legal combination of fingers means that the offset of the final finger around the base cannot overlap or
    #go past the first finger.

    #randomize the list of all possible permuations
    permutation_samples = rnd.sample(hand_permutation_list,len(hand_permutation_list))



    finger_selector_vector = []
    #iterate over the randomized list and take the first legal examples
    for test_finger_selector_vector in permutation_samples:
        #initialize the vector that stores the position (The sum of all offsets up to this finger)
        #of fingers around the base of the palm. The 1st finger always
        #starts at angle 0
        child_angle_vector = [0]
        #for the next 3 fingers create the new finger calculate the position of the finger around the hand
        for i in range(1,4):
            child_angle_vector.append(finger_angle_vectors[test_finger_selector_vector[i]][i-1] + child_angle_vector[-1])
        #Test if the child is legal.
        if child_angle_vector[-1] < 330:
            #record the valid finger selector vector
            finger_selector_vector = test_finger_selector_vector
            break

    #If we did not manage to generate a valid hand, return []
    if not finger_selector_vector:
        return []

    #Set the new hands finger base positions and initialize other finger members.
    new_hand.finger_base_positions = child_angle_vector
    new_hand.finger_id_list = []
    new_hand.fingers = []

    #Record parent finger ids and Fingers.
    for i in range(4):
        new_hand.finger_id_list.append(parent_vector[finger_selector_vector[i]].finger_id_list[i])
        new_hand.fingers.append(parent_vector[finger_selector_vector[i]].fingers[i])


    #Decide which palm to use.
    palm_size_selector = rnd.randint(0,1)

    new_hand.palm_scale = parent_vector[palm_size_selector].palm_scale

    #Now set the 0th link of each finger to the palm scale. This is critical.
    for finger in new_hand.fingers:
        finger.link_length_list[0] = new_hand.palm_scale[0]

    #The hand generation is initialized as the max of of the previous generations + 1.
    new_hand.generation = [max(h1.generation[-1], h2.generation[-1]) + 1]
    new_hand.parents = [h1.hand_id, h2.hand_id]
    new_hand.hand_name = "Eigenhand"


    return new_hand


def mutate_item(mean, std, increment, min_, max_):
    """
    @brief Mutate an item to a new valid item by sampling a gaussian.

    @param mean - The mean of the Gaussian to sample. This should most likely be the current value of the item.
    @param std - The variance of the Gaussian to sample.
    @param min_ - The minimum legal value for the item.
    @param max_ - The maximum legal value for the item.

    @returns float with new legal value for the item.
    """
    return max(min(round(rnd.gauss(mean,std)/increment)*increment, max_),min_)

def remove_link(finger, shrink_index):
    """
    @brief remove a link from a finger, making the finger one link shorter

    @param finger - The Finger to shrink
    @param shrink_index - The index in the link_length_list of the link to remove

    @returns a Finger with the relevant link removed.
    """
    if shrink_index >= len(finger.link_length_list):
        return []
    del finger.link_length_list[shrink_index]
    del finger.joint_range_list[2*shrink_index: 2*shrink_index + 2]
    del finger.joint_default_speed_list[shrink_index]
    return finger


def remove_phalange(finger, phalange_num):
    """
    @brief remove entire phalange from the finger. Here we refer to both the twist and closing joints of the hand.

    @param finger - The finger to remove a phalange from.
    @param link_num - The number of the phalange to remove

    @returns a new Finger with 1 fewer phalanges than the input Finger.
    """
    new_finger = cp.deepcopy(finger)
    joint_index = phalange_num * 2
    new_finger = remove_link(new_finger, joint_index + 1)
    new_finger = remove_link(new_finger, joint_index)
    return new_finger


def split_phalange(finger, phalange_num):
    """
    @brief Split a link in a phalange to produce a new finger with one more phalange

    @param finger - the Finger to extend
    @param phalange_num - The number of the phalange to copy

    @returns A new Finger with one more phalange than the input finger.
    """
    new_finger = cp.deepcopy(finger)
    joint_index = 2 * phalange_num;
    #Insert a the new joint lengths
    new_finger.link_length_list.insert(joint_index + 2, new_finger.link_length_list[joint_index])
    new_finger.link_length_list.insert(joint_index + 3, new_finger.link_length_list[joint_index + 1])

    #Insert new default speeds
    new_finger.joint_default_speed_list.insert(joint_index + 2, new_finger.joint_default_speed_list[joint_index])
    new_finger.joint_default_speed_list.insert(joint_index + 3, new_finger.joint_default_speed_list[joint_index+1])

    #insert new joint ranges
    #These will be a copy of the old ranges
    joint_range_index = 4 * phalange_num
    joint_range_to_copy = new_finger.joint_range_list[joint_range_index:joint_range_index + 4]
    #Do the insertion
    new_finger.joint_range_list[joint_range_index + 4:1] = joint_range_to_copy


    return new_finger




def GA_mutate(hand, rel_stdev):
    """
    @brief Mutate this hand

    @param hand - the Hand to be mutated
    @param stdev - A gain to tune all of the standard deviations.

    @returns a new Hand that is mutated.
    """

    #Set up the all of the constants that will be used

    #The baseline probability that a finger will be mutated
    mutation_probability = .25
    reduction_probability = .1
    expansion_probability = .1
    #Each mutating item has a minimum and maximum length, a discretization increment, and a standard deviation.

    #Finger length modifier description
    finger_min_len = .25
    finger_max_len = 1
    finger_len_increment = .125
    finger_len_dev = rel_stdev*(finger_max_len - finger_min_len)

    #Palm diameter modifier description
    palm_min_diameter = .75
    palm_max_diameter = 1.25
    palm_diameter_increment = .25
    palm_diameter_dev = rel_stdev * (palm_max_diameter - palm_min_diameter)

    #finger base position modifier description
    finger_position_change_min = 30
    finger_position_change_max = 315
    finger_position_increment = 15
    finger_position_dev = 45 * rel_stdev

    #Finger phlange modifier description
    finger_max_phalanges = 4
    finger_min_phalanges = 2

    new_hand = cp.deepcopy(hand)


    """mutate palm"""
    palm_mutation_probability = .25
    palm_size_max = 1.25
    palm_size_min = .75
    palm_size_increment = .25
    palm_mutation_dev = (palm_size_max - palm_size_min) * rel_stdev
    palm_size = hand.palm_scale[0]

    if rnd.random() < palm_mutation_probability:
        palm_size = mutate_item(hand.palm_scale[0], palm_mutation_dev, palm_size_increment, palm_size_min, palm_size_max)

    #Small palms demand wider angles
    if palm_size < 1:
        finger_position_change_min += finger_position_increment

    """mutate finger position around the base"""
    finger_position_mutation_probability = .25

    d = new_hand.finger_base_positions
    finger_position_diffs = vector_diff(d)

    """Finger positions are actually stored as their absolute position,
     but they are modified as their relative position.
    """

    for i in range(len(finger_position_diffs)):
        if rnd.random() < finger_position_mutation_probability:
            continue
        finger_position_diffs[i] = mutate_item(finger_position_diffs[i], finger_position_dev,
                                               finger_position_increment, finger_position_change_min, finger_position_change_max)
    #Translate finger position increments to finger positions
    new_positions =  cumsum(finger_position_diffs)
    new_hand.finger_base_positions[1:] = new_positions

    #Test if the last finger position is too far - meaning it would overlap or go past the 0th finger.
    if new_hand.finger_base_positions[-1] > 330:
        return []

    #Test if the first finger position is too close to the 0th finger.
    if new_hand.finger_base_positions[1] < 20:
        return []



    """mutate finger length"""
    for i in range(len(hand.fingers)):
        new_hand.fingers[i] = cp.deepcopy(hand.fingers[i])

    new_hand.finger_id_list = []
    for f in new_hand.fingers:
        #Go over the finger lengths that represent actual links, not just twists.
        for i in [3,5,7,9]:
            #if this finger doesn't have that link, continue.
            if i > len(f.link_length_list) - 1:
                continue
            if rnd.random() < mutation_probability:
                f.link_length_list[i] = mutate_item(f.link_length_list[i], finger_len_dev,
                                                    finger_len_increment, finger_min_len, finger_max_len)

    """mutate finger phalanges"""

    for i in range(len(hand.fingers)):
        finger = hand.fingers[i]
        num_phalanges = (len(finger.link_length_list) - 2)/2 #Note - the "zeroth phlange" is the palm - should be untouched.
        if rnd.random() < reduction_probability and num_phalanges > finger_min_phalanges:
            phalange_index = rnd.randint(1, num_phalanges)
            new_finger = remove_phalange(finger, phalange_index)
            hand.fingers[i] = new_finger
        elif (rnd.random() < expansion_probability) and (num_phalanges < finger_max_phalanges):
            phalange_index = rnd.randint(1, num_phalanges)
            new_finger = split_phalange(finger, phalange_index)
            hand.fingers[i] = new_finger


    #Set up the new palm scale vector
    new_hand.palm_scale = [palm_size, 1, palm_size]
    #Modify the fingers so that they are at the right distance from the center of the palm
    for finger in new_hand.fingers:
        finger.link_length_list[0] = palm_size

    #Set the new hand generation and hand id
    new_hand.generation = [hand.generation[-1] + 1]
    new_hand.parents = [hand.hand_id]
    return new_hand


def GA_generation(grasp_list, hand_list, eval_functor, rel_stdev):
    """
    @brief Run the GA on an entire generation

    @param grasp_list - The list of grasps for all hands in this generation to be considered
    @param hand_list - The list of hands to mutate and cross
    @param eval_functor - The function to use to generate a score for each hand
    @param rel_stdev - The scaling factor for mutation to use.

    @returns A list of new hands derived from the old hands.
    """
    new_hand_list = list()

    #Organize the grasp list
    grasp_dict = grasp_sorting_utils.get_grasps_by_hand(grasp_list)

    #organize the hand list into a dictionary sorted by hand_id keys.
    hand_dict = dict()
    for h in hand_list:
        hand_dict[h.hand_id] = h

    energy_list = list()

    #Evaluate the score of each hand using the grasp_dict. Lower scores are better.
    for k in hand_dict:
        try:
            energy_list.append(eval_functor(grasp_dict[k],hand_dict[k]))
        except:
            #If the evaluation fails, assign an arbitrarily high score.
            print k
            energy_list.append(1e10)

    #Now we get the best hands by lowest energy

    sorted_key_indices = [hand_dict.keys()[i] for i in argsort(energy_list)]
    elite_list_len = 4
    elite_hand_list = [hand_dict[k] for k in sorted_key_indices[:elite_list_len]]

    #Get a list of all pairs of the elite hands
    #and then pair them all to generate a set of new hands
    hand_pair_list = itertools.combinations(elite_hand_list, 2)

    for pair in hand_pair_list:
        new_hand = GA_pair(pair[0], pair[1])
        if new_hand:
            new_hand_list.append(new_hand)


    #Now get 6 mutated hands - The parent hands are selected randomly from the elite hand list.
    mutation_number = 6
    rand_ind_list = [rnd.randrange(0,elite_list_len) for i in range(mutation_number)]

    for ind in rand_ind_list:
        new_hand = []
        #Not all generated hands will be legal, try ten times to generate a valid hand.
        #This is kind of arbitrary
        for i in range(10):
            new_hand = GA_mutate(elite_hand_list[ind], rel_stdev)
            if new_hand:
                break
        new_hand_list.append(new_hand)

    #Now, the elite hand list is passed on to the next generation unmodified.
    #update the hand generation to reflect this
    for hand in elite_hand_list:
        hand.generation.append(hand.generation[-1] + 1)
        new_hand_list.append(hand)

    return new_hand_list

