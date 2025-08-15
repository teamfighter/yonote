"""Authentication related commands."""

from __future__ import annotations

from ..core import save_config, get_base_and_token, http_json
import json  # used in cmd_auth_info to pretty print


def cmd_auth_set(args):
    save_config(args.base_url, args.token)


def cmd_auth_info(_args):
    base, token = get_base_and_token()
    data = http_json("POST", f"{base}/auth.info", token, {})
    print(json.dumps(data, ensure_ascii=False, indent=2))
