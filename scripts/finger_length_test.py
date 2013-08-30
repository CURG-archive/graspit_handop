import eigenhand_genetic_algorithm
import eigenhand_db_interface
import eigenhand_db_tools
import copy
import socket
import pylab
import numpy

def test_finger_permutes():
	interface = eigenhand_db_interface.EGHandDBaseInterface()
	hands = interface.load_hands_for_generation(0)
	hand = hands[0]
	hand.fingers = [hand.fingers[0]]
	count = 1
	for x in [.25 + i * .125 for i in range(7)]:
		for y in [.25 + i * .125 for i in range(7)]:
			for z in [.25 + i * .125 for i in range(-1, 7)]: #value of .125 means skip the third and fourth phalange
				for w in [.25 + i * .125 for i in range(-1, 7)]: #value of .125 means skip the fourth phalange
					finger = hand.fingers[0]
					if(z == .125):
						finger.link_length_list = [finger.link_length_list[0], finger.link_length_list[1], 1.0, x, 1.0, y]
					elif (w == .125):
						finger.link_length_list = [finger.link_length_list[0], finger.link_length_list[1], 1.0, x, 1.0, y, 1.0, z]
					else:
						finger.link_length_list = [finger.link_length_list[0], finger.link_length_list[1], 1.0, x, 1.0, y, 1.0, z, 1.0, w]
					finger.joint_range_list = finger.joint_range_list[0:2] * len(finger.link_length_list)
					finger.joint_default_speed_list = [finger.joint_default_speed_list[0]] * len(finger.link_length_list)
					hand.fingers[0] = finger
					print ("%d: "%count)
					print hand.fingers[0].link_length_list
					count += 1
					delete_robot(interface)
	print "All tests run fine."

def load_up_robot(hand, interface):
	hand_list = [hand]
	eigenhand_db_tools.insert_unique_hand_list(hand_list, interface)
	print "New Hand ID: %d"%hand_list[0].hand_id
	s = socket.socket()
	s.connect(('localhost', 4765))
	s.send('loadEigenhand %i \n'%(hand_list[0].hand_id))
	output = s.recv(2048)
	if int(output.split(" ")[0]) == 0:
		raise ValueError("Could not load hand")

def delete_robot(interface):
	s = socket.socket()
	s.connect(('localhost', 4765))
	s.send('removeRobot ALL \n')

def quick_test(in_hand = None):
	interface = eigenhand_db_interface.EGHandDBaseInterface()
	if(in_hand == None):
		hands = interface.load_hands_for_generation(0)
		hand = hands[0]
	else:
		hand = in_hand
	finger = hand.fingers[0]
	finger.link_length_list = [finger.link_length_list[0], finger.link_length_list[1], 1.0, .25, 1.0, .25, 1.0, .25]
	finger.joint_range_list = finger.joint_range_list[0:2] * len(finger.link_length_list)
	finger.joint_default_speed_list = [finger.joint_default_speed_list[0]] * len(finger.link_length_list)
	hand.fingers[0] = finger
	load_up_robot(hand, interface)
	return interface

def qlist():
	interface = eigenhand_db_interface.EGHandDBaseInterface()
	return interface.load_hands_for_generation(0), interface
def qmutate(hands):
	for i in range(len(hands)):
		hand = eigenhand_genetic_algorithm.GA_mutate(hands[i], .1)
		hands[i] = hand
	return hands

def percentage_phalanges(generation, interface):
	hands = interface.load_hands_for_generation(generation)
	three = four = five = 0
	for hand in hands:
		for finger in hand.fingers:
			i = len(finger.link_length_list)
			if i is 6:
				three += 1
			elif i is 8:
				four += 1
			elif i is 10:
				five += 1
	total = three + four + five
	p = lambda x: int(float(x) / total * 100)

	print "Number of phalanges:"
	print "Three: %i, %i%%\nFour: %i, %i%%\nFive: %i, %i%%\n"%(three, p(three), four, p(four), five, p(five))

def pp_no_o(generation, interface):
	hands = interface.get_hands_by_grasp_gen(generation)
	t = f = v = 0
	for hand in hands:
		for finger in hand.fingers:
			i = len(finger.link_length_list)
			if i is 6:
				t += 1
			elif i is 8:
				f += 1
			elif i is 10:
				v += 1
	tot = t + f + v
	p = lambda x: int(float(x) / tot * 100)
	return (p(t), p(f), p(v))

def plot_output(i):
	score_list = []
	for gen in range(301):
		percent_1_links, percent_2_links, percent_3_links = pp_no_o(gen, i)
	  	score_list.append([gen, percent_1_links, percent_2_links, percent_3_links])
	  	print gen

	score_mat = numpy.array(score_list)

	#colors are represented by strings -- r,g,b,and k are the most common
	# standing for red green blue and black

	pylab.clf()
	pylab.plot(score_mat[:,0],score_mat[:,1],'r')
	pylab.plot(score_mat[:,0],score_mat[:,2],'b')
	pylab.plot(score_mat[:,0],score_mat[:,3],'g')
	pylab.show()