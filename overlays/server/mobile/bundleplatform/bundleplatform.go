// Package bundleplatform reads which platform a game bundle was built for.
// The game's iOS and Android clients each load only their own bundles, so
// game files for the other platform install but leave the game loading.
//
// The same file lives in overlays/server/mobile/bundleplatform and
// windows/bundleplatform; a test in windows/ fails when they differ. The
// unmasking and bundle layout follow mobile/unityasset/bundle.go.
package bundleplatform

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"path/filepath"
	"strings"

	"github.com/pierrec/lz4/v4"
)

// Unity's build targets for the game's two clients.
const (
	IOS     = 9
	Android = 13
)

// Name names a build target for the player.
func Name(platform int) string {
	switch platform {
	case IOS:
		return "iOS"
	case Android:
		return "Android"
	}
	return "an unknown platform"
}

// Of reads the platform of a bundle's bytes. path is the bundle's path (any
// prefix, then assetbundle/…), which its mask is made from.
func Of(raw []byte, path string) (int, error) {
	data, err := unmask(raw, maskName(path))
	if err != nil {
		return 0, err
	}
	files, err := parse(data)
	if err != nil {
		return 0, err
	}
	for _, f := range files {
		if p, ok := serializedPlatform(f); ok {
			return p, nil
		}
	}
	return 0, errors.New("no serialized file in the bundle")
}

// maskName is Octo's mask for a bundle: its path under assetbundle/, without
// the suffix, joined by ')'.
func maskName(path string) string {
	norm := filepath.ToSlash(path)
	if i := strings.Index(norm, "assetbundle/"); i >= 0 {
		norm = norm[i+len("assetbundle/"):]
	}
	return strings.ReplaceAll(strings.TrimSuffix(norm, ".assetbundle"), "/", ")")
}

func maskBytes(name string) []byte {
	chars := []byte(name)
	n := len(chars)
	buf := make([]byte, n*2)
	for i, c := range chars {
		buf[2*i] = c
		buf[2*n-1-2*i] = ^c
	}
	h := byte(0xbb)
	for _, b := range buf {
		h = (h&1)<<7 | h>>1
		h ^= b
	}
	for i := range buf {
		buf[i] ^= h
	}
	return buf
}

// unmask reverses Octo's MaskedHeaderStream: version 0x31 masks the first 256
// bytes, 0x32 everything.
func unmask(raw []byte, name string) ([]byte, error) {
	if len(raw) == 0 {
		return nil, errors.New("empty bundle")
	}
	if bytes.HasPrefix(raw, []byte("UnityFS")) {
		return raw, nil
	}
	n := len(raw)
	switch raw[0] {
	case 0x31:
		n = min(256, len(raw))
	case 0x32:
	default:
		return nil, fmt.Errorf("unknown bundle mask version 0x%02x", raw[0])
	}
	mask := maskBytes(name)
	if len(mask) == 0 {
		return nil, errors.New("empty mask name")
	}
	out := bytes.Clone(raw)
	for i := 1; i < n; i++ {
		out[i] ^= mask[i%len(mask)]
	}
	out[0] = 'U'
	return out, nil
}

type reader struct {
	b   []byte
	p   int
	err error
}

func (r *reader) take(n int) []byte {
	if r.err != nil || n < 0 || r.p+n > len(r.b) {
		r.err = errors.New("truncated bundle")
		return nil
	}
	out := r.b[r.p : r.p+n]
	r.p += n
	return out
}
func (r *reader) u16() uint16 {
	if b := r.take(2); b != nil {
		return binary.BigEndian.Uint16(b)
	}
	return 0
}
func (r *reader) u32() uint32 {
	if b := r.take(4); b != nil {
		return binary.BigEndian.Uint32(b)
	}
	return 0
}
func (r *reader) u64() uint64 {
	if b := r.take(8); b != nil {
		return binary.BigEndian.Uint64(b)
	}
	return 0
}
func (r *reader) cstring() string {
	if r.err != nil {
		return ""
	}
	end := bytes.IndexByte(r.b[r.p:], 0)
	if end < 0 {
		r.err = errors.New("truncated bundle")
		return ""
	}
	s := string(r.b[r.p : r.p+end])
	r.p += end + 1
	return s
}
func (r *reader) align(n int) { r.p = (r.p + n - 1) / n * n }

func decompress(flags uint32, src []byte, size int) ([]byte, error) {
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
	return nil, fmt.Errorf("unsupported bundle compression %d", flags&0x3f)
}

// parse returns the files in an unmasked UnityFS bundle.
func parse(data []byte) ([][]byte, error) {
	r := &reader{b: data}
	if sig := r.cstring(); sig != "UnityFS" {
		return nil, fmt.Errorf("not a UnityFS bundle")
	}
	version := r.u32()
	r.cstring()
	r.cstring()
	r.u64()
	compressedInfo, uncompressedInfo, flags := int(r.u32()), int(r.u32()), r.u32()
	if version >= 7 {
		r.align(16)
	}
	var info []byte
	if flags&0x80 != 0 {
		if compressedInfo > len(data) {
			return nil, errors.New("bad block info size")
		}
		info = data[len(data)-compressedInfo:]
	} else {
		info = r.take(compressedInfo)
	}
	if r.err != nil {
		return nil, r.err
	}
	if flags&0x200 != 0 {
		r.align(16)
	}
	info, err := decompress(flags, info, uncompressedInfo)
	if err != nil {
		return nil, err
	}
	ir := &reader{b: info}
	ir.take(16)
	type block struct {
		u, c  int
		flags uint16
	}
	blocks := make([]block, ir.u32())
	for i := range blocks {
		blocks[i] = block{int(ir.u32()), int(ir.u32()), ir.u16()}
	}
	type node struct{ offset, size int64 }
	nodes := make([]node, ir.u32())
	for i := range nodes {
		nodes[i] = node{int64(ir.u64()), int64(ir.u64())}
		ir.u32()
		ir.cstring()
	}
	if ir.err != nil {
		return nil, ir.err
	}
	var stream bytes.Buffer
	for _, b := range blocks {
		chunk := r.take(b.c)
		if r.err != nil {
			return nil, r.err
		}
		out, err := decompress(uint32(b.flags), chunk, b.u)
		if err != nil {
			return nil, err
		}
		stream.Write(out)
	}
	all := stream.Bytes()
	var files [][]byte
	for _, n := range nodes {
		if n.offset < 0 || n.offset+n.size > int64(len(all)) {
			return nil, errors.New("a file lies outside the bundle")
		}
		files = append(files, all[n.offset:n.offset+n.size])
	}
	return files, nil
}

// serializedPlatform reads a serialized file's target platform: after its
// header (20 bytes, or 48 from format 22) comes the Unity version, then the
// platform, in the file's byte order.
func serializedPlatform(data []byte) (int, bool) {
	if len(data) < 20 {
		return 0, false
	}
	format := binary.BigEndian.Uint32(data[8:12])
	if format < 9 || format > 50 {
		return 0, false // a resource (.resS) file, not a serialized one
	}
	start := 20
	if format >= 22 {
		start = 48
	}
	if len(data) < start+1 {
		return 0, false
	}
	end := bytes.IndexByte(data[start:], 0)
	if end < 0 || start+end+5 > len(data) {
		return 0, false
	}
	raw := data[start+end+1 : start+end+5]
	if data[16] == 0 {
		return int(binary.LittleEndian.Uint32(raw)), true
	}
	return int(binary.BigEndian.Uint32(raw)), true
}
