package translation

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"hash/crc32"
	"sort"

	"github.com/pierrec/lz4/v4"

	"lunar-tear/server/mobile/unityasset"
)

const textAssetClass = 49

// Mask is the inverse of unityasset.Unmask: marker 0x31 masks bytes 1 to 255,
// 0x32 every byte from 1; byte 0 becomes the marker.
func Mask(plain []byte, name string, marker byte) []byte {
	out := bytes.Clone(plain)
	if len(out) == 0 {
		return out
	}
	n := len(out)
	if marker == 0x31 {
		n = min(256, n)
	}
	mask := unityasset.MaskBytes(name)
	for i := 1; i < n && len(mask) > 0; i++ {
		out[i] ^= mask[i%len(mask)]
	}
	out[0] = marker
	return out
}

// RebuildText rewrites the TextAssets of one masked text bundle. Each asset's
// text goes through edit; when any reports a change, the serialized file is
// written again (other objects' bytes kept, objects 8-byte aligned in their
// order), compressed with LZ4HC into one block, bundled and masked like the
// original. crc is the CRC-32 of the new serialized file, as list.bin keeps it.
// Nothing changed: out is nil.
func RebuildText(raw []byte, name string, edit func(text string) (string, bool)) (out []byte, crc uint32, changed bool, err error) {
	plain, err := unityasset.Unmask(raw, name)
	if err != nil {
		return nil, 0, false, err
	}
	b, err := readBundle(plain)
	if err != nil {
		return nil, 0, false, err
	}
	data, changed, err := rewriteTextAssets(b.data, edit)
	if err != nil || !changed {
		return nil, 0, false, err
	}
	bundle, err := writeBundle(b, data)
	if err != nil {
		return nil, 0, false, err
	}
	marker := raw[0]
	if marker != 0x31 && marker != 0x32 {
		marker = 0x32
	}
	return Mask(bundle, name, marker), crc32.ChecksumIEEE(data), true, nil
}

type bundleFile struct {
	version       uint32
	unityVersion  string
	unityRevision string
	flags         uint32
	hash          []byte
	nodeFlags     uint32
	nodeName      string
	data          []byte
}

type byteReader struct {
	b   []byte
	p   int
	err error
}

// take returns the next n bytes, or nil (and records an error) when they are
// not there; it never allocates, so a damaged length cannot ask for gigabytes.
func (r *byteReader) take(n int) []byte {
	if r.err != nil || n < 0 || n > len(r.b)-r.p {
		if r.err == nil {
			r.err = errors.New("unexpected end of data")
		}
		return nil
	}
	s := r.b[r.p : r.p+n]
	r.p += n
	return s
}

// left is how many bytes remain.
func (r *byteReader) left() int { return max(len(r.b)-r.p, 0) }

// count reads a u32 count of items at least size bytes each, failing when the
// remaining bytes cannot hold that many.
func (r *byteReader) count(o binary.ByteOrder, size int) int {
	n := int(r.u32(o))
	if r.err == nil && n > r.left()/size {
		r.err = fmt.Errorf("count %d does not fit in %d bytes", n, r.left())
	}
	if r.err != nil {
		return 0
	}
	return n
}

func (r *byteReader) u8() uint8 {
	if b := r.take(1); b != nil {
		return b[0]
	}
	return 0
}

func (r *byteReader) u16(o binary.ByteOrder) uint16 {
	if b := r.take(2); b != nil {
		return o.Uint16(b)
	}
	return 0
}

func (r *byteReader) u32(o binary.ByteOrder) uint32 {
	if b := r.take(4); b != nil {
		return o.Uint32(b)
	}
	return 0
}

func (r *byteReader) u64(o binary.ByteOrder) uint64 {
	if b := r.take(8); b != nil {
		return o.Uint64(b)
	}
	return 0
}

// maxTextBytes caps any size read from a text bundle (the largest is well under 1 MB).
const maxTextBytes = 64 << 20

func (r *byteReader) cstring() string {
	if r.err != nil {
		return ""
	}
	end := bytes.IndexByte(r.b[r.p:], 0)
	if end < 0 {
		r.err = errors.New("unterminated string")
		return ""
	}
	s := string(r.b[r.p : r.p+end])
	r.p += end + 1
	return s
}

func (r *byteReader) align(n int) { r.p = (r.p + n - 1) / n * n }

func uncompress(flags uint32, src []byte, size int) ([]byte, error) {
	if size < 0 || size > maxTextBytes {
		return nil, fmt.Errorf("size %d is out of range", size)
	}
	switch flags & 0x3f {
	case 0:
		return src, nil
	case 2, 3:
		out := make([]byte, size)
		n, err := lz4.UncompressBlock(src, out)
		if err != nil {
			return nil, fmt.Errorf("lz4: %w", err)
		}
		return out[:n], nil
	}
	return nil, fmt.Errorf("compression %d is not supported", flags&0x3f)
}

// readBundle reads a version-6 UnityFS bundle with one file, its block info
// stored with the header (the game's text bundles).
func readBundle(plain []byte) (*bundleFile, error) {
	be := binary.BigEndian
	r := &byteReader{b: plain}
	if r.cstring() != "UnityFS" {
		return nil, errors.New("not a UnityFS bundle")
	}
	b := &bundleFile{version: r.u32(be), unityVersion: r.cstring(), unityRevision: r.cstring()}
	r.u64(be) // size
	compressedInfo, infoSize := int(r.u32(be)), int(r.u32(be))
	b.flags = r.u32(be)
	if r.err != nil {
		return nil, r.err
	}
	if b.version != 6 || b.flags&0x40 == 0 || b.flags&0x80 != 0 {
		return nil, fmt.Errorf("bundle version %d flags 0x%x is not supported", b.version, b.flags)
	}
	info, err := uncompress(b.flags, r.take(compressedInfo), infoSize)
	if err != nil || r.err != nil {
		return nil, errors.Join(err, r.err)
	}
	ir := &byteReader{b: info}
	b.hash = bytes.Clone(ir.take(16))
	type block struct {
		size, csize uint32
		flags       uint16
	}
	blocks := make([]block, ir.count(be, 10))
	total := 0
	for i := range blocks {
		blocks[i] = block{ir.u32(be), ir.u32(be), ir.u16(be)}
		total += int(blocks[i].size)
	}
	if total > maxTextBytes {
		return nil, fmt.Errorf("bundle file of %d bytes is out of range", total)
	}
	nodes := int(ir.u32(be))
	if ir.err != nil || nodes != 1 {
		return nil, fmt.Errorf("bundle has %d files, want 1 (%v)", nodes, ir.err)
	}
	offset, size := ir.u64(be), ir.u64(be)
	b.nodeFlags = ir.u32(be)
	b.nodeName = ir.cstring()
	if ir.err != nil {
		return nil, ir.err
	}
	var data []byte
	for _, bl := range blocks {
		part, err := uncompress(uint32(bl.flags), r.take(int(bl.csize)), int(bl.size))
		if err != nil || r.err != nil {
			return nil, errors.Join(err, r.err)
		}
		data = append(data, part...)
	}
	if offset != 0 || size != uint64(len(data)) {
		return nil, fmt.Errorf("bundle file at %d+%d does not fill its %d bytes", offset, size, len(data))
	}
	b.data = data
	return b, nil
}

func compressHC(src []byte) ([]byte, bool) {
	dst := make([]byte, lz4.CompressBlockBound(len(src)))
	n, err := lz4.CompressBlockHC(src, dst, lz4.Level9, nil, nil)
	if err != nil || n == 0 || n >= len(src) {
		return src, false
	}
	return dst[:n], true
}

// writeBundle writes data as the bundle's one file in one block.
func writeBundle(b *bundleFile, data []byte) ([]byte, error) {
	be := binary.BigEndian
	payload, packed := compressHC(data)
	blockFlags := uint16(0)
	if packed {
		blockFlags = 3
	}
	var info bytes.Buffer
	info.Write(b.hash)
	binary.Write(&info, be, uint32(1))
	binary.Write(&info, be, uint32(len(data)))
	binary.Write(&info, be, uint32(len(payload)))
	binary.Write(&info, be, blockFlags)
	binary.Write(&info, be, uint32(1))
	binary.Write(&info, be, uint64(0))
	binary.Write(&info, be, uint64(len(data)))
	binary.Write(&info, be, b.nodeFlags)
	info.WriteString(b.nodeName)
	info.WriteByte(0)
	storedInfo, infoPacked := compressHC(info.Bytes())
	flags := b.flags &^ 0x3f
	if infoPacked {
		flags |= 3
	}
	var head bytes.Buffer
	head.WriteString("UnityFS\x00")
	binary.Write(&head, be, b.version)
	head.WriteString(b.unityVersion + "\x00" + b.unityRevision + "\x00")
	total := head.Len() + 8 + 12 + len(storedInfo) + len(payload)
	binary.Write(&head, be, int64(total))
	binary.Write(&head, be, uint32(len(storedInfo)))
	binary.Write(&head, be, uint32(info.Len()))
	binary.Write(&head, be, flags)
	head.Write(storedInfo)
	head.Write(payload)
	return head.Bytes(), nil
}

type tableObject struct {
	at          int // offset of byte_start in the object table
	start, size int
	classID     int32
}

// objectTable reads a format-21 serialized file's data offset, byte order and
// objects.
func objectTable(sf []byte) (int, binary.ByteOrder, []tableObject, error) {
	be := binary.BigEndian
	r := &byteReader{b: sf}
	r.u32(be) // metadata size
	r.u32(be) // file size
	format := r.u32(be)
	dataOffset := int(r.u32(be))
	if r.err == nil && format != 21 {
		return 0, nil, nil, fmt.Errorf("serialized file format %d is not supported", format)
	}
	var order binary.ByteOrder = be
	if b := r.take(4); b != nil && b[0] == 0 {
		order = binary.LittleEndian
	}
	if r.err != nil || dataOffset < r.p || dataOffset > len(sf) {
		return 0, nil, nil, fmt.Errorf("serialized file header is damaged (data at %d of %d bytes)", dataOffset, len(sf))
	}
	r.cstring() // Unity version
	r.u32(order)
	typeTree := r.u8() != 0
	classes := make([]int32, r.count(order, 23))
	for i := range classes {
		if r.err != nil {
			break
		}
		classes[i] = int32(r.u32(order))
		r.take(1)    // stripped
		r.u16(order) // script type index
		if classes[i] == 114 {
			r.take(16)
		}
		r.take(16)
		if typeTree {
			nodes, strings := int(r.u32(order)), int(r.u32(order))
			r.take(nodes*32 + strings)
			r.take(int(r.u32(order)) * 4) // dependencies
		}
	}
	objects := make([]tableObject, r.count(order, 20))
	for i := range objects {
		if r.err != nil {
			break
		}
		r.align(4)
		r.u64(order) // path id
		o := tableObject{at: r.p}
		o.start, o.size = int(r.u32(order)), int(r.u32(order))
		typeIndex := int(int32(r.u32(order)))
		if typeIndex >= 0 && typeIndex < len(classes) {
			o.classID = classes[typeIndex]
		}
		objects[i] = o
	}
	if r.err != nil {
		return 0, nil, nil, r.err
	}
	for _, o := range objects {
		if o.at+8 > dataOffset || o.start < 0 || o.size < 0 || o.start > len(sf)-dataOffset || o.size > len(sf)-dataOffset-o.start {
			return 0, nil, nil, errors.New("object outside the serialized file")
		}
	}
	return dataOffset, order, objects, nil
}

// rewriteTextAssets passes every TextAsset's text through edit and, if any
// changed, lays the objects out again.
func rewriteTextAssets(sf []byte, edit func(string) (string, bool)) ([]byte, bool, error) {
	dataOffset, order, objects, err := objectTable(sf)
	if err != nil {
		return nil, false, err
	}
	sort.Slice(objects, func(i, j int) bool { return objects[i].start < objects[j].start })
	out := bytes.Clone(sf[:dataOffset])
	changed := false
	for _, o := range objects {
		body := sf[dataOffset+o.start : dataOffset+o.start+o.size]
		if o.classID == textAssetClass {
			r := &byteReader{b: body}
			assetName := r.take(int(r.u32(order)))
			r.align(4)
			text := r.take(int(r.u32(order)))
			r.align(4)
			if r.err != nil || r.p > len(body) {
				return nil, false, errors.New("unreadable TextAsset")
			}
			rest := body[r.p:]
			newText, did := edit(string(text))
			changed = changed || did
			var nb bytes.Buffer
			binary.Write(&nb, order, uint32(len(assetName)))
			nb.Write(assetName)
			nb.Write(make([]byte, (4-nb.Len()%4)%4))
			binary.Write(&nb, order, uint32(len(newText)))
			nb.WriteString(newText)
			nb.Write(make([]byte, (4-nb.Len()%4)%4))
			nb.Write(rest)
			body = nb.Bytes()
		}
		for (len(out)-dataOffset)%8 != 0 {
			out = append(out, 0)
		}
		order.PutUint32(out[o.at:], uint32(len(out)-dataOffset))
		order.PutUint32(out[o.at+4:], uint32(len(body)))
		out = append(out, body...)
	}
	binary.BigEndian.PutUint32(out[4:], uint32(len(out)))
	return out, changed, nil
}
