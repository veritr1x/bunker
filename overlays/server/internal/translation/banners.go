package translation

import (
	"bytes"
	"crypto/md5"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"hash/crc32"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"lunar-tear/server/mobile/unityasset"
)

// Banner 900 is Record: Garden of Benediction's first run (August 2021). The
// live game redrew that run's banner, 512, for the January 2022 rerun
// ("Resurrected"), so no game file has the 2021 one. The Original calendar
// shows banner 900 for that run (event_banners.json); its bundles are built
// here from the player's own files, as the game names them:
//
//   - ui)quest)<lang>)banner)event_banner_900, the event screen: banner 512's
//     bundle with the recreated image from the notice pack
//     (banners/<lang>/event_banner_900.astc, scripts/recreate_banners.py);
//     Japanese 512 was never redrawn and keeps its own image.
//   - ui)quest)<lang>)mom_banner)event_mom_banner_900, the strip: banner
//     512's with the home screen's 2021 strip, which was never redrawn
//     (ui)mom_banner)<lang>)mom_banner_event_mom_banner_512).
//
// A bundle is renamed in place (names of the same length: the bundle's file
// layout stays) and given the new pixels (the same size and format), so no
// field of the texture changes. The game finds the bundles through entries
// added to the list it is served.
const bannerVersion = "1"

var bannerLanguages = []string{"en", "ja", "ko"}

type bannerSpec struct {
	Path, Template string // list paths
	Old, New       string // the name the template bundle uses for itself, and its replacement
	PackImage      string // the image from the notice pack, if any
	FromBundle     string // else the image of this bundle (a list path), if any
}

func bannerSpecs() []bannerSpec {
	var specs []bannerSpec
	for _, lang := range bannerLanguages {
		specs = append(specs, bannerSpec{
			Path: "ui)quest)" + lang + ")banner)event_banner_900", Template: "ui)quest)" + lang + ")banner)event_banner_512",
			Old: "event_banner_512", New: "event_banner_900", PackImage: "banners/" + lang + "/event_banner_900.astc",
		}, bannerSpec{
			Path: "ui)quest)" + lang + ")mom_banner)event_mom_banner_900", Template: "ui)quest)" + lang + ")mom_banner)event_mom_banner_512",
			Old: "event_mom_banner_512", New: "event_mom_banner_900", FromBundle: "ui)mom_banner)" + lang + ")mom_banner_event_mom_banner_512",
		})
	}
	return specs
}

type node struct {
	flags uint32
	name  string
	data  []byte
}

// nodeBundle is a UnityFS bundle with its files read out.
type nodeBundle struct {
	version                     uint32
	unityVersion, unityRevision string
	flags                       uint32
	hash                        []byte
	nodes                       []node
}

// readNodes reads every file of an unmasked UnityFS bundle.
func readNodes(plain []byte) (*nodeBundle, error) {
	be := binary.BigEndian
	r := &byteReader{b: plain}
	if r.cstring() != "UnityFS" {
		return nil, errors.New("not a UnityFS bundle")
	}
	b := &nodeBundle{version: r.u32(be), unityVersion: r.cstring(), unityRevision: r.cstring()}
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
		return nil, fmt.Errorf("bundle of %d bytes is out of range", total)
	}
	count := ir.count(be, 21)
	type place struct{ offset, size uint64 }
	places := make([]place, count)
	b.nodes = make([]node, count)
	for i := range b.nodes {
		places[i] = place{ir.u64(be), ir.u64(be)}
		b.nodes[i].flags = ir.u32(be)
		b.nodes[i].name = ir.cstring()
	}
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
	for i, p := range places {
		if p.offset > uint64(len(data)) || p.size > uint64(len(data))-p.offset {
			return nil, fmt.Errorf("file %s at %d+%d is past the bundle's %d bytes", b.nodes[i].name, p.offset, p.size, len(data))
		}
		b.nodes[i].data = data[p.offset : p.offset+p.size]
	}
	return b, nil
}

// writeNodes writes a bundle with its files in one LZ4HC block, in order.
func writeNodes(b *nodeBundle) ([]byte, error) {
	be := binary.BigEndian
	var data []byte
	for _, n := range b.nodes {
		data = append(data, n.data...)
	}
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
	binary.Write(&info, be, uint32(len(b.nodes)))
	offset := uint64(0)
	for _, n := range b.nodes {
		binary.Write(&info, be, offset)
		binary.Write(&info, be, uint64(len(n.data)))
		binary.Write(&info, be, n.flags)
		info.WriteString(n.name)
		info.WriteByte(0)
		offset += uint64(len(n.data))
	}
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

// resSOf is the texture data file of a banner bundle (its .resS) and the serialized file.
func bannerFiles(b *nodeBundle) (serialized, resS *node, err error) {
	for i := range b.nodes {
		if strings.HasSuffix(b.nodes[i].name, ".resS") {
			resS = &b.nodes[i]
		} else {
			serialized = &b.nodes[i]
		}
	}
	if len(b.nodes) != 2 || serialized == nil || resS == nil {
		return nil, nil, fmt.Errorf("bundle has %d files, want a serialized file and its .resS", len(b.nodes))
	}
	return serialized, resS, nil
}

// buildBanner renames a masked banner bundle for spec.Path and gives it
// pixels (nil keeps the template's). crc is list.bin's: the CRC-32 of the
// bundle's files together.
func buildBanner(raw []byte, spec bannerSpec, pixels []byte) (out []byte, crc uint32, err error) {
	if len(spec.Old) != len(spec.New) || len(spec.Path) != len(spec.Template) {
		return nil, 0, fmt.Errorf("%s: names must keep their length", spec.Path)
	}
	plain, err := unityasset.Unmask(raw, spec.Template)
	if err != nil {
		return nil, 0, err
	}
	b, err := readNodes(plain)
	if err != nil {
		return nil, 0, err
	}
	serialized, resS, err := bannerFiles(b)
	if err != nil {
		return nil, 0, err
	}
	oldCAB := serialized.name
	sum := md5.Sum([]byte(spec.Path))
	newCAB := "CAB-" + hex.EncodeToString(sum[:])
	if len(oldCAB) != len(newCAB) || !strings.HasPrefix(oldCAB, "CAB-") {
		return nil, 0, fmt.Errorf("%s: file name %q is not a CAB name", spec.Template, oldCAB)
	}
	data := bytes.Clone(serialized.data)
	if !bytes.Contains(data, []byte(spec.Old)) || !bytes.Contains(data, []byte(oldCAB)) {
		return nil, 0, fmt.Errorf("%s does not name %s", spec.Template, spec.Old)
	}
	data = bytes.ReplaceAll(data, []byte(oldCAB), []byte(newCAB))
	data = bytes.ReplaceAll(data, []byte(spec.Old), []byte(spec.New))
	serialized.data, serialized.name = data, newCAB
	resS.name = newCAB + ".resS"
	if pixels != nil {
		if len(pixels) != len(resS.data) {
			return nil, 0, fmt.Errorf("%s: image of %d bytes, the banner has %d", spec.Path, len(pixels), len(resS.data))
		}
		resS.data = pixels
	}
	bundle, err := writeNodes(b)
	if err != nil {
		return nil, 0, err
	}
	marker := raw[0]
	if marker != 0x31 && marker != 0x32 {
		marker = 0x32
	}
	return Mask(bundle, spec.Path, marker), crc32.ChecksumIEEE(append(bytes.Clone(serialized.data), resS.data...)), nil
}

// bannerPixels is the image of a banner bundle in the game files (its .resS).
func bannerPixels(assets, path string) ([]byte, error) {
	raw, err := os.ReadFile(bannerBundlePath(assets, path))
	if err != nil {
		return nil, err
	}
	plain, err := unityasset.Unmask(raw, path)
	if err != nil {
		return nil, err
	}
	b, err := readNodes(plain)
	if err != nil {
		return nil, err
	}
	_, resS, err := bannerFiles(b)
	if err != nil {
		return nil, err
	}
	return resS.data, nil
}

func bannerBundlePath(assets, path string) string {
	return filepath.Join(assets, "assetbundle", strings.ReplaceAll(path, ")", "/")+".assetbundle")
}

// Banners are the built bundles: their list entries by object id and the
// entries to add to the list (whole entries, in order).
type Banners struct {
	ID      string           `json:"id"`
	Entries map[string]Entry `json:"entries"`
	Added   [][]byte         `json:"added"`
}

const entryNumber = 1 // an entry's index field

// newEntry is template (an entry of list.bin, without its list field) for e,
// numbered number; its other fields are kept.
func newEntry(template []byte, e Entry, number uint64) []byte {
	var out []byte
	walkFields(template, func(f protoField) bool {
		switch {
		case f.number == entryNumber && f.wire == 0:
			out = appendVarintField(out, entryNumber, number)
		case f.number == entryPath && f.wire == 2:
			out = appendBytesField(out, entryPath, []byte(e.Path))
		case f.number == entrySize && f.wire == 0:
			out = appendVarintField(out, entrySize, e.Size)
		case f.number == entryCRC && f.wire == 0:
			out = appendVarintField(out, entryCRC, uint64(e.CRC))
		case f.number == entryMD5 && f.wire == 2:
			out = appendBytesField(out, entryMD5, []byte(e.MD5))
		case f.number == entryObjectID && f.wire == 2:
			out = appendBytesField(out, entryObjectID, []byte(e.ObjectID))
		default:
			out = append(out, f.raw...)
		}
		return true
	})
	return out
}

// listTemplates reads what the banners need from list.bin: the template
// entries by path, every object id in use and the highest entry number.
func listTemplates(data []byte, paths map[string]bool) (templates map[string][]byte, ids map[string]bool, top uint64, err error) {
	templates, ids = map[string][]byte{}, map[string]bool{}
	err = walkFields(data, func(f protoField) bool {
		if f.number != listBundleField || f.wire != 2 {
			return true
		}
		walkFields(f.bytes, func(g protoField) bool {
			switch {
			case g.number == entryNumber && g.wire == 0:
				top = max(top, g.varint)
			case g.number == entryPath && g.wire == 2 && paths[string(g.bytes)]:
				templates[string(g.bytes)] = f.bytes
			case g.number == entryObjectID && g.wire == 2:
				ids[string(g.bytes)] = true
			}
			return true
		})
		return true
	})
	return templates, ids, top, err
}

const objectLetters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

// objectID names a built bundle by its bytes (a changed bundle is a new
// object, never a changed one), unused in the list.
func objectID(content []byte, used map[string]bool) string {
	sum := sha256.Sum256(content)
	for n := 6; ; n++ {
		id := make([]byte, n)
		for i := range id {
			id[i] = objectLetters[int(sum[i%len(sum)])%len(objectLetters)]
		}
		if !used[string(id)] {
			used[string(id)] = true
			return string(id)
		}
	}
}

// buildBanners builds every banner into dir (one folder per build, named by
// what it was built from) and returns them; nil when the game files lack the
// templates. A build already on disk is used as it is.
func buildBanners(assets, listPath, listMD5, dir string, packFile func(string) ([]byte, error)) (*Banners, error) {
	specs := bannerSpecs()
	images := map[string][]byte{}
	key := sha256.New()
	key.Write([]byte(bannerVersion + ":" + listMD5))
	for _, s := range specs {
		if s.PackImage == "" || packFile == nil {
			continue
		}
		if b, err := packFile(s.PackImage); err == nil {
			images[s.PackImage] = b
			sum := sha256.Sum256(b)
			key.Write([]byte(":" + s.PackImage + ":" + hex.EncodeToString(sum[:])))
		} else if !errors.Is(err, os.ErrNotExist) {
			log.Printf("[Banners] %s: %v (the banner keeps its own image)", s.PackImage, err)
		}
	}
	id := hex.EncodeToString(key.Sum(nil))[:16]
	folder := filepath.Join(dir, id)
	if data, err := os.ReadFile(filepath.Join(folder, "banners.json")); err == nil {
		var b Banners
		if json.Unmarshal(data, &b) == nil && b.ID == id {
			return &b, nil
		}
	}
	want := map[string]bool{}
	for _, s := range specs {
		want[s.Template] = true
	}
	list, err := os.ReadFile(listPath)
	if err != nil {
		return nil, err
	}
	templates, used, top, err := listTemplates(list, want)
	if err != nil {
		return nil, err
	}
	if len(templates) == 0 {
		return nil, nil
	}
	os.RemoveAll(dir)
	b := &Banners{ID: id, Entries: map[string]Entry{}}
	for _, s := range specs {
		template, ok := templates[s.Template]
		if !ok {
			log.Printf("[Banners] %s: no %s in the game files", s.Path, s.Template)
			continue
		}
		raw, err := os.ReadFile(bannerBundlePath(assets, s.Template))
		if err != nil {
			log.Printf("[Banners] %s: %v", s.Path, err)
			continue
		}
		pixels := images[s.PackImage]
		if s.FromBundle != "" {
			if pixels, err = bannerPixels(assets, s.FromBundle); err != nil {
				log.Printf("[Banners] %s: %v (it keeps %s's image)", s.Path, err, s.Template)
				pixels = nil
			}
		}
		out, crc, err := buildBanner(raw, s, pixels)
		if err != nil {
			log.Printf("[Banners] %s: %v", s.Path, err)
			continue
		}
		sum := md5.Sum(out)
		e := Entry{ObjectID: objectID(out, used), Path: s.Path, Size: uint64(len(out)), CRC: crc, MD5: hex.EncodeToString(sum[:])}
		if err := writeFileAtomic(filepath.Join(folder, e.ObjectID+".assetbundle"), out, 0644); err != nil {
			return nil, err
		}
		top++
		b.Entries[e.ObjectID] = e
		b.Added = append(b.Added, newEntry(template, e, top))
	}
	if len(b.Entries) == 0 {
		return nil, nil
	}
	data, err := json.Marshal(b)
	if err != nil {
		return nil, err
	}
	if err := writeFileAtomic(filepath.Join(folder, "banners.json"), data, 0644); err != nil {
		return nil, err
	}
	names := make([]string, 0, len(b.Entries))
	for _, e := range b.Entries {
		names = append(names, e.Path)
	}
	sort.Strings(names)
	log.Printf("[Banners] built %d: %s", len(names), strings.Join(names, ", "))
	return b, nil
}
