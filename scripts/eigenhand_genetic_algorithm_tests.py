import eigenhand_genetic_algorithm
import eigenhand_db_interface
import eigenhand_db_tools
import copy
import socket

def test_split_phalange(hand = None):
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    hands = interface.load_hands_for_generation(0)
    if(hand is None):
    	test_hand = hands[0]
    else:
    	test_hand = hand
    new_finger = eigenhand_genetic_algorithm.split_phalange(test_hand.fingers[0], 1)
    new_hand = copy.deepcopy(test_hand)
    new_hand.fingers[0] = new_finger
    return new_hand

def test_remove_phalange(hand = None):
	interface = eigenhand_db_interface.EGHandDBaseInterface()
	hands = interface.load_hands_for_generation(0)
	if hand is None:
		test_hand = hands[0]
	else:
		test_hand = hand
	new_finger = eigenhand_genetic_algorithm.remove_phalange(test_hand.fingers[0], 1)
	new_hand = copy.deepcopy(test_hand)
	new_hand.fingers[0] = new_finger
	return new_hand

def DB_test_split_phalange(hand = None):
	interface = eigenhand_db_interface.EGHandDBaseInterface()
	hands = interface.load_hands_for_generation(0)
	if hand is None:
		test_hand = hands[0]
	else:
		test_hand = hand
	new_finger = eigenhand_genetic_algorithm.split_phalange(test_hand.fingers[0], 1)
	new_hand = copy.deepcopy(test_hand)
	new_hand.fingers[0] = new_finger
	hand_list = [new_hand]
	hand_list = eigenhand_db_tools.insert_hand_list(hand_list, interface)

	s = socket.socket()
	s.connect(('localhost', 4765))
	s.send('loadEigenhand %i \n'%(hand_list[0].hand_id))
	output = s.recv(2048)
	if int(output.split(" ")[0]) == 0:
		raise ValueError("could not load hand")
	return new_hand

def DB_test_remove_phalange(hand = None):
	interface = eigenhand_db_interface.EGHandDBaseInterface()
	hands = interface.load_hands_for_generation(0)
	if hand is None:
		test_hand = hands[0]
	else:
		test_hand = hand
	new_finger = eigenhand_genetic_algorithm.remove_phalange(test_hand.fingers[0], 1)
	new_hand = copy.deepcopy(test_hand)
	new_hand.fingers[0] = new_finger
	hand_list = [new_hand]
	print("Old Hand ID: %d"%new_hand.hand_id)
	hand_list = eigenhand_db_tools.insert_hand_list(hand_list, interface)
	print("New Hand ID: %d"%hand_list[0].hand_id)
	s = socket.socket()
	s.connect(('localhost', 4765))
	s.send('loadEigenhand %i \n'%(hand_list[0].hand_id))
	output = s.recv(2048)
	if int(output.split(" ")[0]) == 0:
		raise ValueError("could not load hand")
	return new_hand