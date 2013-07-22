import socket

def test_load_hand(hand_num):
    s = socket.socket()
    s.connect(('localhost',4765))
    s.send('loadEigenhand %i \n'%(hand_num))
    return

def test_scale_hand(chain_num, link_num, scale_vector):
    s = socket.socket()
    s.connect(('localhost',4765))
    s.send('scaleRobotLink %i %i %i %i %i\n'%(chain_num, link_num, scale_vector[0], scale_vector[1], scale_vector[2]))
    return


def test_energy(energy_type = 0):
    s = socket.socket()
    s.connect(('localhost',4765))
    s.send('getEnergy %i \n'%energy_type)


