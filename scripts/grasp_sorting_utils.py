"""
@brief A set of utilities to sort grasps by various criterion
"""


def get_grasps_by_hand(grasp_list):
    """
    @brief - Sort the available grasps in to a dictionary by hand_id

    @param grasp_list - The list of grasps to sort

    @returns a dictionary of lists of grasps with the hand_ids of the grasps as keys. 
    """
    grasps_by_hand = dict()
    for g in grasp_list:
        try:
            grasps_by_hand[g.hand_id].append(g)
        except KeyError:
            grasps_by_hand[g.hand_id] = list([g])
    return grasps_by_hand



def get_grasps_by_scaled_model(grasp_list):
    """
    @brief - Sort the available grasps in to a dictionary by scaled_model_id

    @param grasp_list - The list of grasps to sort

    @returns a dictionary of lists of grasps with the scaled_model_ids of the grasps as keys. 
    """
    grasps_by_scaled_model = dict()
    for g in grasp_list:
        try:
            grasps_by_scaled_model[g.scaled_model_id].append(g)
        except KeyError:
            grasps_by_scaled_model[g.scaled_model_id] = list([g])
    return grasps_by_scaled_model



def get_top_grasps_by_hand(grasp_list, number_grasps_per_object):
    """
    @brief - Get a dictionary of grasps with hand_ids as keys with only the top grasps for each object
    for each hand

    @param grasp_list - The list of grasps to sort

    @param number_grasps_per_object - The number of grasps to select per object

    @returns a dictionary of lists of grasps with the hand_ids of the grasps as keys. 
    """
    top_grasp_dict = dict()

    def get_top_grasps_in_list(grasp_list, number):
        """
        @brief Simple sorting function
 
        @param grasp_list - The grasps to sort
        @param number - The index of the energy type to use in sorting

        @returns the sorted list of grasps.
        """
        return sorted(grasp_list, key = lambda grasp:grasp.grasp_energy)[:number]

    grasps_by_hand = get_grasps_by_hand(grasp_list)

    for hand_id in grasps_by_hand:
        grasp_hand_list = grasps_by_hand[hand_id]
        grasps_by_scaled_model = get_grasps_by_scaled_model(grasp_hand_list)
        top_grasp_dict[hand_id] = []
        for scaled_model in grasps_by_scaled_model:
            top_grasp_dict[hand_id].extend(get_top_grasps_in_list(grasps_by_scaled_model[scaled_model],
                                                                  number_grasps_per_object))
    return top_grasp_dict
