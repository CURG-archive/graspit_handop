%run eigenhand_automation

interface = EGHandDBaseInterface()

interface.reset_database()


interface = EGHandDBaseInterface()

run_experiment(interface, 0, weighted_ATE_hand) 
