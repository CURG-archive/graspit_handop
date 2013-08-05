
import eigenhand_db_interface
import experiment_manager
import task_models
import eigenhand_db_objects
import ate


def start_experiment(num_ga_iters = 2, num_atr_iters = 2, trials_per_task = 5): 
    interface = eigenhand_db_interface.EGHandDBaseInterface()
    interface.reset_database()
    task_prototype = eigenhand_db_objects.Task(task_type_id = 4, task_time = 60)
    em = experiment_manager.ExperimentManager(num_ga_iters, num_atr_iters, task_models.full_model_dict,
                                         task_prototype, trials_per_task, ate.weighted_ATE_hand, interface)
      
    em.run_experiment() 


