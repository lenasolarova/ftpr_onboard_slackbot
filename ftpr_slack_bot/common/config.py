# Copyright (c) 2026 Red Hat Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import toml


# Default config file location
DEFAULT_CONFIG = os.path.expanduser("~/.config/ftpr_slack_bot.toml")

# Global config object
CONF = {}


def load_config(config_file=None):
    """Load configuration from TOML file."""
    global CONF

    config_path = config_file or DEFAULT_CONFIG

    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            CONF = toml.load(f)
    else:
        # Use environment variables as fallback
        CONF = {
            'default': {
                'DEVLAKE_URL': os.getenv('DEVLAKE_URL', ''),
                'SLACK_BOT_TOKEN': os.getenv('SLACK_BOT_TOKEN', ''),
                'SLACK_APP_TOKEN': os.getenv('SLACK_APP_TOKEN', ''),
            }
        }

    # Environment variables override config file
    if os.getenv('DEVLAKE_URL'):
        CONF['default']['DEVLAKE_URL'] = os.getenv('DEVLAKE_URL')
    if os.getenv('SLACK_BOT_TOKEN'):
        CONF['default']['SLACK_BOT_TOKEN'] = os.getenv('SLACK_BOT_TOKEN')
    if os.getenv('SLACK_APP_TOKEN'):
        CONF['default']['SLACK_APP_TOKEN'] = os.getenv('SLACK_APP_TOKEN')

    return CONF


def update_config(config_file):
    """Update existing config with additional config file."""
    global CONF

    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            new_conf = toml.load(f)
            # Merge configs (new config takes priority)
            for section, values in new_conf.items():
                if section in CONF:
                    CONF[section].update(values)
                else:
                    CONF[section] = values


# Load default config on import
load_config()
