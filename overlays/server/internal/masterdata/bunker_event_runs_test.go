package masterdata

import "testing"

// Chapter 510's first run (copy 0) had link 17, medal 25 and quest bonuses in
// it; the calendar gives the copy link 17 + 100 * COPY_STEP.
const testEventRuns = `{"copy_step":10000000,"chapters":{"510":[
 {"link":17,"display":200011,"quests":[200271],"drops":{"200271":[[6,25,9],[5,100002,4]]},
  "bonus":{"200271":"b0"},"bonuses":{"b0":[["character",1001,0,[[6,25,2]]],["weapon",300,2,[[6,25,5]]]]}},
 null]}}`

func TestEventRunForTheCalendarsCopy(t *testing.T) {
	runs, err := ParseEventRuns([]byte(testEventRuns))
	if err != nil {
		t.Fatal(err)
	}
	run := runs.For(510, 17+100*10_000_000)
	if run == nil {
		t.Fatal("the first run's copy found no run")
	}
	if got := run.Drops[200271]; len(got) != 2 || got[0] != [3]int32{6, 25, 9} {
		t.Fatalf("drops %v", got)
	}
	rules := run.BonusRules(200271)
	if len(rules) != 2 || rules[1].Kind != "weapon" || rules[1].Id != 300 || rules[1].LimitBreak != 2 || rules[1].Pays[0] != [3]int32{6, 25, 5} {
		t.Fatalf("bonus rules %+v", rules)
	}
}

func TestEventRunNeedsTheCalendarsLink(t *testing.T) {
	runs, _ := ParseEventRuns([]byte(testEventRuns))
	if runs.For(510, 84) != nil {
		t.Fatal("the final game data's chapter (calendar off) took a run's drops")
	}
	if runs.For(510+10_000_000, 17+101*10_000_000) != nil {
		t.Fatal("the last run (null) took a run")
	}
	if runs.For(600, 17+100*10_000_000) != nil {
		t.Fatal("a chapter without runs took one")
	}
}

func TestShippedEventRunsParse(t *testing.T) {
	runs := EventRuns()
	if runs == nil || runs.For(510, 17+100*10_000_000) == nil {
		t.Fatal("event_runs.json has no first run for chapter 510")
	}
	if got := runs.For(510, 17+100*10_000_000).Drops[200271]; len(got) == 0 || got[0][1] != 25 {
		t.Fatalf("chapter 510's first run drops %v, want medal 25", got)
	}
}
