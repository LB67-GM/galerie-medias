"""Envoi DLNA / UPnP vers une télévision (LG, Samsung, etc.) sur le LAN."""

from __future__ import annotations

import hmac
import hashlib
import http.server
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from photo_library.tls import list_local_ipv4

SSDP_ADDR = ("239.255.255.250", 1900)
AV_TRANSPORT = "urn:schemas-upnp-org:device:MediaRenderer:1"
AV_SERVICE = "urn:schemas-upnp-org:service:AVTransport:1"
VARIANTS = frozenset({"preview", "play", "file", "cinema"})
TOKEN_TTL_S = 4 * 3600
SOAP_TIMEOUT_S = 8
SOAP_STOP_TIMEOUT_S = 2.5
SSDP_WAIT_S = 3.0
HTTP_UA = "GaleriePhotos/1.0 DLNADOC/1.50"
SAMSUNG_DMR_PORT = 9197
SAMSUNG_DMR_PATH = "/dmr"

_NS = {
    "upnp": "urn:schemas-upnp-org:device-1-0",
    "s": "urn:schemas-upnp-org:device-1-0",
}


def preferred_lan_ipv4() -> str | None:
    ips = list_local_ipv4()

    def rank(ip: str) -> tuple[int, str]:
        if ip.startswith("192.168."):
            return (0, ip)
        if ip.startswith("10.8."):
            return (2, ip)
        return (1, ip)

    ordered = sorted(ips, key=rank)
    return ordered[0] if ordered else None


def media_http_base(*, https: bool, gallery_port: int, cast_port: int) -> str:
    ip = preferred_lan_ipv4() or "127.0.0.1"
    port = int(cast_port if https else gallery_port)
    return f"http://{ip}:{port}"


def make_token(secret: bytes, media_id: int, variant: str, *, now: int | None = None) -> str:
    if variant not in VARIANTS:
        raise ValueError("variante inconnue")
    exp = int(now if now is not None else time.time()) + TOKEN_TTL_S
    payload = f"{int(media_id)}:{variant}:{exp}"
    sig = hmac.new(secret, payload.encode("ascii"), hashlib.sha256).hexdigest()[:24]
    return f"{int(media_id)}.{variant}.{exp}.{sig}"


def parse_token(secret: bytes, token: str, *, now: int | None = None) -> tuple[int, str]:
    parts = (token or "").split(".")
    if len(parts) != 4:
        raise ValueError("lien TV invalide")
    media_s, variant, exp_s, sig = parts
    if variant not in VARIANTS:
        raise ValueError("lien TV invalide")
    try:
        media_id = int(media_s)
        exp = int(exp_s)
    except ValueError as exc:
        raise ValueError("lien TV invalide") from exc
    payload = f"{media_id}:{variant}:{exp}"
    expect = hmac.new(secret, payload.encode("ascii"), hashlib.sha256).hexdigest()[:24]
    if not hmac.compare_digest(expect, sig):
        raise ValueError("lien TV invalide")
    if int(now if now is not None else time.time()) > exp:
        raise ValueError("lien TV expiré")
    return media_id, variant


def is_private_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if not host:
        return False
    if host.endswith(".local"):
        return True
    try:
        addr = ip_address(host)
    except ValueError:
        return False
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local)


def parse_ssdp_headers(blob: bytes) -> dict[str, str]:
    text = blob.decode("utf-8", errors="replace")
    headers: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        headers[key.strip().upper()] = val.strip()
    return headers


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _walk_devices(elem: ET.Element):
    if _local_tag(elem.tag).lower() == "device":
        yield elem
    for child in list(elem):
        yield from _walk_devices(child)


def parse_renderer_description(xml_text: str, location: str) -> dict[str, str] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    for device in _walk_devices(root):
        control = None
        for node in device.iter():
            if _local_tag(node.tag) != "service":
                continue
            stype = ""
            curl = ""
            for child in list(node):
                name = _local_tag(child.tag)
                if name == "serviceType":
                    stype = (child.text or "").strip()
                elif name == "controlURL":
                    curl = (child.text or "").strip()
            if AV_SERVICE in stype and curl:
                control = urljoin(location, curl)
                break
        if not control:
            continue
        name = "Télévision"
        maker = ""
        for child in list(device):
            tag = _local_tag(child.tag)
            if tag == "friendlyName" and (child.text or "").strip():
                name = (child.text or "").strip()
            elif tag == "manufacturer" and (child.text or "").strip():
                maker = (child.text or "").strip()
        if not is_private_http_url(control):
            continue
        return {
            "name": name,
            "maker": maker,
            "control_url": control,
            "location": location,
        }
    return None


def _ssdp_search(st: str, sock: socket.socket) -> None:
    payload = (
        "M-SEARCH * HTTP/1.1\r\n"
        f"HOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        f"ST: {st}\r\n"
        "\r\n"
    )
    sock.sendto(payload.encode("ascii"), SSDP_ADDR)


def _ssdp_socket() -> socket.socket:
    """Bind sur le réseau local (un tunnel 10.8 passe après), port 1900 si possible."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    except OSError:
        pass
    lan = preferred_lan_ipv4()
    if lan:
        try:
            sock.setsockopt(
                socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(lan)
            )
        except OSError:
            pass
    sock.settimeout(0.4)
    host = lan or ""
    for port in (1900, 0):
        try:
            sock.bind((host, port))
            return sock
        except OSError:
            continue
    sock.close()
    raise OSError("socket SSDP")


def _tcp_open(ip: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def lan_probe_ips() -> list[str]:
    ip = preferred_lan_ipv4()
    if not ip:
        return []
    parts = ip.split(".")
    if len(parts) != 4:
        return []
    prefix = ".".join(parts[:3])
    mine = parts[3]
    return [f"{prefix}.{i}" for i in range(1, 255) if str(i) != mine]


def discover_by_lan_probe(*, fetch_xml=None) -> list[dict[str, str]]:
    """Samsung (et similaires) : le Wi-Fi bloque souvent le multicast SSDP."""
    getter = fetch_xml or _http_get
    ips = lan_probe_ips()
    if not ips:
        return []
    open_ips: list[str] = []
    with ThreadPoolExecutor(max_workers=48) as pool:
        futs = {pool.submit(_tcp_open, ip, SAMSUNG_DMR_PORT): ip for ip in ips}
        for fut in as_completed(futs):
            ip = futs[fut]
            try:
                if fut.result():
                    open_ips.append(ip)
            except Exception:
                continue
    found: list[dict[str, str]] = []
    for ip in open_ips:
        loc = f"http://{ip}:{SAMSUNG_DMR_PORT}{SAMSUNG_DMR_PATH}"
        try:
            xml_text = getter(loc, timeout=3)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError):
            continue
        info = parse_renderer_description(xml_text, loc)
        if info:
            found.append(info)
    return found


def discover_renderers(
    timeout: float = SSDP_WAIT_S,
    *,
    fetch_xml=None,
) -> list[dict[str, str]]:
    """Cherche les télés DLNA (MediaRenderer) sur le LAN."""
    getter = fetch_xml or _http_get
    locations: dict[str, None] = {}
    try:
        sock = _ssdp_socket()
    except OSError:
        sock = None
    if sock is not None:
        try:
            for st in (AV_TRANSPORT, "ssdp:all", "upnp:rootdevice"):
                try:
                    _ssdp_search(st, sock)
                except OSError:
                    pass
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data, _addr = sock.recvfrom(8192)
                except TimeoutError:
                    continue
                except OSError:
                    break
                headers = parse_ssdp_headers(data)
                loc = headers.get("LOCATION") or headers.get("LOC")
                if loc:
                    locations[loc] = None
        finally:
            sock.close()

    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for loc in locations:
        if not is_private_http_url(loc):
            continue
        try:
            xml_text = getter(loc, timeout=4)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError):
            continue
        info = parse_renderer_description(xml_text, loc)
        if not info:
            continue
        key = info["control_url"]
        if key in seen:
            continue
        seen.add(key)
        found.append(info)
    for info in discover_by_lan_probe(fetch_xml=getter):
        key = info["control_url"]
        if key in seen:
            continue
        seen.add(key)
        found.append(info)
    found.sort(key=lambda item: item["name"].lower())
    return found


def _http_get(url: str, timeout: float = 4) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# Profil DLNA lu par les télés LG et Samsung : H.264 Main, 1280x720, AAC.
DLNA_VIDEO_FEATURES = (
    "DLNA.ORG_PN=AVC_MP4_MP_HD_720p_AAC;"
    "DLNA.ORG_OP=01;DLNA.ORG_CI=0;"
    "DLNA.ORG_FLAGS=01700000000000000000000000000000"
)


def didl_metadata(uri: str, title: str, mime: str, *, video: bool) -> str:
    klass = "object.item.videoItem" if video else "object.item.imageItem.photo"
    extra = DLNA_VIDEO_FEATURES if video and mime == "video/mp4" else "*"
    proto = f"http-get:*:{mime}:{extra}"
    didl = (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        '<item id="1" parentID="0" restricted="1">'
        f"<dc:title>{escape(title)}</dc:title>"
        f"<upnp:class>{klass}</upnp:class>"
        f'<res protocolInfo="{escape(proto)}">{escape(uri)}</res>'
        "</item></DIDL-Lite>"
    )
    return didl


def soap_envelope(action: str, body_xml: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        f"<s:Body><u:{action} xmlns:u=\"{AV_SERVICE}\">{body_xml}</u:{action}></s:Body>"
        "</s:Envelope>"
    ).encode("utf-8")


def soap_action(
    control_url: str,
    action: str,
    body_xml: str,
    *,
    opener=None,
    timeout: float | None = None,
) -> None:
    if not is_private_http_url(control_url):
        raise ValueError("adresse TV refusée")
    data = soap_envelope(action, body_xml)
    req = urllib.request.Request(
        control_url,
        data=data,
        method="POST",
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{AV_SERVICE}#{action}"',
            "User-Agent": HTTP_UA,
        },
    )
    call = opener or urllib.request.urlopen
    wait = SOAP_STOP_TIMEOUT_S if action == "Stop" and timeout is None else (
        SOAP_TIMEOUT_S if timeout is None else timeout
    )
    with call(req, timeout=wait) as resp:
        resp.read()


def set_and_play(
    control_url: str,
    uri: str,
    title: str,
    mime: str,
    *,
    video: bool = False,
    opener=None,
) -> None:
    meta = escape(didl_metadata(uri, title, mime, video=video))
    soap_action(
        control_url,
        "SetAVTransportURI",
        "<InstanceID>0</InstanceID>"
        f"<CurrentURI>{escape(uri)}</CurrentURI>"
        f"<CurrentURIMetaData>{meta}</CurrentURIMetaData>",
        opener=opener,
    )
    soap_action(
        control_url,
        "Play",
        "<InstanceID>0</InstanceID><Speed>1</Speed>",
        opener=opener,
    )


def resolve_cast_file(
    library: Path, cache: Path, secret: bytes, token: str
) -> tuple[Path, str]:
    """Fichier JPEG/MP4 que la télévision peut télécharger (jeton HMAC)."""
    from photo_library.db import connect
    from photo_library.locate import locate_library_file
    from photo_library.play import cached_play_path, cinema_tv_path
    from photo_library.thumbs import make_preview, preview_file

    media_id, variant = parse_token(secret, token)
    conn = connect(cache)
    try:
        if variant == "cinema":
            crow = conn.execute(
                "SELECT * FROM cinema_items WHERE id=? AND present=1", (media_id,)
            ).fetchone()
            if crow is None:
                raise FileNotFoundError("vidéo Cinéma introuvable")
            dest = cinema_tv_path(
                cache, media_id, int(crow["size"] or 0), int(crow["mtime_ns"] or 0)
            )
            if dest.is_file() and dest.stat().st_size > 512:
                return dest, "video/mp4"
            raise FileNotFoundError("vidéo Cinéma pas encore préparée pour la TV")
        row = conn.execute(
            "SELECT * FROM media WHERE id=? AND present=1", (media_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise FileNotFoundError("média introuvable")
    kind = str(row["kind"] or "photo")
    relpath = str(row["relpath"])
    src = locate_library_file(library, relpath)
    if variant == "play":
        dest = cached_play_path(
            cache, media_id, int(row["size"] or 0), int(row["mtime_ns"] or 0)
        )
        if dest.is_file() and dest.stat().st_size > 512:
            return dest, "video/mp4"
        raise FileNotFoundError("vidéo pas encore convertie")
    dest = preview_file(cache, media_id)
    if dest.is_file():
        return dest, "image/jpeg"
    if src is not None and src.is_file():
        try:
            make_preview(src, dest, kind)
            return dest, "image/jpeg"
        except Exception:
            pass
    if variant == "file" and src is not None and src.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        mime = "image/jpeg" if src.suffix.lower() != ".png" else "image/png"
        return src, mime
    raise FileNotFoundError("aperçu impossible")


def stop_renderer(control_url: str, *, opener=None) -> None:
    soap_action(
        control_url,
        "Stop",
        "<InstanceID>0</InstanceID>",
        opener=opener,
    )


class _CastFileHandler(http.server.BaseHTTPRequestHandler):
    library: Path
    cache: Path
    secret: bytes
    resolve = None  # jeton → (chemin, type MIME)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        return

    def do_HEAD(self) -> None:  # noqa: N802
        self._send(head_only=True)

    def do_GET(self) -> None:  # noqa: N802
        self._send(head_only=False)

    def _send(self, *, head_only: bool) -> None:
        parsed = urlparse(self.path)
        prefix = "/api/cast/file/"
        if not parsed.path.startswith(prefix):
            self.send_error(404)
            return
        token = parsed.path[len(prefix) :].strip("/")
        try:
            path, mime = self.resolve(token)
        except ValueError:
            self.send_error(403)
            return
        except FileNotFoundError:
            self.send_error(404)
            return
        size = path.stat().st_size
        start = 0
        end = size - 1
        status = 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes=") and size:
            spec = rng.split("=", 1)[1].split(",")[0].strip()
            a, _, b = spec.partition("-")
            try:
                if a:
                    start = int(a)
                if b:
                    end = int(b)
            except ValueError:
                start, end = 0, size - 1
            end = min(end, size - 1)
            if start > end or start < 0:
                self.send_error(416)
                return
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if mime == "video/mp4":
            mode = self.headers.get("transferMode.dlna.org") or "Streaming"
            if mode not in {"Streaming", "Interactive", "Background"}:
                mode = "Streaming"
            self.send_header("transferMode.dlna.org", mode)
            self.send_header("contentFeatures.dlna.org", DLNA_VIDEO_FEATURES)
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "private, max-age=120")
        self.end_headers()
        if head_only:
            return
        with path.open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining:
                chunk = fh.read(min(64 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def start_cast_http_server(
    *,
    host: str,
    port: int,
    resolve,
) -> threading.Thread:
    handler = type(
        "BoundCastHandler",
        (_CastFileHandler,),
        {"resolve": staticmethod(resolve)},
    )
    httpd = http.server.ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, name="cast-http", daemon=True)
    thread.start()
    return thread
