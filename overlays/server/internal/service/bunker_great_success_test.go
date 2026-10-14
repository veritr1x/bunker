package service

import "testing"

func TestGreatSuccess(t *testing.T) {
	if exp, great := rollGreatSuccess(1000, func(int) int { return 5 }); !great || exp != 1500 {
		t.Fatalf("roll 5: %d %v", exp, great)
	}
	if exp, great := rollGreatSuccess(1000, func(int) int { return 50 }); great || exp != 1000 {
		t.Fatalf("roll 50: %d %v", exp, great)
	}
	if _, great := rollGreatSuccess(0, func(int) int { return 0 }); great {
		t.Fatal("great success with no experience")
	}
}
