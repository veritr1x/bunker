package translation

import (
	"encoding/binary"
	"errors"
	"fmt"
	"sort"
	"strings"
)

// list.bin is a protobuf message: field 1 is the list revision, each field 2
// is an asset bundle entry (field 4 holds resources such as movies).
const (
	listRevisionField = 1
	listBundleField   = 2
	entryPath         = 3
	entrySize         = 4
	entryCRC          = 5
	entryMD5          = 10
	entryObjectID     = 11
)

// Entry is an asset bundle in list.bin.
type Entry struct {
	ObjectID, Path string
	Size           uint64
	CRC            uint32
	MD5            string
}

type protoField struct {
	number, wire int
	raw          []byte // the whole field, tag included
	varint       uint64
	bytes        []byte
}

// walkFields calls fn for each field in order without collecting them; fn
// returns false to stop early.
func walkFields(data []byte, fn func(protoField) bool) error {
	for i := 0; i < len(data); {
		start := i
		tag, n := binary.Uvarint(data[i:])
		if n <= 0 {
			return errors.New("bad tag")
		}
		i += n
		f := protoField{number: int(tag >> 3), wire: int(tag & 7)}
		switch f.wire {
		case 0:
			v, n := binary.Uvarint(data[i:])
			if n <= 0 {
				return errors.New("bad varint")
			}
			f.varint, i = v, i+n
		case 1:
			i += 8
		case 2:
			l, n := binary.Uvarint(data[i:])
			if n <= 0 || uint64(len(data)-i-n) < l {
				return errors.New("bad length")
			}
			f.bytes, i = data[i+n:i+n+int(l)], i+n+int(l)
		case 5:
			i += 4
		default:
			return fmt.Errorf("wire type %d", f.wire)
		}
		if i > len(data) {
			return errors.New("truncated field")
		}
		f.raw = data[start:i]
		if !fn(f) {
			return nil
		}
	}
	return nil
}

// entryIDBytes is an entry's object id, read without decoding the rest.
func entryIDBytes(data []byte) []byte {
	var id []byte
	walkFields(data, func(f protoField) bool {
		if f.number == entryObjectID && f.wire == 2 {
			id = f.bytes
			return false
		}
		return true
	})
	return id
}

func parseEntry(data []byte) (Entry, bool) {
	var e Entry
	err := walkFields(data, func(f protoField) bool {
		switch {
		case f.number == entryPath && f.wire == 2:
			e.Path = string(f.bytes)
		case f.number == entrySize && f.wire == 0:
			e.Size = f.varint
		case f.number == entryCRC && f.wire == 0:
			e.CRC = uint32(f.varint)
		case f.number == entryMD5 && f.wire == 2:
			e.MD5 = string(f.bytes)
		case f.number == entryObjectID && f.wire == 2:
			e.ObjectID = string(f.bytes)
		}
		return true
	})
	return e, err == nil && e.ObjectID != "" && e.Path != ""
}

// ParseList reads the revision and the asset bundle entries of list.bin.
func ParseList(data []byte) (uint64, []Entry, error) {
	var revision uint64
	var entries []Entry
	err := walkFields(data, func(f protoField) bool {
		switch {
		case f.number == listRevisionField && f.wire == 0:
			revision = f.varint
		case f.number == listBundleField && f.wire == 2:
			if e, ok := parseEntry(f.bytes); ok {
				entries = append(entries, e)
			}
		}
		return true
	})
	if err != nil {
		return 0, nil, err
	}
	return revision, entries, nil
}

func appendVarintField(b []byte, number int, v uint64) []byte {
	b = binary.AppendUvarint(b, uint64(number<<3))
	return binary.AppendUvarint(b, v)
}

func appendBytesField(b []byte, number int, v []byte) []byte {
	b = binary.AppendUvarint(b, uint64(number<<3|2))
	b = binary.AppendUvarint(b, uint64(len(v)))
	return append(b, v...)
}

// PatchList returns list.bin with its revision set, the size, CRC and md5 of
// each entry in changes (by object id) replaced and the entries in added
// (whole entries) after the others; every other byte is kept.
//
// It walks the list once without collecting its 200,000 entries: only the
// object id of each entry is read, and only the changed ones are decoded.
func PatchList(data []byte, revision uint64, changes map[string]Entry, added [][]byte) ([]byte, error) {
	out := make([]byte, 0, len(data)+64)
	found := map[string]bool{}
	err := walkFields(data, func(f protoField) bool {
		switch {
		case f.number == listRevisionField && f.wire == 0:
			out = appendVarintField(out, listRevisionField, revision)
			return true
		case f.number == listBundleField && f.wire == 2 && len(changes) > 0:
			id := entryIDBytes(f.bytes)
			change, wanted := changes[string(id)]
			if !wanted {
				break
			}
			var entry []byte
			walkFields(f.bytes, func(g protoField) bool {
				switch {
				case g.number == entrySize && g.wire == 0:
					entry = appendVarintField(entry, entrySize, change.Size)
				case g.number == entryCRC && g.wire == 0:
					entry = appendVarintField(entry, entryCRC, uint64(change.CRC))
				case g.number == entryMD5 && g.wire == 2:
					entry = appendBytesField(entry, entryMD5, []byte(change.MD5))
				default:
					entry = append(entry, g.raw...)
				}
				return true
			})
			out = appendBytesField(out, listBundleField, entry)
			found[change.ObjectID] = true
			return true
		}
		out = append(out, f.raw...)
		return true
	})
	if err != nil {
		return nil, err
	}
	var missing []string
	for id := range changes {
		if !found[id] {
			missing = append(missing, id)
		}
	}
	if len(missing) > 0 {
		sort.Strings(missing)
		return nil, fmt.Errorf("list.bin has no entry %s", strings.Join(missing, ", "))
	}
	for _, entry := range added {
		out = appendBytesField(out, listBundleField, entry)
	}
	return out, nil
}
