import graspit_dispatcher

def kill_if_busy(min_idle_level = 10):
    """
    @brief kill graspit jobs if the machine is too busy
    """
    ld = graspit_dispatcher.LocalDispatcher()
    ld.get_idle_percent()
    if ld.idle_percent < min_idle_level:
        ld.kill_existing_graspit()
        exit(1)
    exit(0)


if __name__ == "__main__":
    kill_if_busy()
