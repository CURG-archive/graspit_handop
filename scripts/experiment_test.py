import eigenhand_db_interface

def test_backup():
	interface = eigenhand_db_interface.EGHandDBaseInterface()

	interface.incremental_backup("/data/backups", ['fake_finger'])

def test_load():
	interface = eigenhand_db_interface.EGHandDBaseInterface()

	d = dict()
	d['fake_finger'] = "/data/backups"
	interface.incremental_restore(d)