package unityasset

import (
	"encoding/binary"
	"fmt"
	"math"
	"strings"
)

// typeNode is one field of a Unity type tree.
type typeNode struct {
	typ, name string
	size      int32
	meta      int32
	children  []*typeNode
}

type objectInfo struct {
	pathID     int64
	start, end int64
	classID    int32
	tree       *typeNode
}

// SerializedFile is the object table of one serialized file in a bundle.
type SerializedFile struct {
	data    []byte
	order   binary.ByteOrder
	objects []objectInfo
	byID    map[int64]int
	// Externals are the files a PPtr's FileID (from 1) points into, as Unity names them,
	// e.g. "archive:/CAB-0123…/CAB-0123…".
	Externals []string
}

// Object is a decoded object: its class and its fields by name.
type Object struct {
	ClassID int32
	PathID  int64
	Fields  map[string]any
}

// commonStrings is Unity's shared type-tree string table (offsets with the high bit set).
var commonStrings = func() map[uint32]string {
	const table = "AABB\x00AnimationClip\x00AnimationCurve\x00AnimationState\x00Array\x00Base\x00BitField\x00bitset\x00bool\x00char\x00ColorRGBA\x00Component\x00data\x00deque\x00double\x00dynamic_array\x00FastPropertyName\x00first\x00float\x00Font\x00GameObject\x00Generic Mono\x00GradientNEW\x00GUID\x00GUIStyle\x00int\x00list\x00long long\x00map\x00Matrix4x4f\x00MdFour\x00MonoBehaviour\x00MonoScript\x00m_ByteSize\x00m_Curve\x00m_EditorClassIdentifier\x00m_EditorHideFlags\x00m_Enabled\x00m_ExtensionPtr\x00m_GameObject\x00m_Index\x00m_IsArray\x00m_IsStatic\x00m_MetaFlag\x00m_Name\x00m_ObjectHideFlags\x00m_PrefabInternal\x00m_PrefabParentObject\x00m_Script\x00m_StaticEditorFlags\x00m_Type\x00m_Version\x00Object\x00pair\x00PPtr<Component>\x00PPtr<GameObject>\x00PPtr<Material>\x00PPtr<MonoBehaviour>\x00PPtr<MonoScript>\x00PPtr<Object>\x00PPtr<Prefab>\x00PPtr<Sprite>\x00PPtr<TextAsset>\x00PPtr<Texture>\x00PPtr<Texture2D>\x00PPtr<Transform>\x00Prefab\x00Quaternionf\x00Rectf\x00RectInt\x00RectOffset\x00second\x00set\x00short\x00size\x00SInt16\x00SInt32\x00SInt64\x00SInt8\x00staticvector\x00string\x00TextAsset\x00TextMesh\x00Texture\x00Texture2D\x00Transform\x00TypelessData\x00UInt16\x00UInt32\x00UInt64\x00UInt8\x00unsigned int\x00unsigned long long\x00unsigned short\x00vector\x00Vector2f\x00Vector3f\x00Vector4f\x00m_ScriptingClassIdentifier\x00Gradient\x00Type*\x00int2_storage\x00int3_storage\x00BoundsInt\x00m_CorrespondingSourceObject\x00m_PrefabInstance\x00m_PrefabAsset\x00FileSize\x00Hash128\x00"
	out := map[uint32]string{}
	off := 0
	for _, s := range strings.Split(strings.TrimSuffix(table, "\x00"), "\x00") {
		out[uint32(off)] = s
		off += len(s) + 1
	}
	return out
}()

func lookupString(pool []byte, off uint32) string {
	if off&0x80000000 != 0 {
		return commonStrings[off&0x7fffffff]
	}
	if int(off) >= len(pool) {
		return ""
	}
	end := int(off)
	for end < len(pool) && pool[end] != 0 {
		end++
	}
	return string(pool[off:end])
}

// ParseSerializedFile reads the header, type trees and object table.
func ParseSerializedFile(data []byte) (*SerializedFile, error) {
	r := &reader{b: data, order: binary.BigEndian}
	r.u32() // metadata size
	r.u32() // file size
	version := int(r.u32())
	dataOffset := int64(r.u32())
	if version < 17 {
		return nil, fmt.Errorf("serialized file version %d is not supported", version)
	}
	endian := r.u8()
	r.bytes(3)
	if version >= 22 {
		r.u32()
		r.u64()
		dataOffset = int64(r.u64())
		r.u64()
	}
	if endian == 0 {
		r.order = binary.LittleEndian
	}
	r.cstring() // Unity version
	r.u32()     // target platform
	enableTypeTree := r.u8() != 0
	types := make([]*typeNode, r.u32())
	for i := range types {
		classID := int32(r.u32()) // objects are matched by their type name instead
		r.u8()                    // stripped
		r.u16()                   // script type index
		if classID == 114 {
			r.bytes(16)
		}
		r.bytes(16)
		if enableTypeTree {
			tree, err := readTypeTree(r, version)
			if err != nil {
				return nil, err
			}
			types[i] = tree
			if version >= 21 {
				deps := int(r.u32())
				r.bytes(deps * 4)
			}
		}
		if r.err != nil {
			return nil, r.err
		}
	}
	count := int(r.u32())
	sf := &SerializedFile{data: data, order: r.order}
	for i := 0; i < count && r.err == nil; i++ {
		r.align(4)
		var o objectInfo
		o.pathID = int64(r.u64())
		if version >= 22 {
			o.start = int64(r.u64())
		} else {
			o.start = int64(r.u32())
		}
		size := int64(r.u32())
		typeIndex := int(int32(r.u32()))
		o.start += dataOffset
		o.end = o.start + size
		if typeIndex >= 0 && typeIndex < len(types) {
			o.tree = types[typeIndex]
		}
		sf.objects = append(sf.objects, o)
	}
	// Script types, then the external files.
	scripts := int(r.u32())
	for i := 0; i < scripts && r.err == nil; i++ {
		r.u32()
		r.align(4)
		r.u64()
	}
	externals := int(r.u32())
	for i := 0; i < externals && r.err == nil; i++ {
		r.cstring()
		r.bytes(16)
		r.u32()
		sf.Externals = append(sf.Externals, r.cstring())
	}
	if r.err != nil {
		return nil, r.err
	}
	sf.byID = make(map[int64]int, len(sf.objects))
	for i, o := range sf.objects {
		sf.byID[o.pathID] = i
	}
	return sf, nil
}

// Object decodes one object by its path ID.
func (sf *SerializedFile) Object(pathID int64) (Object, bool) {
	i, ok := sf.byID[pathID]
	if !ok || sf.objects[i].tree == nil {
		return Object{}, false
	}
	o := sf.objects[i]
	if o.start < 0 || o.end > int64(len(sf.data)) || o.start > o.end {
		return Object{}, false
	}
	r := &reader{b: sf.data[o.start:o.end], order: sf.order}
	v := readValue(r, o.tree)
	if r.err != nil {
		return Object{}, false
	}
	fields, _ := v.(map[string]any)
	return Object{ClassID: classIDs[o.tree.typ], PathID: o.pathID, Fields: fields}, true
}

func readTypeTree(r *reader, version int) (*typeNode, error) {
	nodeCount, poolSize := int(r.u32()), int(r.u32())
	if r.err != nil || nodeCount <= 0 || nodeCount > 1<<20 {
		return nil, fmt.Errorf("bad type tree (%d nodes)", nodeCount)
	}
	type flat struct {
		level      int
		typ, name  uint32
		size, meta int32
	}
	flats := make([]flat, nodeCount)
	for i := range flats {
		r.u16() // version
		flats[i].level = int(r.u8())
		r.u8() // type flags
		flats[i].typ, flats[i].name = r.u32(), r.u32()
		flats[i].size = int32(r.u32())
		r.u32() // index
		flats[i].meta = int32(r.u32())
		if version >= 19 {
			r.u64() // ref type hash
		}
	}
	pool := r.bytes(poolSize)
	if r.err != nil {
		return nil, r.err
	}
	var stack []*typeNode
	var root *typeNode
	for _, f := range flats {
		n := &typeNode{typ: lookupString(pool, f.typ), name: lookupString(pool, f.name), size: f.size, meta: f.meta}
		if f.level == 0 {
			root = n
			stack = []*typeNode{n}
			continue
		}
		if f.level > len(stack) {
			return nil, fmt.Errorf("type tree skips a level at %s", n.name)
		}
		stack = stack[:f.level]
		parent := stack[f.level-1]
		parent.children = append(parent.children, n)
		stack = append(stack, n)
	}
	return root, nil
}

// Objects decodes every object of the given class (0 for all).
func (sf *SerializedFile) Objects(classID int32) ([]Object, error) {
	return sf.ObjectsWith(classID, "")
}

// ObjectsWith decodes the objects of the given class whose type has a top-level
// field of that name (any object for ""), skipping the rest without decoding them.
func (sf *SerializedFile) ObjectsWith(classID int32, field string) ([]Object, error) {
	var out []Object
	for _, o := range sf.objects {
		if o.tree == nil {
			continue
		}
		cls := classIDs[o.tree.typ]
		if classID != 0 && cls != classID {
			continue
		}
		if field != "" && !hasField(o.tree, field) {
			continue
		}
		if o.start < 0 || o.end > int64(len(sf.data)) || o.start > o.end {
			return nil, fmt.Errorf("object %d lies outside the file", o.pathID)
		}
		r := &reader{b: sf.data[o.start:o.end], order: sf.order}
		v := readValue(r, o.tree)
		if r.err != nil {
			return nil, fmt.Errorf("object %d (%s): %w", o.pathID, o.tree.typ, r.err)
		}
		fields, _ := v.(map[string]any)
		out = append(out, Object{ClassID: cls, PathID: o.pathID, Fields: fields})
	}
	return out, nil
}

func hasField(n *typeNode, name string) bool {
	for _, c := range n.children {
		if c.name == name {
			return true
		}
	}
	return false
}

// classIDs maps the type names this package reads to Unity class IDs.
var classIDs = map[string]int32{"GameObject": 1, "Transform": 4, "Material": 21, "Texture2D": 28, "Mesh": 43, "TextAsset": 49,
	"AnimationClip": 74, "AudioClip": 83, "Avatar": 90, "AnimatorController": 91, "Animator": 95, "MonoBehaviour": 114, "SkinnedMeshRenderer": 137, "Sprite": 213}

func readValue(r *reader, n *typeNode) any {
	var v any
	alignAfter := n.meta&0x4000 != 0
	switch n.typ {
	case "SInt8":
		v = int64(int8(r.u8()))
	case "UInt8", "char":
		v = int64(r.u8())
	case "bool":
		v = r.u8() != 0
	case "SInt16", "short":
		v = int64(int16(r.u16()))
	case "UInt16", "unsigned short":
		v = int64(r.u16())
	case "SInt32", "int", "Type*":
		v = int64(int32(r.u32()))
	case "UInt32", "unsigned int":
		v = int64(r.u32())
	case "SInt64", "long long", "FileSize":
		v = int64(r.u64())
	case "UInt64", "unsigned long long":
		v = int64(r.u64())
	case "float":
		v = float64(math.Float32frombits(r.u32()))
	case "double":
		v = math.Float64frombits(r.u64())
	case "string":
		size := int(r.u32())
		v = string(r.bytes(size))
		if len(n.children) > 0 && n.children[0].meta&0x4000 != 0 {
			alignAfter = true
		}
	case "TypelessData":
		size := int(r.u32())
		v = r.bytes(size)
	default:
		if len(n.children) > 0 && n.children[0].typ == "Array" {
			arr := n.children[0]
			if arr.meta&0x4000 != 0 {
				alignAfter = true
			}
			size := int(r.u32())
			if size < 0 || size > len(r.b) {
				r.err = fmt.Errorf("bad array size %d in %s", size, n.name)
				return nil
			}
			elem := arr.children[1]
			if elem.typ == "UInt8" || elem.typ == "char" {
				v = r.bytes(size)
			} else {
				items := make([]any, 0, size)
				for i := 0; i < size && r.err == nil; i++ {
					items = append(items, readValue(r, elem))
				}
				v = items
			}
		} else {
			fields := map[string]any{}
			for _, c := range n.children {
				fields[c.name] = readValue(r, c)
				if r.err != nil {
					break
				}
			}
			v = fields
		}
	}
	if alignAfter {
		r.align(4)
	}
	return v
}
