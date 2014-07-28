import experiment_manager
import eigenhand_genetic_algorithm
import numpy
import grasp_sorting_utils
import pdb

def get_all_elite_hands(em, num_generations):
    elite_hands = {}
    for generation in range(num_generations):
        em.gm.generation = generation
        hands = em.interface.load_hands_for_generation(generation, False)
        for hand in hands:
            hand.energy_list = []
        grasp_list = em.gm.get_all_grasps()        
        elite_hands[generation] = eigenhand_genetic_algorithm.GA_get_elite_hands(grasp_list, hands, em.eval_functor)
        print [hand.hand_id for hand in elite_hands[generation][0]]
    return elite_hands


def analyze_all_hands(em, num_generations):
    all_hand_dict = {}
    for generation in range(num_generations):
        all_hand_dict[generation] = []
        em.gm.generation = generation
        grasp_list = em.gm.get_all_grasps()
        hand_list = em.interface.load_hands_for_grasps(grasp_list)

        grasp_dict = grasp_sorting_utils.get_grasps_by_hand(grasp_list)

        for hand in hand_list:
            hand.energy_list = []
        hand_dict = dict()
        for h in hand_list:
            hand_dict[h.hand_id] = h
            total_energy = 1e10
            try:
                total_energy = em.eval_functor(grasp_dict[h.hand_id], h)
            except Exception as e:
                print "analyze_all_hands::Exception %s"%(e);
                pdb.set_trace()
                
            h.energy_list.append(total_energy)
        
            all_hand_dict[generation].append(h)
    return all_hand_dict
        
            
        
    
def get_energy_per_hand(generation_desc_dict):
    elite_hand_dict = {}
    for gen_key in elite_hands:
        elite_gen_hand = generation_desc_dict[gen_key][0]
        hand_energies = generation_desc_dict[gen_key][1]
        hand_energies.sort()
        sorted_energies = hand_energies
        for ind, elite_hand in enumerate(elite_gen_hand):
            elite_hand.energy_list.append(sorted_energies[ind])
            if not elite_hand.hand_id in elite_hand_dict:
                elite_hand_dict[elite_hand.hand_id] = []
            elite_hand_dict[elite_hand.hand_id].append([gen_key, elite_hand])

    return elite_hand_dict

"""
def get_repeated_hand_energies(elite_hand_dict):
    repeated_hand_energy_dict = {}
    
    for hand_id in elite_hand_dict:
        if len(elite_hand_dict[hand_id]) <= 1:
            continue

        for gen_list in elite_hand_dict[hand_id]:
            if not hand_id in repeated_hand_energy_dict:
                repeated_hand_energy_dict[hand_id] = []
            descriptor = [gen_list[0], gen_list[1].energy_list[-1]]
            repeated_hand_energy_dict[hand_id].append(descriptor)
    return repeated_hand_energy_dict
"""

def get_repeated_hand_energies(all_hand_dict):
    hand_dict = {}
    repeated_hand_energy_dict = {}
    for generation in all_hand_dict:
        for hand in all_hand_dict[generation]:
            if not hand.hand_id in hand_dict:
                hand_dict[hand.hand_id] = []
            hand_dict[hand.hand_id].append([generation, hand])

    for hand_id in hand_dict:
        if len(hand_dict[hand_id]) <= 1:
            continue

        for gen_list in hand_dict[hand_id]:
            if not hand_id in repeated_hand_energy_dict:
                repeated_hand_energy_dict[hand_id] = []
            descriptor = [gen_list[0], gen_list[1].energy_list[-1]]
            repeated_hand_energy_dict[hand_id].append(descriptor)
    return repeated_hand_energy_dict


def get_hand_overlap(all_hand_dict, g1, g2):
    return list(set([h.hand_id for h in all_hand_dict[g1]]) & set([h.hand_id for h in all_hand_dict[g2]]))
