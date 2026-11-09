package translation

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"os"
	"strings"
)

// listInfo is what the translator needs from list.bin: its md5, its revision
// and the English text entries. Reading and hashing the 26 MB file on every
// start is avoided by keeping these beside the builds, keyed by the file's
// size and modification time (a new import of the game files changes both).
type listInfo struct {
	Size     int64   `json:"size"`
	ModTime  int64   `json:"modTime"` // Unix nanoseconds
	MD5      string  `json:"md5"`
	Revision uint64  `json:"revision"`
	Entries  []Entry `json:"entries"`
}

func readListInfo(listPath, cachePath string) (*listInfo, error) {
	st, err := os.Stat(listPath)
	if err != nil {
		return nil, err
	}
	if data, err := os.ReadFile(cachePath); err == nil {
		var c listInfo
		if json.Unmarshal(data, &c) == nil && c.Size == st.Size() && c.ModTime == st.ModTime().UnixNano() && c.MD5 != "" {
			return &c, nil
		}
	}
	data, err := os.ReadFile(listPath)
	if err != nil {
		return nil, err
	}
	revision, entries, err := ParseList(data)
	if err != nil {
		return nil, err
	}
	sum := md5.Sum(data)
	info := &listInfo{Size: st.Size(), ModTime: st.ModTime().UnixNano(), MD5: hex.EncodeToString(sum[:]), Revision: revision}
	for _, e := range entries { // only these are ever translated: about 6,600 of 200,000
		if strings.HasPrefix(e.Path, englishTextPrefix) {
			info.Entries = append(info.Entries, e)
		}
	}
	if data, err := json.Marshal(info); err == nil {
		writeFileAtomic(cachePath, data, 0644) // a cache: if it cannot be saved, the next start reads the list again
	}
	return info, nil
}
