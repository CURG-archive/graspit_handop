from eigenhand_db_interface import *



def test_insert_hand(e):
    h = Hand(4,"EIGENHAND_test", 1, [1,1,1,1], [1,1,1],[0,90,180,270], [], [-1,-1])
    return e.add_hand_to_db(h)



def test_insert_task(e):
    t = Task(3,1000, 18000,1,3,1,"fakeworld.xml")
    return e.add_task_to_db(t)



def test_insert_finger(e):
    f = Finger(1,[1,1,1],[-180,180,-180,180,-180,180],[1,1,1])
    return e.add_finger_to_db(f)



def test_insert_unique_hand(hand, interface):
    db_hand_list = interface.get_data_obj_from_table(Hand, "hand")
    db_finger_list = interface.get_data_obj_from_table(Finger, "finger")
    insert_unique_hand(interface, hand, db_hand_list, db_finger_list)
