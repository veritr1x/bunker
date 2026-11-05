# Numeric address parsing

The Android import accepts AF_INET=2 and AF_INET6=10. Windows maps IPv6 to its
AF_INET6=23 and invokes the real `InetPtonA` numeric converter. Valid syntax
returns 1 and publishes exactly four or sixteen network-order bytes; invalid
syntax returns 0 without changing output or guest errno. Unsupported families
return -1/EAFNOSUPPORT=97 before reading strings or touching output.

Microsoft documents that InetPton does not require Windows Sockets startup for
numeric conversion. The component performs no socket creation, DNS query,
network request, WSAStartup, or network-setting change. Input must be a valid
readable C string and output must be valid writable storage. Checked output
publication is host defensive policy, not a safe-pointer extension of C.

The focused test compares the same NDK caller object in static Bionic and the
translated Windows fixture. Direct and function-pointer calls cover strict
IPv4 grammar and IPv6 groups/compression/dotted tails, complete output canaries,
status/errno, State1200 and Memory64. It separately checks assigned-output page
boundaries and the native environment at the installed callback boundary.

Primary API source: https://learn.microsoft.com/en-us/windows/win32/api/ws2tcpip/nf-ws2tcpip-inet_pton
