import socket

_original_getaddrinfo = socket.getaddrinfo
_patched = False


def force_ipv4_for_shopify():
    global _patched
    if _patched:
        return

    def getaddrinfo_ipv4(host, *args, **kwargs):
        results = _original_getaddrinfo(host, *args, **kwargs)
        if isinstance(host, str) and host.endswith("myshopify.com"):
            ipv4 = [result for result in results if result[0] == socket.AF_INET]
            if ipv4:
                return ipv4
        return results

    socket.getaddrinfo = getaddrinfo_ipv4
    _patched = True
