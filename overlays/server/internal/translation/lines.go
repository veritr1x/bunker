// Package translation applies a language pack to the game's English text: it
// builds translated copies of the text bundles in a folder of their own and
// serves a list.bin that points the game to them under a higher revision.
package translation

import "strings"

// ReplaceValues swaps the value of every "key:value" line whose key is in
// values, keeping everything else byte for byte. Lines follow the export's
// rules (scripts/game_text.py parse_lines): one trailing CR is not part of the
// value, blank and "//" lines are skipped, the key is the trimmed text before
// the first ':' and the value is everything after it.
func ReplaceValues(text string, values map[string]string) (string, int) {
	lines := strings.Split(text, "\n")
	changed := 0
	for i, line := range lines {
		body, cr := strings.CutSuffix(line, "\r")
		stripped := strings.TrimSpace(body)
		if stripped == "" || strings.HasPrefix(stripped, "//") {
			continue
		}
		head, _, found := strings.Cut(body, ":")
		if !found {
			continue
		}
		value, ok := values[strings.TrimSpace(head)]
		if !ok || strings.TrimSpace(head) == "" {
			continue
		}
		line = head + ":" + value
		if cr {
			line += "\r"
		}
		lines[i] = line
		changed++
	}
	return strings.Join(lines, "\n"), changed
}
