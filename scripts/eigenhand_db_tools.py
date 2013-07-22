"""@brief Set of functions to add, analyze, and update objects in the database.
"""

import eigenhand_db_objects
import copy as cp


def insert_unique_finger(interface, finger, finger_list):
    """
    @brief insert a finger in to the database if it does not already exist in this list of fingers.
    otherwise, it simply sets the id of the given finger to the similar finger found in the database.

    FIXME - Maybe the test for uniqueness should be on the database server side instead of maintaining a unique list
    This is probably really inefficient as we do it so many times, but it doesn't occur during the blocking phase of the experiment
    For longer experiments where the number of fingers becomes astronomically large, this could really be a problem

    @param finger - the Finger to install
    @param finger_list - The list of fingers to test against. 
    """
    equivalent_finger = eigenhand_db_objects.find_equivalent_finger(finger_list, finger)
    if(equivalent_finger):
        return equivalent_finger
    
    finger = cp.deepcopy(finger)
    finger.finger_id = interface.add_finger_to_db(finger)[0]
    return finger

def insert_unique_hand(interface, hand, hand_list, finger_list):
    """
    @brief insert a Hand into the database if it does not already exist in this list of fingers.
    otherwise, it simply sets the id of the given Hand to the similar Hand found in the database.

    FIXME - Maybe the test for uniqueness should be on the database server side instead of maintaining a unique list
    This is probably really inefficient as we do it so many times, but it doesn't occur during the blocking phase of the experiment
    For longer experiments where the number of fingers becomes astronomically large, this could really be a problem

    @param hand - the Finger to install
    @param hand_list - The list of hands to test against.
    @param finger_list - The list of fingers to test against.     
    """
    hand.fingers = [insert_unique_finger(interface, finger, finger_list) for finger in hand.fingers]
    hand.finger_id_list = [finger.finger_id for finger in hand.fingers]
    equivalent_hand = eigenhand_db_objects.find_equivalent_hand(hand_list, hand)    
    if equivalent_hand:
        hand.hand_id = equivalent_hand.hand_id
        interface.update_hand_generation(hand)
        return equivalent_hand
    hand.hand_id = interface.add_hand_to_db(hand)[0]
    return hand


def insert_unique_hand_list(hand_list, interface):
    """
    @brief insert a list of hands, insuring that theya are only inserted if they are unique

    @param hand_list - The list of hands to insert
    @param interface - the interface to insert in to.
    """
    for hand in hand_list:
        db_hand_list = interface.get_data_obj_from_table(eigenhand_db_object.Hand, "hand")
        db_finger_list = interface.get_data_obj_from_table(eigenhand_db_object.Finger, "finger")
        insert_unique_hand(interface, hand, db_hand_list, db_finger_list)



def get_num_unlaunched_jobs(interface):
    """
    @brief Get the number of unlaunched jobs remaining

    @param interface - The database interface to query.

    @returns the number of unlaunched jobs
    """
    return len(interface.get_data_obj_by_index_list(eigenhand_db_object.Task, "task", "task_outcome_id", [1]))




def insert_new_finger(finger, finger_list, interface):
    """
    @brief Inserts a finger into the database if it does not exist in a list of known fingers

    @param finger - The Finger to add
    @param finger_list - The list of Fingers to compare the new finger to.
    @param interface - The database interface to use to add the finger. 
    """
    if(not eigenhand_db_objects.find_equivalent_finger(finger_list, finger)):
        return interface.add_finger_to_db(finger)
    return -1
        


def insert_new_hand(hand, hand_list, interface):
    """
    @brief Inserts a Hand into the database if it does not exist in a list of known Hands

    @param hand - The Finger to add
    @param hand_list - The list of Hands to compare the new hand to.
    @param interface - The database interface to use to add the hand. 
    """
    if(not eigenhand_db_objects.find_equivalent_hand(hand_list, hand)):
        return interface.add_hand_to_db(hand)
    return -1



def insert_entire_hand(hand, hand_list, finger_list, interface):
    """
    @brief Inserts a Hand into the database if it does not exist in a list of known Hands,
    also inserting any new fingers in the Hand.

    @param hand - The Hand to add
    @param hand_list - The list of Hands to compare the new hand to.
    @param finger_list - The list of fingers to compare the fingers of the new hand to. 
    @param interface - The database interface to use to add the hand. 
    """
    for f in hand.fingers:
        f_ind = insert_new_finger(f, finger_list, interface)
        if f_ind > 0:
            f.finger_ind = f_ind
    hand.finger_id_list = [finger.finger_id for finger in hand.fingers]
    return insert_new_hand(hand, hand_list, interface)
        

def insert_hand_list(new_hand_list, interface):
    """
    @brief Inserts a list of hands in to the database if they do not exist.

    @param new_hand_list - The list of hands to add
    @param interface - The interface to add it to. 
    """

    # Get all of the existing fingers and hands in the database
    finger_list = interface.get_data_obj_from_table(eigenhand_db_objects.Finger, 'finger')
    hand_list = interface.get_data_obj_from_table(eigenhand_db_objects.Hand, 'hand')

    # Go through each hand in the list and add it individually.
    for hand in new_hand_list:
        new_hand_id = insert_entire_hand(hand, hand_list, finger_list, interface)
        if new_hand_id > 0:
            hand.hand_id = new_hand_id
    return new_hand_list


def evaluate_generation_energy(interface, eval_function, generation):    
    """
    @brief Evaluates some function on all grasps for a generation

    @param interface - database interface to use
    @param eval_function - the function to evaluate the grasp list with
    @param generation - The generation to analyze

    @returns A dictionary of grasp energies by hand id.
    """
    grasps = interface.load_grasps_for_generation(generation)
    grasps_by_hand = get_grasps_by_hand(grasps)
    
    grasp_group_energy = dict()

    for grasp_group in grasps_by_hand:
        grasp_group_energy[grasp_group[0].hand_id] = eval_function(grasp_group)
    
    return grasp_group_energy



def update_group_energies(interface, grasp_group_energy):
    """
    @brief Add an energy list to the database

    @param interface - database interface to use
    @param grasp_group_energy - The a dictionary of energies to insert with the hand_id as the key.

    """
    for energy, hand_id in zip(grasp_group_energy.values(), grasp_group_energy.keys()):
        h = interface.get_hand(hand_id)
        h.energy_list.append(energy)
        interface.update_hand_energy(h)

    return
