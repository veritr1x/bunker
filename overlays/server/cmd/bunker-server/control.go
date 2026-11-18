package main

import (
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"

	"lunar-tear/server/mobile"
)

// The control endpoint is how Pod Programs, running beside this server on a
// computer, does what it does through the app on a phone: edit the save with
// the server's own code, stop the server around a change and start it again.
// It listens on loopback only and wants the token in X-Bunker-Token.
//
//	POST /edit              one save edit, as the phone bridge sends it
//	POST /pause             stop the game's services, keep this program running
//	POST /resume?title=1    start them again; title=1 sends the game to its title screen
//	GET  /status            the server's status
//	POST /texture           {"bundle","target","size"}: decode one texture to a PNG
func serveControl(address, token, data, assets string) (string, error) {
	listener, e := net.Listen("tcp", address)
	if e != nil {
		return "", e
	}
	answer := func(w http.ResponseWriter, text string) {
		w.Header().Set("Content-Type", "application/json")
		io.WriteString(w, text)
	}
	result := func(w http.ResponseWriter, problem string) {
		b, _ := json.Marshal(map[string]any{"ok": problem == "", "error": problem})
		answer(w, string(b))
	}
	mux := http.NewServeMux()
	handle := func(method, path string, f func(http.ResponseWriter, *http.Request)) {
		mux.HandleFunc(path, func(w http.ResponseWriter, r *http.Request) {
			if subtle.ConstantTimeCompare([]byte(r.Header.Get("X-Bunker-Token")), []byte(token)) != 1 {
				http.Error(w, "forbidden", http.StatusForbidden)
				return
			}
			if r.Method != method {
				http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
				return
			}
			f(w, r)
		})
	}
	handle(http.MethodPost, "/edit", func(w http.ResponseWriter, r *http.Request) {
		body, e := io.ReadAll(io.LimitReader(r.Body, 64<<20))
		if e != nil {
			result(w, e.Error())
			return
		}
		answer(w, mobile.Edit(data, assets, string(body)))
	})
	handle(http.MethodPost, "/pause", func(w http.ResponseWriter, r *http.Request) {
		mobile.Stop()
		result(w, "")
	})
	handle(http.MethodPost, "/resume", func(w http.ResponseWriter, r *http.Request) {
		if e := mobile.Start(data, assets); e != nil {
			result(w, e.Error())
			return
		}
		if r.URL.Query().Get("title") == "1" {
			mobile.RequestTitle()
		}
		result(w, "")
	})
	handle(http.MethodGet, "/status", func(w http.ResponseWriter, r *http.Request) { answer(w, mobile.Status()) })
	handle(http.MethodPost, "/texture", func(w http.ResponseWriter, r *http.Request) {
		var request struct {
			Bundle, Target string
			Size           int
		}
		if e := json.NewDecoder(io.LimitReader(r.Body, 1<<20)).Decode(&request); e != nil {
			result(w, e.Error())
			return
		}
		result(w, mobile.Texture(request.Bundle, request.Target, request.Size))
	})
	go func() {
		if e := http.Serve(listener, mux); e != nil {
			fmt.Fprintln(os.Stderr, "bunker-server: control: "+e.Error())
		}
	}()
	return "http://" + listener.Addr().String(), nil
}
