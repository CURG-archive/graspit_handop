import eigenhand_genetic_algorithm 
import eigenhand_db_interface

def test_mutate(hand_id):
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    hand = interface.load_hand(hand_id)
    
    hand2 = eigenhand_genetic_algorithm.GA_mutate(hand, .5)
    
    return hand2

def generate_starting_set(starting_hand):
    current_hand = starting_hand
    hand_list = []
    for i in range(17):
        hand = []
        while not hand:
            hand = eigenhand_genetic_algorithm.GA_mutate(current_hand,.5)
        current_hand = hand
        hand.generation = [0]
        hand_list.append(current_hand)
    return hand_list
        
def test_starting_set(hand_list):
    diffs = [vector_diff(hand.finger_base_positions) for hand in hand_list]
    return any([any(d < 30) for d in diffs])

def test_generate_starting_set(starting_hand):
    hand_list = generate_starting_set(starting_hand)
    return test_starting_set(hand_list)

def test_legal_mutate(hand_id, times  = 1000):
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    hand = interface.load_hand(hand_id)
    hand_list = []
    for i in range(1000):
        hand2 = eigenhand_genetic_algorithm.GA_mutate(hand, .5)
        if hand2:
            hand_list.append(hand2)
    print test_starting_set(hand_list)
    
