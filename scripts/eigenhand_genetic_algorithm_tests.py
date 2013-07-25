import eigenhand_genetic_algorithm
import eigenhand_db_interface
import copy

def test_split_phalange(finger_ind):
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    hands = interface.load_hands_for_generation(0)
    test_hand = hands[0]
    new_finger = eigenhand_genetic_algorithm.split_phalange(hand.fingers[0], 1)
    new_hand = copy.deep_copy(test_hand)
    new_hand.fingers[0] = new_finger
    return new_hand
