package translation

import "testing"

func TestReplaceValues(t *testing.T) {
	in := "// c\r\nui.a:Quests\r\nui.b:Menu 　\r\nnokey\r\n\r\nui.c:x:y"
	out, n := ReplaceValues(in, map[string]string{"ui.a": "Missões", "ui.c": "z"})
	want := "// c\r\nui.a:Missões\r\nui.b:Menu 　\r\nnokey\r\n\r\nui.c:z"
	if out != want || n != 2 {
		t.Fatalf("got %q %d", out, n)
	}
}

func TestReplaceValuesKeyIsTrimmedValueIsNot(t *testing.T) {
	out, n := ReplaceValues(" ui.a :old", map[string]string{"ui.a": " new "})
	if out != " ui.a : new " || n != 1 {
		t.Fatalf("got %q %d", out, n)
	}
}

func TestReplaceValuesNothingToDo(t *testing.T) {
	in := "a:b\n"
	if out, n := ReplaceValues(in, map[string]string{"z": "q"}); out != in || n != 0 {
		t.Fatalf("got %q %d", out, n)
	}
}

func TestReplaceValuesEveryLineOfAKeyAndComments(t *testing.T) {
	in := "a:1\n//a:2\na:3\n"
	out, n := ReplaceValues(in, map[string]string{"a": "x"})
	if out != "a:x\n//a:2\na:x\n" || n != 2 {
		t.Fatalf("got %q %d", out, n)
	}
}
