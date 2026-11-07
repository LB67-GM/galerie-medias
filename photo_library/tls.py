"""Certificat HTTPS local (CA maison + certificat serveur)."""

from __future__ import annotations

import socket
import ssl
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from typing import Iterable

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CA_DAYS = 3650
SERVER_DAYS = 825
RENEW_BEFORE = timedelta(days=30)
MDNS_HOST = "galerie.local"


@dataclass(frozen=True)
class TlsPaths:
    directory: Path
    ca_cert: Path
    ca_key: Path
    cert: Path
    key: Path


def tls_dir(cache: Path) -> Path:
    return Path(cache) / "tls"


def paths_for(cache: Path) -> TlsPaths:
    folder = tls_dir(cache)
    return TlsPaths(
        directory=folder,
        ca_cert=folder / "ca.pem",
        ca_key=folder / "ca-key.pem",
        cert=folder / "cert.pem",
        key=folder / "key.pem",
    )


def list_local_ipv4() -> list[str]:
    found: set[str] = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if _usable_ipv4(ip):
                found.add(ip)
    except OSError:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("1.1.1.1", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if _usable_ipv4(ip):
            found.add(ip)
    except OSError:
        pass
    try:
        out = subprocess.check_output(
            ["hostname", "-I"], text=True, timeout=2, stderr=subprocess.DEVNULL
        )
        for tok in out.split():
            if _usable_ipv4(tok):
                found.add(tok)
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(found)


def extra_names_from_env(extra: Iterable[str] | None = None) -> list[str]:
    names: list[str] = []
    import os

    raw = os.environ.get("GALERIE_TLS_HOSTS") or ""
    for part in raw.split(","):
        item = part.strip()
        if item:
            names.append(item)
    for item in extra or ():
        text = (item or "").strip()
        if text:
            names.append(text)
    return names


def fingerprint_sha256(cert_path: Path) -> str:
    data = cert_path.read_bytes()
    cert = x509.load_pem_x509_certificate(data)
    digest = cert.fingerprint(hashes.SHA256())
    return ":".join(f"{b:02X}" for b in digest)


def ssl_context(cache: Path) -> ssl.SSLContext:
    ca = paths_for(cache).ca_cert
    if not ca.is_file():
        raise FileNotFoundError(f"Certificat maison introuvable : {ca}")
    return ssl.create_default_context(cafile=str(ca))


def letsencrypt_dir(cache: Path) -> Path:
    return Path(cache) / "letsencrypt"


def letsencrypt_pair(cache: Path) -> tuple[Path, Path] | None:
    folder = letsencrypt_dir(cache)
    cert = folder / "fullchain.pem"
    key = folder / "privkey.pem"
    if cert.is_file() and key.is_file():
        return cert, key
    return None


def dns_names(cert_path: Path) -> list[str]:
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return []
    return list(san.value.get_values_for_type(x509.DNSName))


def client_context(cache: Path, port: int = 8765) -> tuple[str, ssl.SSLContext]:
    """URL et contexte pour parler au site. Certificat public s'il est installé."""
    pair = letsencrypt_pair(cache)
    if pair is not None:
        names = [name for name in dns_names(pair[0]) if name != "localhost"]
        host = names[0] if names else "localhost"
        return f"https://{host}:{port}", ssl.create_default_context()
    return f"https://127.0.0.1:{port}", ssl_context(cache)


def ensure_tls(
    cache: Path, *, extra_hosts: Iterable[str] | None = None
) -> TlsPaths:
    paths = paths_for(cache)
    paths.directory.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = _ensure_ca(paths)
    wanted = _wanted_sans(extra_hosts)
    if _server_ok(paths, wanted):
        return paths
    _write_server(paths, ca_key, ca_cert, wanted)
    return paths


def lan_urls(port: int, extra_hosts: Iterable[str] | None = None) -> list[str]:
    urls = [
        f"https://127.0.0.1:{port}",
        f"https://{MDNS_HOST}:{port}",
    ]
    for ip in list_local_ipv4():
        urls.append(f"https://{ip}:{port}")
    for name in extra_names_from_env(extra_hosts):
        if _looks_like_ip(name):
            urls.append(f"https://{name}:{port}")
        else:
            urls.append(f"https://{name}:{port}")
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _usable_ipv4(ip: str) -> bool:
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    if addr.version != 4:
        return False
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified:
        return False
    return bool(addr.is_private)


def _looks_like_ip(value: str) -> bool:
    try:
        ip_address(value)
        return True
    except ValueError:
        return False


def _write_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _write_cert(path: Path, cert: x509.Certificate) -> None:
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    try:
        path.chmod(0o644)
    except OSError:
        pass


def _load_key(path: Path) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def _load_cert(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def _ensure_ca(paths: TlsPaths) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    if paths.ca_cert.is_file() and paths.ca_key.is_file():
        key = _load_key(paths.ca_key)
        cert = _load_cert(paths.ca_cert)
        if cert.not_valid_after_utc > datetime.now(timezone.utc) + RENEW_BEFORE:
            return key, cert
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Galerie Médias"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Galerie Médias (maison)"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=CA_DAYS))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    _write_key(paths.ca_key, key)
    _write_cert(paths.ca_cert, cert)
    return key, cert


def _wanted_sans(extra_hosts: Iterable[str] | None) -> list[x509.GeneralName]:
    names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(MDNS_HOST),
        x509.IPAddress(ip_address("127.0.0.1")),
        x509.IPAddress(ip_address("::1")),
    ]
    host = socket.gethostname().strip()
    if host and host.lower() != "localhost":
        names.append(x509.DNSName(host))
        short = host.split(".")[0]
        if short and short != host:
            names.append(x509.DNSName(short))
    for ip in list_local_ipv4():
        names.append(x509.IPAddress(ip_address(ip)))
    for raw in extra_names_from_env(extra_hosts):
        if _looks_like_ip(raw):
            names.append(x509.IPAddress(ip_address(raw)))
        else:
            names.append(x509.DNSName(raw))
    seen: set[str] = set()
    unique: list[x509.GeneralName] = []
    for item in names:
        key = (
            item.value.exploded
            if isinstance(item, x509.IPAddress)
            else str(item.value).lower()
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _san_keys(cert: x509.Certificate) -> set[str]:
    try:
        ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    except x509.ExtensionNotFound:
        return set()
    keys: set[str] = set()
    for item in ext.value:
        if isinstance(item, x509.IPAddress):
            keys.add(item.value.exploded)
        else:
            keys.add(str(item.value).lower())
    return keys


def _wanted_keys(names: list[x509.GeneralName]) -> set[str]:
    keys: set[str] = set()
    for item in names:
        if isinstance(item, x509.IPAddress):
            keys.add(item.value.exploded)
        else:
            keys.add(str(item.value).lower())
    return keys


def _server_ok(paths: TlsPaths, wanted: list[x509.GeneralName]) -> bool:
    if not (paths.cert.is_file() and paths.key.is_file()):
        return False
    try:
        cert = _load_cert(paths.cert)
    except ValueError:
        return False
    if cert.not_valid_after_utc <= datetime.now(timezone.utc) + RENEW_BEFORE:
        return False
    have = _san_keys(cert)
    return _wanted_keys(wanted).issubset(have)


def _write_server(
    paths: TlsPaths,
    ca_key: rsa.RSAPrivateKey,
    ca_cert: x509.Certificate,
    wanted: list[x509.GeneralName],
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Galerie Médias"),
            x509.NameAttribute(NameOID.COMMON_NAME, "galerie.local"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=SERVER_DAYS))
        .add_extension(x509.SubjectAlternativeName(wanted), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )
    _write_key(paths.key, key)
    _write_cert(paths.cert, cert)
