import cumulus_server.libs.cumulus_config as config

def test_load():
	config.load("test/cumulus.conf")
	assert len(config.CONFIG) == 16

def test_get():
	assert config.get("database.file.path") == "./test/cumulus.db"

def test_init():
	config.init(False)
	assert config.DATA_DIR == "./test/data"

def test_export():
	assert config.export() == {
		"output.folder": "output",
		"temp.folder": "temp",
		"data.max.age.in.days": "90",
		"controller.version": "0.5.0",
		"client.min.version": "0.5.0"
	}

def test_get_final_stdout_path():
	assert config.get_final_stdout_path(1) == "./test/logs/job_1.stdout"

def test_get_final_stderr_path():
	assert config.get_final_stderr_path(1) == "./test/logs/job_1.stderr"
