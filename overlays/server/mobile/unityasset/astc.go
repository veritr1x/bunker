// Package unityasset reads the game's Unity asset bundles: Octo's header mask,
// UnityFS, serialized files and Texture2D, and decodes their ASTC textures.
//
// The ASTC decoder is a Go port of texture2ddecoder's astc.cpp
// (MIT License, Copyright (c) 2020 K0lb3), itself derived from Perfare's
// AssetStudio. See THIRD-PARTY-NOTICES.md beside this file.
package unityasset

import (
	"encoding/binary"
	"fmt"
	"math"
)

var bitReverseTable = func() (t [256]uint8) {
	for i := range t {
		v := uint8(i)
		var r uint8
		for b := 0; b < 8; b++ {
			r = r<<1 | v&1
			v >>= 1
		}
		t[i] = r
	}
	return
}()

var (
	weightPrecTableA = [16]int{0, 0, 0, 3, 0, 5, 3, 0, 0, 0, 5, 3, 0, 5, 3, 0}
	weightPrecTableB = [16]int{0, 0, 1, 0, 2, 0, 1, 3, 0, 0, 1, 2, 4, 2, 3, 5}
	cemTableA        = [19]int{0, 3, 5, 0, 3, 5, 0, 3, 5, 0, 3, 5, 0, 3, 5, 0, 3, 0, 0}
	cemTableB        = [19]int{8, 6, 5, 7, 5, 4, 6, 4, 3, 5, 3, 2, 4, 2, 1, 3, 1, 2, 1}
)

// block is one 16-byte ASTC block with padding, so the unaligned 32- and
// 64-bit reads of the reference decoder stay in bounds.
type block [24]byte

func bitReverseU8(c, bits int) int { return int(bitReverseTable[c&0xff]) >> (8 - bits) }

func bitReverseU64(d uint64, bits int) uint64 {
	var r uint64
	for i := 0; i < 8; i++ {
		r |= uint64(bitReverseTable[d>>(8*i)&0xff]) << (56 - 8*i)
	}
	return r >> (64 - bits)
}

func (b *block) getbits(bit, length int) int {
	v := int32(binary.LittleEndian.Uint32(b[bit/8:]))
	return int(v>>(bit%8)) & (1<<length - 1)
}

func (b *block) getbits64(bit, length int) uint64 {
	mask := uint64(math.MaxUint64)
	if length < 64 {
		mask = 1<<length - 1
	}
	lo, hi := binary.LittleEndian.Uint64(b[0:]), binary.LittleEndian.Uint64(b[8:])
	switch {
	case length < 1:
		return 0
	case bit >= 64:
		return hi >> (bit - 64) & mask
	case bit <= 0:
		return lo << -bit & mask
	case bit+length <= 64:
		return lo >> bit & mask
	default:
		return (lo>>bit | hi<<(64-bit)) & mask
	}
}

func (b *block) u16(i int) int { return int(binary.LittleEndian.Uint16(b[i:])) }

func clamp8(n int) int {
	if n < 0 {
		return 0
	}
	if n > 255 {
		return 255
	}
	return n
}

func clampHDR(n int) int {
	if n < 0 {
		return 0
	}
	if n > 0xfff {
		return 0xfff
	}
	return n
}

func bitTransferSigned(a, b *int) {
	*b = (*b >> 1) | (*a & 0x80)
	*a = (*a >> 1) & 0x3f
	if *a&0x20 != 0 {
		*a -= 0x40
	}
}

type endpoint [8]int

func (e *endpoint) set(v ...int) { copy(e[:], v) }

func (e *endpoint) setClamp(v ...int) {
	for i, x := range v {
		e[i] = clamp8(x)
	}
}

func (e *endpoint) setBlue(r1, g1, b1, a1, r2, g2, b2, a2 int) {
	e.set((r1+b1)>>1, (g1+b1)>>1, b1, a1, (r2+b2)>>1, (g2+b2)>>1, b2, a2)
}

func (e *endpoint) setBlueClamp(r1, g1, b1, a1, r2, g2, b2, a2 int) {
	e.setClamp((r1+b1)>>1, (g1+b1)>>1, b1, a1, (r2+b2)>>1, (g2+b2)>>1, b2, a2)
}

func (e *endpoint) setHDRClamp(v ...int) {
	for i, x := range v {
		e[i] = clampHDR(x)
	}
}

func selectColor(v0, v1, weight int) int {
	return ((((v0<<8|v0)*(64-weight)+(v1<<8|v1)*weight+32)>>6)*255 + 32768) / 65536
}

func fp16ToFloat(h uint16) float32 {
	sign := uint32(h>>15) << 31
	exp := int(h >> 10 & 0x1f)
	mant := uint32(h & 0x3ff)
	switch {
	case exp == 0:
		if mant == 0 {
			return math.Float32frombits(sign)
		}
		f := float32(mant) / 1024 / 16384
		if sign != 0 {
			return -f
		}
		return f
	case exp == 31:
		return math.Float32frombits(sign | 0x7f800000 | mant<<13)
	default:
		return math.Float32frombits(sign | uint32(exp-15+127)<<23 | mant<<13)
	}
}

func f32ToU8(f float32) int {
	c := math.Round(float64(f) * 255)
	if c < 0 {
		return 0
	}
	if c > 255 {
		return 255
	}
	return int(c)
}

func selectColorHDR(v0, v1, weight int) int {
	c := uint16(((v0<<4)*(64-weight) + (v1<<4)*weight + 32) >> 6)
	m := c & 0x7ff
	switch {
	case m < 512:
		m *= 3
	case m < 1536:
		m = 4*m - 512
	default:
		m = 5*m - 2048
	}
	f := fp16ToFloat((c >> 1 & 0x7c00) | m>>3)
	if math.IsInf(float64(f), 0) || math.IsNaN(float64(f)) {
		return 255
	}
	return clamp8(int(math.Round(float64(f) * 255)))
}

type blockData struct {
	bw, bh, width, height, partNum, dualPlane, planeSelector, weightRange, weightNum int
	cem                                                                              [4]int
	cemRange, endpointValueNum                                                       int
	endpoints                                                                        [4]endpoint
	weights                                                                          [144][2]int
	partition                                                                        [144]int
}

type intSeq struct{ bits, nonbits int }

var tritsTable = [5][256]int{
	{0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 1, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 1, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2, 0, 1, 2, 0, 0, 1, 2, 1, 0, 1, 2, 2, 0, 1, 2, 2},
	{0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 2, 2, 2, 0, 0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 2, 2, 2, 0, 0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 2, 2, 2, 1, 0, 0, 0, 0, 1, 1, 1, 0, 2, 2, 2, 0, 2, 2, 2, 0, 0, 0, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 2, 2, 2, 1},
	{0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 2, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 0, 0, 0, 2, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 2, 2},
	{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2},
	{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2},
}

var quintsTable = [3][128]int{
	{0, 1, 2, 3, 4, 0, 4, 4, 0, 1, 2, 3, 4, 1, 4, 4, 0, 1, 2, 3, 4, 2, 4, 4, 0, 1, 2, 3, 4, 3, 4, 4, 0, 1, 2, 3, 4, 0, 4, 0, 0, 1, 2, 3, 4, 1, 4, 1, 0, 1, 2, 3, 4, 2, 4, 2, 0, 1, 2, 3, 4, 3, 4, 3, 0, 1, 2, 3, 4, 0, 2, 3, 0, 1, 2, 3, 4, 1, 2, 3, 0, 1, 2, 3, 4, 2, 2, 3, 0, 1, 2, 3, 4, 3, 2, 3, 0, 1, 2, 3, 4, 0, 0, 1, 0, 1, 2, 3, 4, 1, 0, 1, 0, 1, 2, 3, 4, 2, 0, 1, 0, 1, 2, 3, 4, 3, 0, 1},
	{0, 0, 0, 0, 0, 4, 4, 4, 1, 1, 1, 1, 1, 4, 4, 4, 2, 2, 2, 2, 2, 4, 4, 4, 3, 3, 3, 3, 3, 4, 4, 4, 0, 0, 0, 0, 0, 4, 0, 4, 1, 1, 1, 1, 1, 4, 1, 4, 2, 2, 2, 2, 2, 4, 2, 4, 3, 3, 3, 3, 3, 4, 3, 4, 0, 0, 0, 0, 0, 4, 0, 0, 1, 1, 1, 1, 1, 4, 1, 1, 2, 2, 2, 2, 2, 4, 2, 2, 3, 3, 3, 3, 3, 4, 3, 3, 0, 0, 0, 0, 0, 4, 0, 0, 1, 1, 1, 1, 1, 4, 1, 1, 2, 2, 2, 2, 2, 4, 2, 2, 3, 3, 3, 3, 3, 4, 3, 3},
	{0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 1, 4, 0, 0, 0, 0, 0, 0, 2, 4, 0, 0, 0, 0, 0, 0, 3, 4, 1, 1, 1, 1, 1, 1, 4, 4, 1, 1, 1, 1, 1, 1, 4, 4, 1, 1, 1, 1, 1, 1, 4, 4, 1, 1, 1, 1, 1, 1, 4, 4, 2, 2, 2, 2, 2, 2, 4, 4, 2, 2, 2, 2, 2, 2, 4, 4, 2, 2, 2, 2, 2, 2, 4, 4, 2, 2, 2, 2, 2, 2, 4, 4, 3, 3, 3, 3, 3, 3, 4, 4, 3, 3, 3, 3, 3, 3, 4, 4, 3, 3, 3, 3, 3, 3, 4, 4, 3, 3, 3, 3, 3, 3, 4, 4},
}

// decodeIntSeq reads count integers of the bounded integer sequence encoding (trits, quints or plain bits).
func (buf *block) decodeIntSeq(offset, a, b, count int, reverse bool, out []intSeq) {
	mt := [5]int{0, 2, 4, 5, 7}
	mq := [3]int{0, 3, 5}
	if count <= 0 {
		return
	}
	n := 0
	mask := uint64(1)<<b - 1
	switch a {
	case 3:
		blockCount := (count + 4) / 5
		lastBlockCount := (count+4)%5 + 1
		blockSize := 8 + 5*b
		lastBlockSize := (blockSize*lastBlockCount + 4) / 5
		for i, p := 0, offset; i < blockCount; i++ {
			size := blockSize
			if i == blockCount-1 {
				size = lastBlockSize
			}
			var d uint64
			if reverse {
				d = bitReverseU64(buf.getbits64(p-size, size), size)
				p -= blockSize
			} else {
				d = buf.getbits64(p, size)
				p += blockSize
			}
			bb := uint(b)
			x := int(d>>bb&3 | d>>(bb*2)&0xc | d>>(bb*3)&0x10 | d>>(bb*4)&0x60 | d>>(bb*5)&0x80)
			for j := 0; j < 5 && n < count; j, n = j+1, n+1 {
				out[n] = intSeq{int(d >> (uint(mt[j]) + bb*uint(j)) & mask), tritsTable[j][x]}
			}
		}
	case 5:
		blockCount := (count + 2) / 3
		lastBlockCount := (count+2)%3 + 1
		blockSize := 7 + 3*b
		lastBlockSize := (blockSize*lastBlockCount + 2) / 3
		for i, p := 0, offset; i < blockCount; i++ {
			size := blockSize
			if i == blockCount-1 {
				size = lastBlockSize
			}
			var d uint64
			if reverse {
				d = bitReverseU64(buf.getbits64(p-size, size), size)
				p -= blockSize
			} else {
				d = buf.getbits64(p, size)
				p += blockSize
			}
			bb := uint(b)
			x := int(d>>bb&7 | d>>(bb*2)&0x18 | d>>(bb*3)&0x60)
			for j := 0; j < 3 && n < count; j, n = j+1, n+1 {
				out[n] = intSeq{int(d >> (uint(mq[j]) + bb*uint(j)) & mask), quintsTable[j][x]}
			}
		}
	default:
		if reverse {
			for p := offset - b; n < count; n, p = n+1, p-b {
				out[n] = intSeq{bitReverseU8(buf.getbits(p, b), b), 0}
			}
		} else {
			for p := offset; n < count; n, p = n+1, p+b {
				out[n] = intSeq{buf.getbits(p, b), 0}
			}
		}
	}
}

func (buf *block) decodeParams(d *blockData) {
	if buf[1]&4 != 0 {
		d.dualPlane = 1
	}
	d.weightRange = int(buf[0]>>4&1) | int(buf[1]<<2&8)
	if buf[0]&3 != 0 {
		d.weightRange |= int(buf[0] << 1 & 6)
		switch buf[0] & 0xc {
		case 0:
			d.width, d.height = (buf.u16(0)>>7&3)+4, int(buf[0]>>5&3)+2
		case 4:
			d.width, d.height = (buf.u16(0)>>7&3)+8, int(buf[0]>>5&3)+2
		case 8:
			d.width, d.height = int(buf[0]>>5&3)+2, (buf.u16(0)>>7&3)+8
		case 12:
			if buf[1]&1 != 0 {
				d.width, d.height = int(buf[0]>>7&1)+2, int(buf[0]>>5&3)+2
			} else {
				d.width, d.height = int(buf[0]>>5&3)+2, int(buf[0]>>7&1)+6
			}
		}
	} else {
		d.weightRange |= int(buf[0] >> 1 & 6)
		switch buf.u16(0) & 0x180 {
		case 0:
			d.width, d.height = 12, int(buf[0]>>5&3)+2
		case 0x80:
			d.width, d.height = int(buf[0]>>5&3)+2, 12
		case 0x100:
			d.width, d.height = int(buf[0]>>5&3)+6, int(buf[1]>>1&3)+6
			d.dualPlane = 0
			d.weightRange &= 7
		case 0x180:
			if buf[0]&0x20 != 0 {
				d.width, d.height = 10, 6
			} else {
				d.width, d.height = 6, 10
			}
		}
	}
	d.partNum = int(buf[1]>>3&3) + 1
	d.weightNum = d.width * d.height
	if d.dualPlane != 0 {
		d.weightNum *= 2
	}
	var weightBits, configBits, cemBase int
	switch weightPrecTableA[d.weightRange] {
	case 3:
		weightBits = d.weightNum*weightPrecTableB[d.weightRange] + (d.weightNum*8+4)/5
	case 5:
		weightBits = d.weightNum*weightPrecTableB[d.weightRange] + (d.weightNum*7+2)/3
	default:
		weightBits = d.weightNum * weightPrecTableB[d.weightRange]
	}
	if d.partNum == 1 {
		d.cem[0] = buf.u16(1) >> 5 & 0xf
		configBits = 17
	} else {
		cemBase = buf.u16(2) >> 7 & 3
		if cemBase == 0 {
			cem := int(buf[3] >> 1 & 0xf)
			for i := 0; i < d.partNum; i++ {
				d.cem[i] = cem
			}
			configBits = 29
		} else {
			for i := 0; i < d.partNum; i++ {
				d.cem[i] = (int(buf[3]>>(i+1)&1) + cemBase - 1) << 2
			}
			switch d.partNum {
			case 2:
				d.cem[0] |= int(buf[3] >> 3 & 3)
				d.cem[1] |= buf.getbits(126-weightBits, 2)
			case 3:
				d.cem[0] |= int(buf[3] >> 4 & 1)
				d.cem[0] |= buf.getbits(122-weightBits, 2) & 2
				d.cem[1] |= buf.getbits(124-weightBits, 2)
				d.cem[2] |= buf.getbits(126-weightBits, 2)
			case 4:
				for i := 0; i < 4; i++ {
					d.cem[i] |= buf.getbits(120+i*2-weightBits, 2)
				}
			}
			configBits = 25 + d.partNum*3
		}
	}
	if d.dualPlane != 0 {
		configBits += 2
		if cemBase != 0 {
			d.planeSelector = buf.getbits(130-weightBits-d.partNum*3, 2)
		} else {
			d.planeSelector = buf.getbits(126-weightBits, 2)
		}
	}
	remainBits := 128 - configBits - weightBits
	d.endpointValueNum = 0
	for i := 0; i < d.partNum; i++ {
		d.endpointValueNum += (d.cem[i] >> 1 & 6) + 2
	}
	for i := range cemTableA {
		var endpointBits int
		switch cemTableA[i] {
		case 3:
			endpointBits = d.endpointValueNum*cemTableB[i] + (d.endpointValueNum*8+4)/5
		case 5:
			endpointBits = d.endpointValueNum*cemTableB[i] + (d.endpointValueNum*7+2)/3
		default:
			endpointBits = d.endpointValueNum * cemTableB[i]
		}
		if endpointBits <= remainBits {
			d.cemRange = i
			break
		}
	}
}

func decodeEndpointsHDR7(e *endpoint, v []int) {
	modeval := (v[2] >> 4 & 0x8) | (v[1] >> 5 & 0x4) | (v[0] >> 6)
	var major, mode int
	switch {
	case modeval&0xc != 0xc:
		major, mode = modeval>>2, modeval&3
	case modeval != 0xf:
		major, mode = modeval&3, 4
	default:
		major, mode = 0, 5
	}
	c := [4]int{v[0] & 0x3f, v[1] & 0x1f, v[2] & 0x1f, v[3] & 0x1f}
	shift := 0
	switch mode {
	case 0:
		c[3] |= v[3] & 0x60
		c[0] |= v[3]>>1&0x40 | v[2]<<1&0x80 | v[1]<<3&0x300 | v[2]<<5&0x400
		shift = 1
	case 1:
		c[1] |= v[1] & 0x20
		c[2] |= v[2] & 0x20
		c[0] |= v[3]>>1&0x40 | v[2]<<1&0x80 | v[1]<<2&0x100 | v[3]<<4&0x600
		shift = 1
	case 2:
		c[3] |= v[3] & 0xe0
		c[0] |= v[2]<<1&0xc0 | v[1]<<3&0x300
		shift = 2
	case 3:
		c[1] |= v[1] & 0x20
		c[2] |= v[2] & 0x20
		c[3] |= v[3] & 0x60
		c[0] |= v[3]>>1&0x40 | v[2]<<1&0x80 | v[1]<<2&0x100
		shift = 3
	case 4:
		c[1] |= v[1] & 0x60
		c[2] |= v[2] & 0x60
		c[3] |= v[3] & 0x20
		c[0] |= v[3]>>1&0x40 | v[3]<<1&0x80
		shift = 4
	case 5:
		c[1] |= v[1] & 0x60
		c[2] |= v[2] & 0x60
		c[3] |= v[3] & 0x60
		c[0] |= v[3] >> 1 & 0x40
		shift = 5
	}
	for i := range c {
		c[i] <<= shift
	}
	if mode != 5 {
		c[1] = c[0] - c[1]
		c[2] = c[0] - c[2]
	}
	switch major {
	case 1:
		e.setHDRClamp(c[1]-c[3], c[0]-c[3], c[2]-c[3], 0x780, c[1], c[0], c[2], 0x780)
	case 2:
		e.setHDRClamp(c[2]-c[3], c[1]-c[3], c[0]-c[3], 0x780, c[2], c[1], c[0], 0x780)
	default:
		e.setHDRClamp(c[0]-c[3], c[1]-c[3], c[2]-c[3], 0x780, c[0], c[1], c[2], 0x780)
	}
}

func signExtend(v, bits int) int {
	if v&(1<<(bits-1)) != 0 {
		return v - 1<<bits
	}
	return v
}

func decodeEndpointsHDR11(e *endpoint, v []int, alpha1, alpha2 int) {
	major := (v[4] >> 7) | (v[5] >> 6 & 2)
	if major == 3 {
		e.set(v[0]<<4, v[2]<<4, v[4]<<5&0xfe0, alpha1, v[1]<<4, v[3]<<4, v[5]<<5&0xfe0, alpha2)
		return
	}
	mode := (v[1] >> 7) | (v[2] >> 6 & 2) | (v[3] >> 5 & 4)
	va := v[0] | (v[1] << 2 & 0x100)
	vb0, vb1 := v[2]&0x3f, v[3]&0x3f
	vc := v[1] & 0x3f
	var vd0, vd1 int
	switch mode {
	case 0, 2:
		vd0, vd1 = signExtend(v[4]&0x7f, 7), signExtend(v[5]&0x7f, 7)
	case 1, 3, 5, 7:
		vd0, vd1 = signExtend(v[4]&0x3f, 6), signExtend(v[5]&0x3f, 6)
	default:
		vd0, vd1 = signExtend(v[4]&0x1f, 5), signExtend(v[5]&0x1f, 5)
	}
	switch mode {
	case 0:
		vb0 |= v[2] & 0x40
		vb1 |= v[3] & 0x40
	case 1:
		vb0 |= v[2]&0x40 | v[4]<<1&0x80
		vb1 |= v[3]&0x40 | v[5]<<1&0x80
	case 2:
		va |= v[2] << 3 & 0x200
		vc |= v[3] & 0x40
	case 3:
		va |= v[4] << 3 & 0x200
		vc |= v[5] & 0x40
		vb0 |= v[2] & 0x40
		vb1 |= v[3] & 0x40
	case 4:
		va |= v[4]<<4&0x200 | v[5]<<5&0x400
		vb0 |= v[2]&0x40 | v[4]<<1&0x80
		vb1 |= v[3]&0x40 | v[5]<<1&0x80
	case 5:
		va |= v[2]<<3&0x200 | v[3]<<4&0x400
		vc |= v[5]&0x40 | v[4]<<1&0x80
	case 6:
		va |= v[4]<<4&0x200 | v[5]<<5&0x400 | v[4]<<5&0x800
		vc |= v[5] & 0x40
		vb0 |= v[2] & 0x40
		vb1 |= v[3] & 0x40
	case 7:
		va |= v[2]<<3&0x200 | v[3]<<4&0x400 | v[4]<<5&0x800
		vc |= v[5] & 0x40
	}
	shamt := (mode >> 1) ^ 3
	va <<= shamt
	vb0 <<= shamt
	vb1 <<= shamt
	vc <<= shamt
	// The reference keeps vd in int16, so the scaled differences wrap at 16 bits.
	vd0 = int(int16(vd0 * (1 << shamt)))
	vd1 = int(int16(vd1 * (1 << shamt)))
	switch major {
	case 1:
		e.setHDRClamp(va-vb0-vc-vd0, va-vc, va-vb1-vc-vd1, alpha1, va-vb0, va, va-vb1, alpha2)
	case 2:
		e.setHDRClamp(va-vb1-vc-vd1, va-vb0-vc-vd0, va-vc, alpha1, va-vb1, va-vb0, va, alpha2)
	default:
		e.setHDRClamp(va-vc, va-vb0-vc-vd0, va-vb1-vc-vd1, alpha1, va, va-vb0, va-vb1, alpha2)
	}
}

func (buf *block) decodeEndpoints(d *blockData) {
	tritsScale := [7]int{0, 204, 93, 44, 22, 11, 5}
	quintsScale := [6]int{0, 113, 54, 26, 13, 6}
	var seq [32]intSeq
	var ev [32]int
	offset := 29
	if d.partNum == 1 {
		offset = 17
	}
	a, b := cemTableA[d.cemRange], cemTableB[d.cemRange]
	buf.decodeIntSeq(offset, a, b, d.endpointValueNum, false, seq[:])
	switch a {
	case 3:
		c := tritsScale[b]
		for i := 0; i < d.endpointValueNum; i++ {
			sa := (seq[i].bits & 1) * 0x1ff
			x := seq[i].bits >> 1
			var sb int
			switch b {
			case 2:
				sb = 0b100010110 * x
			case 3:
				sb = x<<7 | x<<2 | x
			case 4:
				sb = x<<6 | x
			case 5:
				sb = x<<5 | x>>2
			case 6:
				sb = x<<4 | x>>4
			}
			ev[i] = (sa & 0x80) | ((seq[i].nonbits*c+sb)^sa)>>2
		}
	case 5:
		c := quintsScale[b]
		for i := 0; i < d.endpointValueNum; i++ {
			sa := (seq[i].bits & 1) * 0x1ff
			x := seq[i].bits >> 1
			var sb int
			switch b {
			case 2:
				sb = 0b100001100 * x
			case 3:
				sb = x<<7 | x<<1 | x>>1
			case 4:
				sb = x<<6 | x>>1
			case 5:
				sb = x<<5 | x>>3
			}
			ev[i] = (sa & 0x80) | ((seq[i].nonbits*c+sb)^sa)>>2
		}
	default:
		for i := 0; i < d.endpointValueNum; i++ {
			s := seq[i].bits
			switch b {
			case 1:
				ev[i] = s * 0xff
			case 2:
				ev[i] = s * 0x55
			case 3:
				ev[i] = s<<5 | s<<2 | s>>1
			case 4:
				ev[i] = s<<4 | s
			case 5:
				ev[i] = s<<3 | s>>2
			case 6:
				ev[i] = s<<2 | s>>4
			case 7:
				ev[i] = s<<1 | s>>6
			case 8:
				ev[i] = s
			}
		}
	}
	v := ev[:]
	for cem := 0; cem < d.partNum; cem++ {
		e := &d.endpoints[cem]
		switch d.cem[cem] {
		case 0:
			e.set(v[0], v[0], v[0], 255, v[1], v[1], v[1], 255)
		case 1:
			l0 := (v[0] >> 2) | (v[1] & 0xc0)
			l1 := clamp8(l0 + (v[1] & 0x3f))
			e.set(l0, l0, l0, 255, l1, l1, l1, 255)
		case 2:
			var y0, y1 int
			if v[0] <= v[1] {
				y0, y1 = v[0]<<4, v[1]<<4
			} else {
				y0, y1 = (v[1]<<4)+8, (v[0]<<4)-8
			}
			e.set(y0, y0, y0, 0x780, y1, y1, y1, 0x780)
		case 3:
			var y0, dd int
			if v[0]&0x80 != 0 {
				y0, dd = (v[1]&0xe0)<<4|(v[0]&0x7f)<<2, (v[1]&0x1f)<<2
			} else {
				y0, dd = (v[1]&0xf0)<<4|(v[0]&0x7f)<<1, (v[1]&0x0f)<<1
			}
			y1 := clampHDR(y0 + dd)
			e.set(y0, y0, y0, 0x780, y1, y1, y1, 0x780)
		case 4:
			e.set(v[0], v[0], v[0], v[2], v[1], v[1], v[1], v[3])
		case 5:
			bitTransferSigned(&v[1], &v[0])
			bitTransferSigned(&v[3], &v[2])
			v[1] += v[0]
			e.setClamp(v[0], v[0], v[0], v[2], v[1], v[1], v[1], v[2]+v[3])
		case 6:
			e.set(v[0]*v[3]>>8, v[1]*v[3]>>8, v[2]*v[3]>>8, 255, v[0], v[1], v[2], 255)
		case 7:
			decodeEndpointsHDR7(e, v)
		case 8:
			if v[0]+v[2]+v[4] <= v[1]+v[3]+v[5] {
				e.set(v[0], v[2], v[4], 255, v[1], v[3], v[5], 255)
			} else {
				e.setBlue(v[1], v[3], v[5], 255, v[0], v[2], v[4], 255)
			}
		case 9:
			bitTransferSigned(&v[1], &v[0])
			bitTransferSigned(&v[3], &v[2])
			bitTransferSigned(&v[5], &v[4])
			if v[1]+v[3]+v[5] >= 0 {
				e.setClamp(v[0], v[2], v[4], 255, v[0]+v[1], v[2]+v[3], v[4]+v[5], 255)
			} else {
				e.setBlueClamp(v[0]+v[1], v[2]+v[3], v[4]+v[5], 255, v[0], v[2], v[4], 255)
			}
		case 10:
			e.set(v[0]*v[3]>>8, v[1]*v[3]>>8, v[2]*v[3]>>8, v[4], v[0], v[1], v[2], v[5])
		case 11:
			decodeEndpointsHDR11(e, v, 0x780, 0x780)
		case 12:
			if v[0]+v[2]+v[4] <= v[1]+v[3]+v[5] {
				e.set(v[0], v[2], v[4], v[6], v[1], v[3], v[5], v[7])
			} else {
				e.setBlue(v[1], v[3], v[5], v[7], v[0], v[2], v[4], v[6])
			}
		case 13:
			bitTransferSigned(&v[1], &v[0])
			bitTransferSigned(&v[3], &v[2])
			bitTransferSigned(&v[5], &v[4])
			bitTransferSigned(&v[7], &v[6])
			if v[1]+v[3]+v[5] >= 0 {
				e.setClamp(v[0], v[2], v[4], v[6], v[0]+v[1], v[2]+v[3], v[4]+v[5], v[6]+v[7])
			} else {
				e.setBlueClamp(v[0]+v[1], v[2]+v[3], v[4]+v[5], v[6]+v[7], v[0], v[2], v[4], v[6])
			}
		case 14:
			decodeEndpointsHDR11(e, v, v[6], v[7])
		case 15:
			mode := (v[6] >> 7 & 1) | (v[7] >> 6 & 2)
			v[6] &= 0x7f
			v[7] &= 0x7f
			if mode == 3 {
				decodeEndpointsHDR11(e, v, v[6]<<5, v[7]<<5)
			} else {
				v[6] |= (v[7] << (mode + 1)) & 0x780
				v[7] = ((v[7] & (0x3f >> mode)) ^ (0x20 >> mode)) - (0x20 >> mode)
				v[6] <<= 4 - mode
				v[7] <<= 4 - mode
				decodeEndpointsHDR11(e, v, v[6], clampHDR(v[6]+v[7]))
			}
		}
		v = v[(d.cem[cem]/4+1)*2:]
	}
}

func (buf *block) decodeWeights(d *blockData) {
	var seq [128]intSeq
	var wv [128]int
	a, b := weightPrecTableA[d.weightRange], weightPrecTableB[d.weightRange]
	buf.decodeIntSeq(128, a, b, d.weightNum, true, seq[:])
	switch {
	case a == 0:
		for i := 0; i < d.weightNum; i++ {
			s := seq[i].bits
			switch b {
			case 1:
				if s != 0 {
					wv[i] = 63
				}
			case 2:
				wv[i] = s<<4 | s<<2 | s
			case 3:
				wv[i] = s<<3 | s
			case 4:
				wv[i] = s<<2 | s>>2
			case 5:
				wv[i] = s<<1 | s>>4
			}
			if wv[i] > 32 {
				wv[i]++
			}
		}
	case b == 0:
		s := 16
		if a == 3 {
			s = 32
		}
		for i := 0; i < d.weightNum; i++ {
			wv[i] = seq[i].nonbits * s
		}
	default:
		for i := 0; i < d.weightNum; i++ {
			switch {
			case a == 3 && b == 1:
				wv[i] = seq[i].nonbits * 50
			case a == 3 && b == 2:
				wv[i] = seq[i].nonbits * 23
				if seq[i].bits&2 != 0 {
					wv[i] += 0b1000101
				}
			case a == 3 && b == 3:
				wv[i] = seq[i].nonbits*11 + ((seq[i].bits<<4 | seq[i].bits>>1) & 0b1100011)
			case a == 5 && b == 1:
				wv[i] = seq[i].nonbits * 28
			case a == 5 && b == 2:
				wv[i] = seq[i].nonbits * 13
				if seq[i].bits&2 != 0 {
					wv[i] += 0b1000010
				}
			}
			sa := (seq[i].bits & 1) * 0x7f
			wv[i] = (sa & 0x20) | ((wv[i] ^ sa) >> 2)
			if wv[i] > 32 {
				wv[i]++
			}
		}
	}
	ds := (1024 + d.bw/2) / (d.bw - 1)
	dt := (1024 + d.bh/2) / (d.bh - 1)
	pn := 1
	if d.dualPlane != 0 {
		pn = 2
	}
	for t, i := 0, 0; t < d.bh; t++ {
		for s := 0; s < d.bw; s, i = s+1, i+1 {
			gs := (ds*s*(d.width-1) + 32) >> 6
			gt := (dt*t*(d.height-1) + 32) >> 6
			fs, ft := gs&0xf, gt&0xf
			v := (gs >> 4) + (gt>>4)*d.width
			w11 := (fs*ft + 8) >> 4
			w10 := ft - w11
			w01 := fs - w11
			w00 := 16 - fs - ft + w11
			for p := 0; p < pn; p++ {
				at := func(k int) int {
					if k < 0 || k >= len(wv) {
						return 0
					}
					return wv[k]
				}
				p00 := at(v*pn + p)
				p01 := at((v+1)*pn + p)
				p10 := at((v+d.width)*pn + p)
				p11 := at((v+d.width+1)*pn + p)
				d.weights[i][p] = (p00*w00 + p01*w01 + p10*w10 + p11*w11 + 8) >> 4
			}
		}
	}
}

func (buf *block) selectPartition(d *blockData) {
	small := d.bw*d.bh < 31
	seed := int(int32(binary.LittleEndian.Uint32(buf[0:]))>>13&0x3ff) | (d.partNum-1)<<10
	rnum := uint32(seed)
	rnum ^= rnum >> 15
	rnum -= rnum << 17
	rnum += rnum << 7
	rnum += rnum << 4
	rnum ^= rnum >> 5
	rnum += rnum << 16
	rnum ^= rnum >> 7
	rnum ^= rnum >> 3
	rnum ^= rnum << 6
	rnum ^= rnum >> 17
	var seeds [8]int
	for i := range seeds {
		seeds[i] = int(rnum >> (i * 4) & 0xf)
		seeds[i] *= seeds[i]
	}
	sh := [2]int{5, 5}
	if seed&2 != 0 {
		sh[0] = 4
	}
	if d.partNum == 3 {
		sh[1] = 6
	}
	for i := range seeds {
		if seed&1 != 0 {
			seeds[i] >>= sh[i%2]
		} else {
			seeds[i] >>= sh[1-i%2]
		}
	}
	r := int(rnum)
	for t, i := 0, 0; t < d.bh; t++ {
		for s := 0; s < d.bw; s, i = s+1, i+1 {
			x, y := s, t
			if small {
				x, y = s<<1, t<<1
			}
			a := (seeds[0]*x + seeds[1]*y + (r >> 14)) & 0x3f
			b := (seeds[2]*x + seeds[3]*y + (r >> 10)) & 0x3f
			c, dd := 0, 0
			if d.partNum >= 3 {
				c = (seeds[4]*x + seeds[5]*y + (r >> 6)) & 0x3f
			}
			if d.partNum >= 4 {
				dd = (seeds[6]*x + seeds[7]*y + (r >> 2)) & 0x3f
			}
			switch {
			case a >= b && a >= c && a >= dd:
				d.partition[i] = 0
			case b >= c && b >= dd:
				d.partition[i] = 1
			case c >= dd:
				d.partition[i] = 2
			default:
				d.partition[i] = 3
			}
		}
	}
}

var hdrColor = [16]bool{2: true, 3: true, 7: true, 11: true, 14: true, 15: true}
var hdrAlpha = [16]bool{2: true, 3: true, 7: true, 11: true, 15: true}

func pick(hdr bool, v0, v1, w int) int {
	if hdr {
		return selectColorHDR(v0, v1, w)
	}
	return selectColor(v0, v1, w)
}

// applyColor writes the block's texels as RGBA into out (bw*bh*4 bytes).
func (d *blockData) applyColor(out []byte) {
	planes := [4]int{}
	if d.dualPlane != 0 {
		planes[d.planeSelector] = 1
	}
	for i := 0; i < d.bw*d.bh; i++ {
		p := 0
		if d.partNum > 1 {
			p = d.partition[i]
		}
		e, cem := &d.endpoints[p], d.cem[p]
		out[i*4+0] = byte(pick(hdrColor[cem], e[0], e[4], d.weights[i][planes[0]]))
		out[i*4+1] = byte(pick(hdrColor[cem], e[1], e[5], d.weights[i][planes[1]]))
		out[i*4+2] = byte(pick(hdrColor[cem], e[2], e[6], d.weights[i][planes[2]]))
		out[i*4+3] = byte(pick(hdrAlpha[cem], e[3], e[7], d.weights[i][planes[3]]))
	}
}

func decodeBlock(src []byte, bw, bh int, out []byte) {
	var buf block
	copy(buf[:], src[:16])
	fill := func(r, g, b, a byte) {
		for i := 0; i < bw*bh; i++ {
			out[i*4], out[i*4+1], out[i*4+2], out[i*4+3] = r, g, b, a
		}
	}
	switch {
	case buf[0] == 0xfc && buf[1]&1 == 1: // void-extent: one colour
		if buf[1]&2 != 0 {
			h := func(i int) byte { return byte(f32ToU8(fp16ToFloat(uint16(buf.u16(i))))) }
			fill(h(8), h(10), h(12), h(14))
		} else {
			fill(buf[9], buf[11], buf[13], buf[15])
		}
	case (buf[0]&0xc3 == 0xc0 && buf[1]&1 == 1) || buf[0]&0xf == 0: // reserved: the error colour
		fill(255, 0, 255, 255)
	default:
		d := blockData{bw: bw, bh: bh}
		buf.decodeParams(&d)
		buf.decodeEndpoints(&d)
		buf.decodeWeights(&d)
		if d.partNum > 1 {
			buf.selectPartition(&d)
		}
		d.applyColor(out)
	}
}

// DecodeASTC decodes an LDR or HDR ASTC image with bw×bh blocks into RGBA rows, top row first
// in the data's own order.
func DecodeASTC(data []byte, width, height, bw, bh int) ([]byte, error) {
	bx, by := (width+bw-1)/bw, (height+bh-1)/bh
	if len(data) < bx*by*16 {
		return nil, fmt.Errorf("ASTC data is %d bytes; %dx%d at %dx%d needs %d", len(data), width, height, bw, bh, bx*by*16)
	}
	img := make([]byte, width*height*4)
	texels := make([]byte, bw*bh*4)
	for y := 0; y < by; y++ {
		for x := 0; x < bx; x++ {
			decodeBlock(data[(y*bx+x)*16:], bw, bh, texels)
			for t := 0; t < bh && y*bh+t < height; t++ {
				n := bw
				if x*bw+n > width {
					n = width - x*bw
				}
				copy(img[((y*bh+t)*width+x*bw)*4:], texels[t*bw*4:(t*bw+n)*4])
			}
		}
	}
	return img, nil
}
