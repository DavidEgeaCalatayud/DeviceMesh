from dataclasses import dataclass
import ipaddress


@dataclass(frozen=True, slots=True)
class DiscoveryScope:
    cidr: str

    def network(self) -> ipaddress.IPv4Network:
        parsed = ipaddress.ip_network(self.cidr, strict=False)
        if not isinstance(parsed, ipaddress.IPv4Network):
            raise ValueError("V1 discovery supports IPv4 scopes only")
        if parsed.num_addresses > 4096:
            raise ValueError("discovery scope is too large; maximum 4096 addresses")
        return parsed


def candidate_addresses(scope: DiscoveryScope) -> list[str]:
    return [str(address) for address in scope.network().hosts()]
