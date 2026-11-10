package translation

import (
	"encoding/json"
	"errors"
	"log"
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
	serr := tmp.Sync() // on disk before the rename, so a power cut cannot leave an empty file
	cerr := tmp.Close()
	werr = errors.Join(werr, serr)
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
// (a build id, or "none:<list md5>" for the original entries) to a game that
// last stored revision requested (the revision in its list request). It only
// ever goes up: a different fingerprint gets the next revision, at least
// original+RevisionOffset and above requested, so a damaged, lost or old
// state file cannot leave the game on a list it ignores. While no translation
// was ever served, the original list is served as it is and nothing is stored.
func ServedRevision(statePath string, original, requested uint64, fingerprint string) (uint64, error) {
	var s state
	data, err := os.ReadFile(statePath)
	switch {
	case errors.Is(err, os.ErrNotExist):
		if strings.HasPrefix(fingerprint, "none:") && requested <= original {
			return original, nil
		}
	case err != nil:
		return 0, err
	default:
		if json.Unmarshal(data, &s) != nil {
			log.Printf("[Translation] state file unreadable, starting above revision %d", requested)
			s = state{}
		}
		if s.Fingerprint == fingerprint && s.Revision >= requested {
			return s.Revision, nil
		}
	}
	next := max(s.Revision+1, original+RevisionOffset, requested+1)
	data, err = json.Marshal(state{Revision: next, Fingerprint: fingerprint})
	if err != nil {
		return 0, err
	}
	if err := writeFileAtomic(statePath, data, 0644); err != nil {
		return 0, err
	}
	return next, nil
}
