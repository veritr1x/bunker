package unityasset

import (
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/pierrec/lz4/v4"
)

// MaskName is Octo's mask for a bundle: its path under assetbundle/, without
// the suffix, joined by ')'.
func MaskName(path string) string {
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

// Unmask reverses Octo's MaskedHeaderStream. Version 0x31 masks the first 256
// bytes of the file, the version byte included; 0x32 masks everything.
func Unmask(raw []byte, name string) ([]byte, error) {
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
	b     []byte
	p     int
	order binary.ByteOrder
	err   error
}

func (r *reader) need(n int) bool {
	if r.err == nil && (n < 0 || r.p+n > len(r.b)) {
		r.err = fmt.Errorf("read past the end (%d+%d of %d)", r.p, n, len(r.b))
	}
	return r.err == nil
}
func (r *reader) bytes(n int) []byte {
	if !r.need(n) {
		return nil
	}
	r.p += n
	return r.b[r.p-n : r.p]
}
func (r *reader) u8() uint8 {
	if b := r.bytes(1); b != nil {
		return b[0]
	}
	return 0
}
func (r *reader) u16() uint16 {
	if b := r.bytes(2); b != nil {
		return r.order.Uint16(b)
	}
	return 0
}
func (r *reader) u32() uint32 {
	if b := r.bytes(4); b != nil {
		return r.order.Uint32(b)
	}
	return 0
}
func (r *reader) u64() uint64 {
	if b := r.bytes(8); b != nil {
		return r.order.Uint64(b)
	}
	return 0
}
func (r *reader) cstring() string {
	if r.err != nil {
		return ""
	}
	i := bytes.IndexByte(r.b[r.p:], 0)
	if i < 0 {
		r.err = errors.New("unterminated string")
		return ""
	}
	s := string(r.b[r.p : r.p+i])
	r.p += i + 1
	return s
}
func (r *reader) align(n int) { r.p = (r.p + n - 1) / n * n }

// Bundle is an opened UnityFS archive: its files by name.
type Bundle struct{ Files map[string][]byte }

// OpenBundle reads, unmasks and decompresses one .assetbundle file.
func OpenBundle(path string) (*Bundle, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	data, err := Unmask(raw, MaskName(path))
	if err != nil {
		return nil, err
	}
	return ParseBundle(data)
}

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
	default:
		return nil, fmt.Errorf("unsupported bundle compression %d", flags&0x3f)
	}
}

// ParseBundle reads an unmasked UnityFS archive.
func ParseBundle(data []byte) (*Bundle, error) {
	r := &reader{b: data, order: binary.BigEndian}
	if sig := r.cstring(); sig != "UnityFS" {
		return nil, fmt.Errorf("not a UnityFS bundle (%q)", sig)
	}
	version := r.u32()
	r.cstring()
	r.cstring()
	r.u64() // file size
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
		info = r.bytes(compressedInfo)
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
	ir := &reader{b: info, order: binary.BigEndian}
	ir.bytes(16) // uncompressed data hash
	type blockInfo struct {
		u, c  int
		flags uint16
	}
	blocks := make([]blockInfo, ir.u32())
	for i := range blocks {
		blocks[i] = blockInfo{int(ir.u32()), int(ir.u32()), ir.u16()}
	}
	type node struct {
		offset, size int64
		name         string
	}
	nodes := make([]node, ir.u32())
	for i := range nodes {
		nodes[i].offset, nodes[i].size = int64(ir.u64()), int64(ir.u64())
		ir.u32() // flags
		nodes[i].name = ir.cstring()
	}
	if ir.err != nil {
		return nil, ir.err
	}
	var stream bytes.Buffer
	for _, b := range blocks {
		chunk := r.bytes(b.c)
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
	bundle := &Bundle{Files: map[string][]byte{}}
	for _, n := range nodes {
		if n.offset < 0 || n.offset+n.size > int64(len(all)) {
			return nil, fmt.Errorf("file %s lies outside the bundle", n.name)
		}
		bundle.Files[n.name] = all[n.offset : n.offset+n.size]
	}
	return bundle, nil
}
