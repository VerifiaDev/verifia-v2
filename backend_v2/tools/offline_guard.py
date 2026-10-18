"""Fail before DNS or socket connections to external hosts in the offline suite."""
import ipaddress
import socket


def pytest_configure(config):
    def local(host):
        if host in {None, "localhost", b"localhost"}:
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise AssertionError("External network is disabled in offline tests")

    original_dns = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def dns(host, *args, **kwargs):
        local(host)
        return original_dns(host, *args, **kwargs)

    def connect(sock, address):
        if isinstance(address, tuple):
            local(address[0])
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if isinstance(address, tuple):
            local(address[0])
        return original_connect_ex(sock, address)

    socket.getaddrinfo = dns
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
