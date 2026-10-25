package org.veritr1x.bunker;

import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * The true state of the movement keys, from Bunker.exe on Windows. The
 * emulator passes a held key on as a stream of taps and drops a held key
 * when another is pressed, so the game cannot tell what is held from the
 * keys it receives. Bunker.exe watches the computer's keyboard instead and
 * sends each press and release here, through adb's port forwarding, as lines
 * such as "w 1" and "w 0". Only on the emulator, and only on this device's
 * loopback address.
 */
final class HostKeys {
    static final int PORT = 27183;

    private static Keyboard keyboard;
    private static boolean started;
    private static volatile boolean connected;

    private HostKeys() {}

    /** Sends what Bunker.exe reports to the game's current keyboard controls. */
    static synchronized void attach(Keyboard target) {
        keyboard = target;
        if (started || !onEmulator()) return;
        started = true;
        Handler main = new Handler(Looper.getMainLooper());
        Thread thread = new Thread(() -> serve(main), "bunker-host-keys");
        thread.setDaemon(true);
        thread.start();
    }

    /** Whether Bunker.exe is sending the keys, so the emulator's own key events are left out. */
    static boolean connected() { return connected; }

    private static boolean onEmulator() {
        return Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish");
    }

    private static void serve(Handler main) {
        try (ServerSocket server = new ServerSocket(PORT, 1, InetAddress.getLoopbackAddress())) {
            while (true) {
                try (Socket client = server.accept();
                     BufferedReader in = new BufferedReader(new InputStreamReader(client.getInputStream(), StandardCharsets.US_ASCII))) {
                    connected = true;
                    String line;
                    while ((line = in.readLine()) != null) {
                        String[] parts = line.trim().split(" ");
                        if (parts.length != 2) continue;
                        String key = parts[0];
                        boolean pressed = parts[1].equals("1");
                        main.post(() -> { Keyboard k = keyboard; if (k != null) k.host(key, pressed); });
                    }
                } catch (Exception lost) {
                    // Bunker.exe went away; wait for it to connect again.
                } finally {
                    connected = false;
                    main.post(() -> { Keyboard k = keyboard; if (k != null) k.release(); });
                }
            }
        } catch (Exception error) {
            Log.w("Bunker", "Keyboard link from Bunker.exe unavailable: " + error);
        }
    }
}
