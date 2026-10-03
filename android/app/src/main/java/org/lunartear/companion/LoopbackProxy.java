package org.lunartear.companion;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.ProxySelector;
import java.net.SocketAddress;
import java.net.URI;
import java.util.Collections;
import java.util.List;

/**
 * Sends the game's requests to its own server on this phone directly.
 *
 * Android's Java HTTP stack routes even http://127.0.0.1 through the phone's
 * proxy, such as one set by a VPN or "network accelerator" app. That proxy
 * cannot reach this phone's loopback, so every asset download waits out the
 * game's 10-second timeout and retries: loading stalls for minutes until the
 * proxy is turned off (for example by airplane mode). Loopback addresses get
 * no proxy here; everything else keeps the phone's normal proxy.
 */
final class LoopbackProxy extends ProxySelector {
    private static final List<Proxy> DIRECT = Collections.singletonList(Proxy.NO_PROXY);
    private final ProxySelector system;

    private LoopbackProxy(ProxySelector system) { this.system = system; }

    /** Installs the selector, and again whenever Android replaces it after a proxy change. */
    static void install() {
        wrap();
        Thread keeper = new Thread(() -> {
            while (true) {
                try { Thread.sleep(1000); } catch (InterruptedException e) { return; }
                wrap();
            }
        }, "lunar-loopback-proxy");
        keeper.setDaemon(true);
        keeper.start();
    }

    private static synchronized void wrap() {
        ProxySelector current = ProxySelector.getDefault();
        if (!(current instanceof LoopbackProxy)) ProxySelector.setDefault(new LoopbackProxy(current));
    }

    static boolean isLoopback(String host) {
        if (host == null) return false;
        host = host.toLowerCase(java.util.Locale.ROOT);
        return host.equals("localhost") || host.startsWith("127.") || host.equals("::1") || host.equals("[::1]");
    }

    @Override public List<Proxy> select(URI uri) {
        if (uri != null && isLoopback(uri.getHost())) return DIRECT;
        return system != null ? system.select(uri) : DIRECT;
    }

    @Override public void connectFailed(URI uri, SocketAddress address, IOException error) {
        if (system != null && (uri == null || !isLoopback(uri.getHost()))) system.connectFailed(uri, address, error);
    }
}
