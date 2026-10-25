package main

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

// The emulator passes a held key on as a stream of taps and drops a held key
// when another is pressed, so the game cannot tell which movement keys are
// held. This helper watches the real keyboard while the emulator window has
// focus and sends each press and release to the game (HostKeys.java) over
// adb's port forwarding. It changes no keys, so typing works as before, and
// it quits when the emulator closes.

var (
	user32   = syscall.NewLazyDLL("user32.dll")
	kernel32 = syscall.NewLazyDLL("kernel32.dll")
)

// The keys the game moves with, by Windows virtual-key code.
var movementKeys = map[uint32]string{
	'W': "w", 'A': "a", 'S': "s", 'D': "d",
	0x26: "up", 0x28: "down", 0x25: "left", 0x27: "right",
	0x10: "shift", 0xA0: "shift", 0xA1: "shift",
}

const emulatorTitle = "Android Emulator - " + avdName + ":"

// startKeys forwards a local port to the game and starts the helper, which
// keeps adb running until the emulator closes. It reports whether it did.
func startKeys(f folders, dev device) bool {
	out, err := dev.run("forward", "tcp:0", "tcp:"+strconv.Itoa(hostKeysPort))
	port, convErr := strconv.Atoi(strings.TrimSpace(out))
	if err != nil || convErr != nil {
		return false
	}
	self, err := os.Executable()
	if err != nil {
		return false
	}
	cmd := exec.Command(self, "-keys", strconv.Itoa(port), "-data", f.root)
	cmd.Env = f.env()
	detach(cmd)
	return cmd.Start() == nil
}

// runKeys is the helper: Bunker.exe -keys PORT -data FOLDER.
func runKeys(port int, root string) {
	name, _ := syscall.UTF16PtrFromString(`Local\BunkerKeys`)
	kernel32.NewProc("CreateMutexW").Call(0, 0, uintptr(unsafe.Pointer(name)))
	if syscall.GetLastError() == syscall.Errno(183) { // ERROR_ALREADY_EXISTS: one is running
		return
	}
	f := newFolders(root)
	defer func() {
		stop := exec.Command(f.adb(), "kill-server")
		stop.Env = f.env()
		stop.Run()
	}()

	keys := make(chan string, 64)
	go send(port, keys)
	runtime.LockOSThread()
	thread, _, _ := kernel32.NewProc("GetCurrentThreadId").Call()
	go func() {
		for emulatorWindow() != 0 {
			time.Sleep(2 * time.Second)
		}
		user32.NewProc("PostThreadMessageW").Call(thread, 0x12, 0, 0) // WM_QUIT
	}()
	hook(keys)
}

// hook reports movement keys to keys until the thread gets WM_QUIT.
func hook(keys chan<- string) {
	held := map[string]bool{}
	report := func(key string, down bool) {
		held[key] = down
		state := "0"
		if down {
			state = "1"
		}
		select {
		case keys <- key + " " + state:
		default:
		}
	}
	callback := syscall.NewCallback(func(code int, wParam, lParam uintptr) uintptr {
		if code == 0 {
			// KBDLLHOOKSTRUCT, copied out of the hook's memory.
			var info struct{ VK, Scan, Flags, Time uint32 }
			kernel32.NewProc("RtlMoveMemory").Call(uintptr(unsafe.Pointer(&info)), lParam, unsafe.Sizeof(info))
			if key, ok := movementKeys[info.VK]; ok {
				down := wParam == 0x100 || wParam == 0x104 // WM_KEYDOWN, WM_SYSKEYDOWN
				// Presses count only in the emulator; releases always, so
				// nothing stays held after switching windows.
				if down && !held[key] && focusedOnEmulator() {
					report(key, true)
				} else if !down && held[key] {
					report(key, false)
				}
			}
		}
		next, _, _ := user32.NewProc("CallNextHookEx").Call(0, uintptr(code), wParam, lParam)
		return next
	})
	module, _, _ := kernel32.NewProc("GetModuleHandleW").Call(0)
	h, _, _ := user32.NewProc("SetWindowsHookExW").Call(13, callback, module, 0) // WH_KEYBOARD_LL
	if h == 0 {
		return
	}
	defer user32.NewProc("UnhookWindowsHookEx").Call(h)
	var msg [48]byte
	getMessage := user32.NewProc("GetMessageW")
	for {
		r, _, _ := getMessage.Call(uintptr(unsafe.Pointer(&msg[0])), 0, 0, 0)
		if r == 0 || int32(r) == -1 {
			return
		}
	}
}

// send keeps a connection to the game and writes key changes to it. After it
// reconnects, such as when the game restarted, it repeats what is held.
func send(port int, keys <-chan string) {
	held := map[string]bool{}
	var conn net.Conn
	for change := range keys {
		key, state, _ := strings.Cut(change, " ")
		held[key] = state == "1"
		if conn == nil {
			c, err := net.DialTimeout("tcp", fmt.Sprintf("127.0.0.1:%d", port), time.Second)
			if err != nil {
				continue
			}
			conn = c
			for k, down := range held {
				if down && k != key {
					fmt.Fprintf(conn, "%s 1\n", k)
				}
			}
		}
		if _, err := fmt.Fprintf(conn, "%s\n", change); err != nil {
			conn.Close()
			conn = nil
		}
	}
}

func focusedOnEmulator() bool {
	h, _, _ := user32.NewProc("GetForegroundWindow").Call()
	return strings.HasPrefix(windowText(h), emulatorTitle)
}

// One window-listing callback for the helper's life: Windows callbacks made
// with syscall.NewCallback are never freed.
var (
	foundWindow uintptr
	findWindow  = syscall.NewCallback(func(h, _ uintptr) uintptr {
		if strings.HasPrefix(windowText(h), emulatorTitle) {
			foundWindow = h
			return 0
		}
		return 1
	})
)

// emulatorWindow finds the emulator's window, or returns 0.
func emulatorWindow() uintptr {
	foundWindow = 0
	user32.NewProc("EnumWindows").Call(findWindow, 0)
	return foundWindow
}

func windowText(h uintptr) string {
	buf := make([]uint16, 256)
	n, _, _ := user32.NewProc("GetWindowTextW").Call(h, uintptr(unsafe.Pointer(&buf[0])), 256)
	return syscall.UTF16ToString(buf[:n])
}
