// Package bunkercache holds values derived from the master data: computed on
// first use, like sync.OnceValue, and again after Invalidate.
//
// The server can start again in the same process with different master data
// (Pod Programs beside the running game: mobile.Start after Stop), and package
// variables outlive that, as does the desktop server's master data reload.
// runtime.Holder.Reload calls Invalidate once the new master data is loaded,
// so every table built from it is built again from the new one.
package bunkercache

import (
	"sync"
	"sync/atomic"
)

// generation counts Invalidate calls; a value remembers the one it was built in.
var generation atomic.Uint64

// Invalidate drops every value: each is computed again on its next use.
func Invalidate() { generation.Add(1) }

// Value returns a function that computes f on first use and again after
// Invalidate, and otherwise returns what it computed.
func Value[T any](f func() T) func() T {
	var (
		mu    sync.Mutex
		built bool
		gen   uint64
		value T
	)
	return func() T {
		now := generation.Load()
		mu.Lock()
		defer mu.Unlock()
		if !built || gen != now {
			value, gen, built = f(), now, true
		}
		return value
	}
}

// Values is Value for a function with two results (sync.OnceValues).
func Values[T1, T2 any](f func() (T1, T2)) func() (T1, T2) {
	type pair struct {
		a T1
		b T2
	}
	get := Value(func() pair {
		a, b := f()
		return pair{a, b}
	})
	return func() (T1, T2) {
		p := get()
		return p.a, p.b
	}
}
