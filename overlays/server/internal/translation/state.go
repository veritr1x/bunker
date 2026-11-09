package translation

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
)

// RevisionOffset puts the first translated list above any revision the game
// may have seen before (the game ignores a changed list whose revision is not
// higher than the one it stored).
const RevisionOffset = 1000

type state struct {
	Revision    uint64 `json:"revision"`
	Fingerprint string `json:"fingerprint"`
}

// writeFileAtomic writes data under a temporary name beside path, then renames
// it into place: a reader sees the old file or the new one, never part of it,
// and a link to the old file keeps the old bytes.
func writeFileAtomic(path string, data []byte, mode os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".*")
	if err != nil {
		return err
	}
	_, werr := tmp.Write(data)
	cerr := tmp.Close()
	if err := errors.Join(werr, cerr, os.Chmod(tmp.Name(), mode)); err != nil {
		os.Remove(tmp.Name())
		return err
	}
	if err := os.Rename(tmp.Name(), path); err != nil {
		os.Remove(tmp.Name())
		return err
	}
	return nil
}

// ServedRevision is the revision to serve for the list named by fingerprint
// (a build id, or "none:<list md5>" for the original entries). It only ever
// goes up: a different fingerprint gets the next revision, at least
// original+RevisionOffset. While no translation was ever served, the original
// list is served as it is and nothing is stored.
func ServedRevision(statePath string, original uint64, fingerprint string) (uint64, error) {
	var s state
	data, err := os.ReadFile(statePath)
	switch {
	case errors.Is(err, os.ErrNotExist):
		if strings.HasPrefix(fingerprint, "none:") {
			return original, nil
		}
	case err != nil:
		return 0, err
	default:
		if err := json.Unmarshal(data, &s); err != nil {
			return 0, err
		}
		if s.Fingerprint == fingerprint {
			return s.Revision, nil
		}
	}
	next := max(s.Revision+1, original+RevisionOffset)
	data, err = json.Marshal(state{Revision: next, Fingerprint: fingerprint})
	if err != nil {
		return 0, err
	}
	if err := writeFileAtomic(statePath, data, 0644); err != nil {
		return 0, err
	}
	return next, nil
}
