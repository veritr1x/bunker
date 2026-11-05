# Unity public TLS trust-anchor export on Windows

The original game's CA-export routine `707cc1a0..707cc4c0` calls these Java methods:

| Original call | Owner and signature |
| --- | --- |
| `707cc1fc` | `javax/net/ssl/TrustManagerFactory.getDefaultAlgorithm()Ljava/lang/String;` (static) |
| `707cc208` | `TrustManagerFactory.getInstance(Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;` (static) |
| `707cc230` | `TrustManagerFactory.init(Ljava/security/KeyStore;)V` |
| `707cc244` | `TrustManagerFactory.getTrustManagers()[Ljavax/net/ssl/TrustManager;` |
| `707cc338` | `javax/net/ssl/X509TrustManager.getAcceptedIssuers()[Ljava/security/cert/X509Certificate;` |
| `707cc39c` | `java/security/cert/Certificate.getEncoded()[B` |

The routine checks each manager with JNI `IsInstanceOf(X509TrustManager)`, gets each encoded certificate using JNI byte-array elements (slot184), passes DER to original native import `707ca2ac`/`708c7ab0`, releases the lease using slot192/JNI_ABORT, and continues into original native code `707ca440`. The `init` argument comes through a zero-initialized global wrapper. That is static initial-state evidence; the actual runtime argument was not logged. This closure does not call Java `checkServerTrusted`, nor pass a hostname or authType to Java. Unreferenced JCA signatures in string data do not justify implementing those methods.

The original socket1 run logged missing `TrustManagerFactory` at lines20415/20416 and then Curl51 `UNITYTLS_X509VERIFY_FLAG_NOT_TRUSTED` at20418. This establishes a missing CA-export dependency, not proof that every TLS failure will disappear. The pinned original ELF/disassembly/log evidence is `work/java-tls-trust-boundary2/acceptance.json`, SHA256 `166c3251a0d3b1b920e3bc5d77a69901baaa754395f8386c46dd8d02b43c21da`.

## Native export policy

`ReadWindowsRootCertificates` dynamically loads System32 `crypt32.dll` and reads the existing logical CURRENT_USER `ROOT` store. Windows current-user root stores inherit local-machine roots, including the physical siblings assembled by the store provider. It never opens Personal/MY or accesses key APIs. See [system store locations](https://learn.microsoft.com/en-us/windows/win32/seccrypto/system-store-locations) and [current-user inheritance](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/local-machine-and-current-user-certificate-stores).

The reader copies and deduplicates full public DER bytes, excluding:

- Certificates whose DER appears in the read-only CURRENT_USER or LOCAL_MACHINE `Disallowed` stores.
- Certificates whose effective EKU property/extension intersection excludes server authentication. An absent restriction permits all uses; an explicitly empty intersection permits none. The reader follows the documented `cUsageIdentifier`/`GetLastError` distinction and accepts serverAuth or anyExtendedKeyUsage. See [CertGetEnhancedKeyUsage](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-certgetenhancedkeyusage).
- Anchors whose real current-user CryptoAPI chain reports `CERT_TRUST_IS_EXPLICIT_DISTRUST`. The query requests serverAuth and uses flags `0x2104`: cached URL objects only, disabled third-party-root auto-update, and disabled AIA. It performs no revocation retrieval. API failure fails the query; API success does not mean successful certificate validation. Only the explicit-distrust status bit is used for this narrow anchor filter. See [CertGetCertificateChain](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-certgetcertificatechain) and [CERT_TRUST_STATUS](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/ns-wincrypt-cert_trust_status).

Enumeration consumes the previous certificate context; exceptional exits free the remaining context. Stores, native chain contexts and DLL references have scoped ownership. DER is copied before those resources expire. See [CertEnumCertificatesInStore](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-certenumcertificatesinstore).

This is a snapshot of locally available anchors. It does not download missing roots, alter trust/network settings, implement Windows/JSSE peer-chain verification, or bypass the original UnityTLS verifier. DER alone cannot carry all Windows CTL policies, future or downstream distrust dates, revocation state, enterprise restrictions or external EKU properties. Complete Windows policy equivalence is not claimed. Any later Java peer-chain-check request is outside this audited profile and requires a separate implementation.

The original native continuation copies its incoming name span to a NUL-terminated buffer at `707ca590..707ca5a0`, then passes that buffer in X4 to `708c8f5c`, alongside chain, trust-list, profile, verification-flags output and optional callback/userdata. This is consistent with the [Mbed TLS verify-with-profile signature](https://github.com/Mbed-TLS/mbedtls/blob/mbedtls-2.16.12/include/mbedtls/x509_crt.h), whose name argument controls certificate-name matching. That identification is an inference from the native ABI, not a recovered symbol or a logged runtime hostname. The adapter leaves that entire original native path intact. No successful peer-chain or hostname-verification result has yet been observed for this adapter.

## Java objects and lifetime

Construct `JavaTlsTrust` once after the Java catalog and before original JNI startup; retain it until original workers stop. It defines initialized framework metadata and supplies exactly the methods above. `X509TrustManager` genuinely extends `TrustManager` using the narrow parent-interface catalog extension. The concrete manager overrides the interface method. Encoded-certificate objects extend X509Certificate/Certificate and override the base-owner getEncoded declaration, so original interface/base MethodIDs dispatch correctly.

The factory supports `PKIX` (case-insensitive) and a null system-root KeyStore. Unknown algorithms throw NoSuchAlgorithmException; null algorithms throw NullPointerException; explicit KeyStores throw KeyStoreException; getTrustManagers before init throws IllegalStateException. Native query failure publishes KeyStoreException with its error diagnostic; allocation failure in the reader publishes OutOfMemoryError. No successful fake chain-check methods are installed.

Successful init atomically publishes an immutable DER snapshot under the factory mutex, without holding that mutex or the JNI provider lock across native enumeration or observers. Existing managers/certificates retain their prior snapshots after another init. Each getter returns a fresh correctly typed Java array; getEncoded copies DER into a fresh `[B`, so caller mutation cannot change the anchor snapshot. Owned callback frames retire temporary JNI locals; actual Java arrays retain their elements. Service callbacks retain native shared state, check revocation, and reject cross-service or uninitialized object state. Revoke/destruction prevents later service calls while retained snapshots still own their data.

The native reader and all supplied callback bodies preserve native errno, LastError and floating-point environment. `Config.read_roots` is an explicit dependency injection point for isolated fixture cases; the production default is the genuine Windows reader. Observer events identify the method, reader use and certificate count, without exposing keys or changing trust decisions.

## Qualified component evidence

`work/java-tls-trust-qualification3/acceptance.json` (SHA256 `3df59e64ee17277eee80e224649e84f316b359f89797534900749906f5c64efb`) passed 6,630 checks and 1,420 actual translated NDK entry calls, including direct/V/A Java calls, exact base/interface dispatch, interface inheritance, typed arrays, full DER bytes, fresh-array mutation isolation, snapshot reinit/lifetimes, genuine exception identity, native errno/LastError/FENV preservation and full State/Memory-token preservation. A separate revoked-service child failed closed through the installed JNI boundary. The existing JNI interface-proxy regression passed 237 checks with the changed interface catalog.

The default native reader and actual JNI export both matched every DER byte in an independently enumerated read-only .NET/CryptoAPI public-root oracle: 84 root contexts minus 16 effective-usage exclusions and 8 cache-only explicit-distrust exclusions yielded 60 certificates. Both explicit Disallowed stores were empty in that environment. These counts describe the qualification machine's snapshot, not a fixed production result. The oracle bundle SHA256 is `28cd07a04036fd8e2acc0e9b59ac137ab0b4c06d448452ae3bae895d5d479207`.

The controller is `test_java_tls_trust.py`. Original-game TLS success and the first rendered frame remain separate integration outcomes; this component gate makes no successful TLS peer-verification or handshake claim.
