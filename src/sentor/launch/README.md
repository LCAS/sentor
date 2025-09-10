# Sentor Launch Files

This directory contains launch files for the Sentor monitoring system.

## Available Launch Files

### `sentor_launch.py` (Python Launch File)
A Python-based launch file that provides more flexibility and programmatic control.

**Usage:**
```bash
# Launch with default configuration
ros2 launch sentor sentor_launch.py

# Launch with custom config file
ros2 launch sentor sentor_launch.py config_file:=/path/to/your/config.yaml

# Launch with different log level
ros2 launch sentor sentor_launch.py log_level:=debug

# Launch with both custom config and log level
ros2 launch sentor sentor_launch.py config_file:=/path/to/config.yaml log_level:=warn
```

## Launch Arguments

- `config_file`: Path to the YAML configuration file for sentor monitoring
  - Default: `$(find-pkg-share sentor)/config/test_monitor_config.yaml`
  - Type: string

- `log_level`: Log level for the sentor node
  - Default: `info`
  - Valid values: `debug`, `info`, `warn`, `error`, `fatal`
  - Type: string

## Configuration

The default configuration file is located at:
```
src/sentor/config/test_monitor_config.yaml
```

After installation, it will be available at:
```
install/sentor/share/sentor/config/test_monitor_config.yaml
```

