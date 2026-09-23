import ipaddress
import platform
import re
import socket
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Event
from time import perf_counter


@dataclass(frozen=True, slots=True)
class DiscoveryScope:
    cidr: str

    def network(self) -> ipaddress.IPv4Network:
        parsed = ipaddress.ip_network(self.cidr, strict=False)
        if not isinstance(parsed, ipaddress.IPv4Network):
            raise TypeError("V1 discovery supports IPv4 scopes only")
        if parsed.num_addresses > 4096:
            raise ValueError("discovery scope is too large; maximum 4096 addresses")
        return parsed


@dataclass(frozen=True, slots=True)
class ObservedService:
    port: int
    transport: str = "tcp"
    name: str | None = None


@dataclass(frozen=True, slots=True)
class HostObservation:
    ip_address: str
    observed_at: datetime
    latency_ms: float
    hostname: str | None = None
    mac_address: str | None = None
    network_cidr: str | None = None
    services: tuple[ObservedService, ...] = ()
    scanned_tcp_ports: tuple[int, ...] = ()


_SERVICE_NAMES = {
    22: "ssh",
    53: "dns",
    80: "http",
    443: "https",
    445: "smb",
    1883: "mqtt",
    3389: "rdp",
    5432: "postgresql",
    6379: "redis",
    8080: "http-alt",
    8443: "https-alt",
}


def candidate_addresses(scope: DiscoveryScope) -> list[str]:
    return [str(address) for address in scope.network().hosts()]


def scan_scope(
    scope: DiscoveryScope,
    *,
    max_workers: int = 64,
    timeout_seconds: float = 1.0,
    service_timeout_seconds: float = 0.35,
    tcp_ports: tuple[int, ...] = (),
    cancellation: Event | None = None,
    probe: Callable[[str, float], HostObservation | None] | None = None,
    port_probe: Callable[[str, int, float], bool] | None = None,
) -> list[HostObservation]:
    if not 1 <= max_workers <= 128:
        raise ValueError("max_workers must be between 1 and 128")
    if not 0.1 <= timeout_seconds <= 10:
        raise ValueError("timeout_seconds must be between 0.1 and 10")
    if not 0.05 <= service_timeout_seconds <= 2:
        raise ValueError("service_timeout_seconds must be between 0.05 and 2")
    if len(tcp_ports) > 32 or any(port < 1 or port > 65535 for port in tcp_ports):
        raise ValueError("tcp_ports must contain at most 32 valid TCP ports")

    probe_host = probe or _probe_host
    network_cidr = str(scope.network())
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="devicemesh-discovery")
    futures = {}
    try:
        for address in candidate_addresses(scope):
            if cancellation is not None and cancellation.is_set():
                break
            futures[executor.submit(probe_host, address, timeout_seconds)] = address

        observations: list[HostObservation] = []
        for future in as_completed(futures):
            if cancellation is not None and cancellation.is_set():
                break
            observation = future.result()
            if observation is None:
                continue
            services = scan_tcp_services(
                observation.ip_address,
                tcp_ports,
                timeout_seconds=service_timeout_seconds,
                port_probe=port_probe,
            )
            observations.append(
                HostObservation(
                    ip_address=observation.ip_address,
                    observed_at=observation.observed_at,
                    latency_ms=observation.latency_ms,
                    hostname=observation.hostname,
                    mac_address=observation.mac_address,
                    network_cidr=network_cidr,
                    services=services,
                    scanned_tcp_ports=tcp_ports,
                )
            )
        return sorted(observations, key=lambda item: ipaddress.ip_address(item.ip_address))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def scan_tcp_services(
    address: str,
    ports: tuple[int, ...],
    *,
    timeout_seconds: float = 0.35,
    port_probe: Callable[[str, int, float], bool] | None = None,
) -> tuple[ObservedService, ...]:
    if len(ports) > 32 or any(port < 1 or port > 65535 for port in ports):
        raise ValueError("ports must contain at most 32 valid TCP ports")
    if not 0.05 <= timeout_seconds <= 2:
        raise ValueError("timeout_seconds must be between 0.05 and 2")

    probe = port_probe or _tcp_connect_open
    return tuple(
        ObservedService(port=port, name=_SERVICE_NAMES.get(port))
        for port in ports
        if probe(address, port, timeout_seconds)
    )


def _tcp_connect_open(address: str, port: int, timeout_seconds: float) -> bool:
    try:
        with socket.create_connection((address, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _probe_host(address: str, timeout_seconds: float) -> HostObservation | None:
    command = _ping_command(address, timeout_seconds)
    started = perf_counter()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 1,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None

    elapsed_ms = (perf_counter() - started) * 1000
    hostname = _reverse_dns(address)
    mac_address = _neighbor_mac(address)
    return HostObservation(
        ip_address=address,
        observed_at=datetime.now(UTC),
        latency_ms=elapsed_ms,
        hostname=hostname,
        mac_address=mac_address,
    )


def _ping_command(address: str, timeout_seconds: float) -> list[str]:
    if platform.system() == "Windows":
        return ["ping", "-n", "1", "-w", str(int(timeout_seconds * 1000)), address]
    return ["ping", "-c", "1", "-W", str(max(1, int(timeout_seconds))), address]


def _reverse_dns(address: str) -> str | None:
    try:
        return socket.gethostbyaddr(address)[0]
    except (OSError, socket.herror):
        return None


def _neighbor_mac(address: str) -> str | None:
    if platform.system() == "Windows":
        command = ["arp", "-a", address]
    else:
        command = ["ip", "neigh", "show", address]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", result.stdout)
    return match.group(0).upper().replace("-", ":") if match else None
