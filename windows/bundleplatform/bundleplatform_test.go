package bundleplatform

import (
	"bytes"
	"encoding/binary"
	"testing"
)

// fakeBundle builds an unmasked, uncompressed UnityFS bundle holding one
// serialized file (format 21) built for platform.
func fakeBundle(platform uint32) []byte {
	var sf bytes.Buffer
	be := func(v uint32) { binary.Write(&sf, binary.BigEndian, v) }
	be(0)                        // metadata size
	be(0)                        // file size
	be(21)                       // format
	be(0)                        // data offset
	sf.Write([]byte{0, 0, 0, 0}) // little-endian, reserved
	sf.WriteString("2019.4.9f1\x00")
	binary.Write(&sf, binary.LittleEndian, platform)
	sf.Write(make([]byte, 32))

	var info bytes.Buffer
	info.Write(make([]byte, 16))
	binary.Write(&info, binary.BigEndian, uint32(1))
	binary.Write(&info, binary.BigEndian, uint32(sf.Len()))
	binary.Write(&info, binary.BigEndian, uint32(sf.Len()))
	binary.Write(&info, binary.BigEndian, uint16(0))
	binary.Write(&info, binary.BigEndian, uint32(1))
	binary.Write(&info, binary.BigEndian, uint64(0))
	binary.Write(&info, binary.BigEndian, uint64(sf.Len()))
	binary.Write(&info, binary.BigEndian, uint32(4))
	info.WriteString("CAB-test\x00")

	var b bytes.Buffer
	b.WriteString("UnityFS\x00")
	binary.Write(&b, binary.BigEndian, uint32(6))
	b.WriteString("5.x.x\x002019.4.9f1\x00")
	binary.Write(&b, binary.BigEndian, uint64(0))
	binary.Write(&b, binary.BigEndian, uint32(info.Len()))
	binary.Write(&b, binary.BigEndian, uint32(info.Len()))
	binary.Write(&b, binary.BigEndian, uint32(0))
	b.Write(info.Bytes())
	b.Write(sf.Bytes())
	return b.Bytes()
}

func TestOf(t *testing.T) {
	for _, want := range []int{Android, IOS} {
		got, err := Of(fakeBundle(uint32(want)), "x/revisions/0/assetbundle/ui/one.assetbundle")
		if err != nil || got != want {
			t.Fatalf("platform %d: got %d, %v", want, got, err)
		}
	}
	// Masked as the game stores bundles (0x31: the first 256 bytes).
	raw := fakeBundle(IOS)
	mask := maskBytes(maskName("assetbundle/ui/one.assetbundle"))
	for i := 1; i < min(256, len(raw)); i++ {
		raw[i] ^= mask[i%len(mask)]
	}
	raw[0] = 0x31
	if got, err := Of(raw, "assetbundle/ui/one.assetbundle"); err != nil || got != IOS {
		t.Fatalf("masked: got %d, %v", got, err)
	}
	if _, err := Of([]byte("not a bundle"), "assetbundle/x.assetbundle"); err == nil {
		t.Fatal("a broken bundle gave a platform")
	}
	if Name(Android) != "Android" || Name(IOS) != "iOS" {
		t.Fatal("Name")
	}
}
