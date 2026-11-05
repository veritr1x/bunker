package bunkercache

import "testing"

func TestValueComputesOnceUntilInvalidated(t *testing.T) {
	calls := 0
	get := Value(func() int { calls++; return calls })
	if get() != 1 || get() != 1 || calls != 1 {
		t.Fatalf("computed %d times before Invalidate", calls)
	}
	Invalidate()
	if got := get(); got != 2 {
		t.Fatalf("after Invalidate got %d, want 2", got)
	}
	if get() != 2 || calls != 2 {
		t.Fatalf("computed %d times after one Invalidate", calls)
	}
}

func TestValuesKeepsBothResults(t *testing.T) {
	n := 0
	get := Values(func() (int, string) { n++; return n, "x" })
	a, b := get()
	if a != 1 || b != "x" {
		t.Fatalf("got %d %q", a, b)
	}
	Invalidate()
	if a, _ := get(); a != 2 {
		t.Fatalf("after Invalidate got %d, want 2", a)
	}
}
