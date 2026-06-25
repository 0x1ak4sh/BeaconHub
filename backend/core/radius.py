"""
FreeRADIUS server manager for WPA2-Enterprise authentication.
Manages RADIUS user database and server lifecycle.
"""

import os
import signal
import subprocess
import logging
import time
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

CONFIG_DIR = "/opt/beaconhub/configs/radius"
USERS_FILE = "/opt/beaconhub/configs/radius/users"
CLIENTS_FILE = "/opt/beaconhub/configs/radius/clients.conf"
EAP_FILE = "/opt/beaconhub/configs/radius/eap.conf"
RADIUSD_CONF = "/opt/beaconhub/configs/radius/radiusd.conf"
RUN_DIR = "/opt/beaconhub/run"
CERTS_DIR = "/opt/beaconhub/configs/radius/certs"


class RadiusError(Exception):
    """Custom exception for RADIUS operations."""
    pass


class RadiusManager:
    """Manages FreeRADIUS server for WPA2-Enterprise authentication."""

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._users: Dict[str, dict] = {}  # username -> {password, groups}
        self._running = False
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(CERTS_DIR, exist_ok=True)
        os.makedirs(RUN_DIR, exist_ok=True)

    def _generate_test_certs(self):
        """Generate self-signed test certificates for EAP-TLS/PEAP."""
        ca_key = os.path.join(CERTS_DIR, "ca.key")
        ca_cert = os.path.join(CERTS_DIR, "ca.pem")
        server_key = os.path.join(CERTS_DIR, "server.key")
        server_cert = os.path.join(CERTS_DIR, "server.pem")
        dh_file = os.path.join(CERTS_DIR, "dh")

        # Only generate if not present
        if os.path.exists(ca_cert) and os.path.exists(server_cert):
            return

        try:
            # Generate CA key and certificate
            subprocess.run([
                "openssl", "genrsa", "-out", ca_key, "2048"
            ], capture_output=True, timeout=30)
            
            subprocess.run([
                "openssl", "req", "-new", "-x509", "-days", "365",
                "-key", ca_key, "-out", ca_cert,
                "-subj", "/CN=BeaconHub-CA/O=BeaconHub/C=US"
            ], capture_output=True, timeout=30)

            # Generate server key and certificate
            subprocess.run([
                "openssl", "genrsa", "-out", server_key, "2048"
            ], capture_output=True, timeout=30)

            # Generate CSR
            csr_file = os.path.join(CERTS_DIR, "server.csr")
            subprocess.run([
                "openssl", "req", "-new", "-key", server_key, "-out", csr_file,
                "-subj", "/CN=radius.beaconhub.local/O=BeaconHub/C=US"
            ], capture_output=True, timeout=30)

            # Sign with CA
            subprocess.run([
                "openssl", "x509", "-req", "-days", "365",
                "-in", csr_file, "-CA", ca_cert, "-CAkey", ca_key,
                "-CAcreateserial", "-out", server_cert
            ], capture_output=True, timeout=30)

            # Generate DH parameters (smaller for testing)
            subprocess.run([
                "openssl", "dhparam", "-out", dh_file, "1024"
            ], capture_output=True, timeout=60)

            # Set permissions
            os.chmod(server_key, 0o600)
            os.chmod(ca_key, 0o600)

            logger.info("Generated RADIUS test certificates")
        except Exception as e:
            logger.error(f"Failed to generate certificates: {e}")

    def _write_users_file(self):
        """Write FreeRADIUS users file."""
        lines = []
        for username, info in self._users.items():
            password = info.get("password", "")
            # FreeRADIUS users file format
            lines.append(f'{username}  Cleartext-Password := "{password}"')
            lines.append(f'    Reply-Message = "Hello, {username}"')
            lines.append("")
        
        # Add default test users if none configured
        if not self._users:
            lines.extend([
                'employee@corp.local  Cleartext-Password := "Welcome123"',
                '    Reply-Message = "Welcome Employee"',
                '',
                'admin@corp.local  Cleartext-Password := "Admin@123"',
                '    Reply-Message = "Welcome Admin"',
                '',
                'guest  Cleartext-Password := "guest123"',
                '    Reply-Message = "Welcome Guest"',
                '',
                'testuser  Cleartext-Password := "testpass"',
                '    Reply-Message = "Welcome Test User"',
                '',
            ])

        with open(USERS_FILE, "w") as f:
            f.write("\n".join(lines))
        
        logger.info(f"Wrote RADIUS users file with {len(self._users) or 4} users")

    def _write_clients_file(self):
        """Write FreeRADIUS clients configuration (which NAS can connect)."""
        content = """# RADIUS clients - who can connect to authenticate
client localhost {
    ipaddr = 127.0.0.1
    secret = testing123
    require_message_authenticator = no
    shortname = localhost
}

client localnet {
    ipaddr = 10.0.0.0/8
    secret = testing123
    require_message_authenticator = no
    shortname = localnet
}
"""
        with open(CLIENTS_FILE, "w") as f:
            f.write(content)

    def _write_eap_config(self):
        """Write EAP module configuration for PEAP/MSCHAPv2."""
        ca_cert = os.path.join(CERTS_DIR, "ca.pem")
        server_cert = os.path.join(CERTS_DIR, "server.pem")
        server_key = os.path.join(CERTS_DIR, "server.key")
        dh_file = os.path.join(CERTS_DIR, "dh")

        content = f"""# EAP Configuration for BeaconHub
eap {{
    default_eap_type = peap
    timer_expire = 60
    ignore_unknown_eap_types = no
    cisco_accounting_username_bug = no
    max_sessions = 4096

    tls-config tls-common {{
        private_key_password =
        private_key_file = {server_key}
        certificate_file = {server_cert}
        ca_file = {ca_cert}
        dh_file = {dh_file}
        ca_path = {CERTS_DIR}
        cipher_list = "DEFAULT"
        cipher_server_preference = no
        tls_min_version = "1.0"
        tls_max_version = "1.2"
        ecdh_curve = "prime256v1"
        check_crl = no
    }}

    tls {{
        tls = tls-common
    }}

    ttls {{
        tls = tls-common
        default_eap_type = mschapv2
        copy_request_to_tunnel = yes
        use_tunneled_reply = yes
        virtual_server = "inner-tunnel"
    }}

    peap {{
        tls = tls-common
        default_eap_type = mschapv2
        copy_request_to_tunnel = yes
        use_tunneled_reply = yes
        virtual_server = "inner-tunnel"
    }}

    mschapv2 {{
    }}
}}
"""
        with open(EAP_FILE, "w") as f:
            f.write(content)

    def _write_radiusd_config(self):
        """Write main radiusd.conf configuration."""
        content = f"""# FreeRADIUS configuration for BeaconHub
prefix = /usr
exec_prefix = /usr
sysconfdir = /etc
localstatedir = /var
sbindir = ${{exec_prefix}}/sbin
logdir = /opt/beaconhub/logs
raddbdir = {CONFIG_DIR}
radacctdir = ${{logdir}}/radacct
run_dir = /opt/beaconhub/run

name = radiusd
confdir = {CONFIG_DIR}
modconfdir = ${{confdir}}/mods-config
certdir = {CERTS_DIR}
cadir = {CERTS_DIR}

correct_escapes = true
max_request_time = 30
cleanup_delay = 5
max_requests = 16384
hostname_lookups = no

log {{
    destination = files
    colourise = yes
    file = /opt/beaconhub/logs/radius.log
    syslog_facility = daemon
    stripped_names = no
    auth = yes
    auth_badpass = yes
    auth_goodpass = yes
}}

security {{
    max_attributes = 200
    reject_delay = 1
    status_server = yes
}}

# Include other config files
$INCLUDE {CLIENTS_FILE}
$INCLUDE {EAP_FILE}

# Thread pool for handling requests
thread pool {{
    start_servers = 5
    max_servers = 32
    min_spare_servers = 3
    max_spare_servers = 10
    max_requests_per_server = 0
    auto_limit_acct = no
}}

# Modules configuration
modules {{
    $INCLUDE /etc/freeradius/3.0/mods-enabled/always
    $INCLUDE /etc/freeradius/3.0/mods-enabled/chap
    $INCLUDE /etc/freeradius/3.0/mods-enabled/mschap
    $INCLUDE /etc/freeradius/3.0/mods-enabled/pap
    $INCLUDE /etc/freeradius/3.0/mods-enabled/expr
    
    # Use our custom users file
    files {{
        usersfile = {USERS_FILE}
        acctusersfile = /dev/null
        preproxy_usersfile = /dev/null
    }}
}}

# Policy configuration
policy {{
    $INCLUDE /etc/freeradius/3.0/policy.d/
}}

# Server configuration
server default {{
    listen {{
        type = auth
        ipaddr = *
        port = 1812
        limit {{
            max_connections = 16
            lifetime = 0
            idle_timeout = 30
        }}
    }}

    listen {{
        type = acct
        ipaddr = *
        port = 1813
        limit {{
            max_connections = 16
            lifetime = 0
            idle_timeout = 30
        }}
    }}

    authorize {{
        filter_username
        preprocess
        chap
        mschap
        suffix
        eap {{
            ok = return
        }}
        files
        pap
    }}

    authenticate {{
        Auth-Type PAP {{
            pap
        }}
        Auth-Type CHAP {{
            chap
        }}
        Auth-Type MS-CHAP {{
            mschap
        }}
        eap
    }}

    preacct {{
        preprocess
        acct_unique
        suffix
    }}

    accounting {{
        detail
    }}

    post-auth {{
        update {{
            &reply: += &session-state:
        }}
        remove_reply_message_if_eap
    }}
}}

# Inner tunnel for PEAP/TTLS
server inner-tunnel {{
    listen {{
        type = auth
        ipaddr = 127.0.0.1
        port = 18120
    }}

    authorize {{
        filter_username
        chap
        mschap
        suffix
        update control {{
            &Proxy-To-Realm := LOCAL
        }}
        eap {{
            ok = return
        }}
        files
        pap
    }}

    authenticate {{
        Auth-Type PAP {{
            pap
        }}
        Auth-Type CHAP {{
            chap
        }}
        Auth-Type MS-CHAP {{
            mschap
        }}
        eap
    }}

    post-auth {{
    }}
}}
"""
        with open(RADIUSD_CONF, "w") as f:
            f.write(content)

    def add_user(self, username: str, password: str, groups: List[str] = None):
        """Add a user to the RADIUS database."""
        self._users[username] = {
            "password": password,
            "groups": groups or []
        }
        if self._running:
            self._write_users_file()
            self._reload()

    def remove_user(self, username: str):
        """Remove a user from the RADIUS database."""
        if username in self._users:
            del self._users[username]
            if self._running:
                self._write_users_file()
                self._reload()

    def list_users(self) -> List[dict]:
        """List all configured users."""
        return [
            {"username": u, "groups": info.get("groups", [])}
            for u, info in self._users.items()
        ]

    def start(self) -> bool:
        """Start the FreeRADIUS server."""
        if self._running and self._process and self._process.poll() is None:
            logger.info("RADIUS server already running")
            return True

        try:
            # Generate certificates if needed
            self._generate_test_certs()

            # Write configuration files
            self._write_users_file()
            self._write_clients_file()
            self._write_eap_config()
            self._write_radiusd_config()

            # Kill any existing freeradius
            subprocess.run(["pkill", "-f", "freeradius"], capture_output=True, timeout=5)
            time.sleep(0.5)

            log_file = os.path.join(RUN_DIR, "radius.log")
            log_fd = open(log_file, "w")

            # Start freeradius with our config
            # Try using system freeradius with -d to specify config dir
            self._process = subprocess.Popen(
                ["freeradius", "-X", "-d", CONFIG_DIR],
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()

            time.sleep(2)
            
            if self._process.poll() is not None:
                # Process died, try alternative approach using system config
                logger.warning("Custom RADIUS config failed, using system default with custom users")
                return self._start_with_system_config()

            self._running = True
            logger.info(f"Started FreeRADIUS server (PID: {self._process.pid})")
            return True

        except FileNotFoundError:
            logger.error("freeradius binary not found")
            return self._start_with_system_config()
        except Exception as e:
            logger.error(f"Failed to start RADIUS server: {e}")
            return False

    def _start_with_system_config(self) -> bool:
        """Start RADIUS with system default config, just update users file."""
        try:
            # Use system config but copy our users to /etc/freeradius
            system_users = "/etc/freeradius/3.0/users"
            if os.path.exists("/etc/freeradius/3.0"):
                # Backup and write our users
                self._write_users_file()
                subprocess.run(["cp", USERS_FILE, system_users], capture_output=True)
            
            # Kill any existing
            subprocess.run(["pkill", "-9", "freeradius"], capture_output=True, timeout=5)
            subprocess.run(["systemctl", "stop", "freeradius"], capture_output=True, timeout=10)
            time.sleep(1)

            # Start freeradius in background
            log_file = os.path.join(RUN_DIR, "radius.log")
            log_fd = open(log_file, "w")
            self._process = subprocess.Popen(
                ["freeradius", "-f"],  # -f = foreground but not debug
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
            log_fd.close()
            
            time.sleep(2)
            
            if self._process.poll() is None:
                self._running = True
                logger.info(f"Started FreeRADIUS with system config (PID: {self._process.pid})")
                return True
            
            logger.error("FreeRADIUS failed to start")
            return False
            
        except Exception as e:
            logger.error(f"Failed to start RADIUS with system config: {e}")
            return False

    def _reload(self):
        """Reload RADIUS configuration."""
        if self._process and self._process.poll() is None:
            try:
                os.kill(self._process.pid, signal.SIGHUP)
                logger.info("Reloaded RADIUS configuration")
            except Exception as e:
                logger.error(f"Failed to reload RADIUS: {e}")

    def stop(self):
        """Stop the FreeRADIUS server."""
        if self._process and self._process.poll() is None:
            try:
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.error(f"Error stopping RADIUS: {e}")

        # Also kill any stray freeradius processes
        subprocess.run(["pkill", "-f", "freeradius"], capture_output=True, timeout=5)
        
        self._running = False
        self._process = None
        logger.info("Stopped FreeRADIUS server")

    def is_running(self) -> bool:
        """Check if RADIUS server is running."""
        if self._process and self._process.poll() is None:
            return True
        # Also check via pgrep
        try:
            result = subprocess.run(
                ["pgrep", "-f", "freeradius"],
                capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def test_auth(self, username: str, password: str) -> bool:
        """Test authentication against the RADIUS server."""
        try:
            result = subprocess.run(
                ["radtest", username, password, "localhost", "0", "testing123"],
                capture_output=True, text=True, timeout=10
            )
            return "Access-Accept" in result.stdout
        except Exception as e:
            logger.error(f"RADIUS test failed: {e}")
            return False
