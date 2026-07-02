from de_funk.utils.env_loader import inject_credentials_into_config
from pathlib import Path
import json


# Load Alpha Vantage config
alpha_vantage_cfg = json.loads(Path("configs/alpha_vantage_endpoints.json").read_text())

# Inject credentials
alpha_vantage_cfg = inject_credentials_into_config(alpha_vantage_cfg, 'alpha_vantage')

print(alpha_vantage_cfg)