# Unity manual proxy-property profile

The method preserves the original DEX formatting: case-sensitive `http:` and
`https:` prefixes select their host and port properties; an absent or empty
host returns Java null. A nonempty port adds `:port`, and the raw
`http.nonProxyHosts` value adds a newline and the exclusion string for either
scheme. Unknown prefixes skip the property reader. Null URL raises Java NPE.

The Windows reader retrieves the current user's manual configuration using
`WinHttpGetIEProxyConfigForCurrentUser`. It records autodetect and PAC metadata
without resolving either. Absence of manual properties is not a claim about
the effective network route. No PAC file, WPAD discovery, network request,
authentication or setting change is performed.

The bounded manual parser supports a single proxy, explicit per-scheme entries,
numeric ports and bracketed IPv6. Supported bypass patterns are translated to
pipe-separated property values. Unqualified fallback lists, URLs, authentication
syntax and `<local>` fail explicitly instead of silently dropping semantics.
Injected property formatting preserves raw Unicode, NUL and unusual port text;
this is separate from parsing native manual configuration.

Tests use genuine NDK direct/V/A object calls and the qualified JNI host,
including callback revocation, exceptions, reference lifetime and State/Memory
ABI checks. The live Windows check compares raw manual/PAC/autodetect fields to
an independent read of the configuration API; it does not test a proxy route.

[Microsoft query documentation](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpgetieproxyconfigforcurrentuser)
and [configuration structure](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/ns-winhttp-winhttp_current_user_ie_proxy_config).
