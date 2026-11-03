"""Fail-closed comparison for the qualified numeric-carrier FCSEL repair.

This module does not lift, optimize, instrument, compile, or execute guest code.
The caller supplies original-opcode-attributed sites in the selected old body.
Only its erroneous scalar pointer/read is replaced. The complete resulting body
must equal the fresh body under a bijection of local names and exact attribute /
reachable metadata contents. Any other difference is a HOLD.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Mapping, Sequence

LOCAL = r'%[-A-Za-z$._0-9]+'
QUOTED = r'"(?:[^"\\]|\\.)*"'
PAIR = re.compile(
    rf'^  (?P<pointer>{LOCAL}) = inttoptr i64 (?P<source>{LOCAL}) to ptr\n'
    rf'  (?P<loaded>{LOCAL}) = load i(?P<width>32|64), ptr (?P=pointer), align 1\n'
    rf'  store i(?P=width) (?P=loaded), ptr (?P<destination>{LOCAL}), align 1', re.M)
FUNCTION = re.compile(r'^define[^\n]*@sub_([0-9a-f]+)\([^\n]*\).*?^}', re.M | re.S)
ENTRY_TYPE = r'(?:float|double|i\d+|\[\d+ x i\d+\]|%[-A-Za-z$._0-9]+)'
ENTRY_PREFIX = re.compile(r'[^\n]+\n((?:  %[-A-Za-z$._0-9]+ = alloca '
                          + '(?:' + ENTRY_TYPE + r'|ptr), align \d+\n)*)')


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    mapped_body: str | None
    proof: dict[str, Any]
    hold_reason: str | None


class Hold(ValueError):
    """An unproved or unsupported comparison shape; never a relaxed match."""


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _outside(text: str, pattern: str, replacement) -> str:
    token = re.compile(QUOTED + '|(?:' + pattern + ')')
    return token.sub(lambda m: m[0] if m[0].startswith('"') else replacement(m[0]), text)


def parse_attributes(module: str) -> dict[str, str]:
    result = {}
    for m in re.finditer(r'^attributes #(\d+) = (.*)$', module, re.M):
        if m[1] in result:
            raise Hold('duplicate attribute group')
        result[m[1]] = m[2]
    return result


def parse_metadata(module: str) -> dict[str, str]:
    """Read LLVM's printed numeric nodes. Multiline nodes fail explicitly."""
    result = {}
    for m in re.finditer(r'^!(\d+) = (.*)$', module, re.M):
        if m[1] in result:
            raise Hold('duplicate metadata node')
        bare = re.sub(QUOTED, '""', m[2])
        if any(bare.count(a) != bare.count(b) for a, b in [('(', ')'), ('[', ']'), ('{', '}')]):
            raise Hold('multiline or unbalanced metadata node')
        result[m[1]] = m[2]
    return result


def parse_types(module: str) -> dict[str, str]:
    result = {}
    for m in re.finditer(r'^(%[-A-Za-z$._0-9]+) = type (.*)$', module, re.M):
        if m[1] in result:
            raise Hold('duplicate named type')
        bare = re.sub(QUOTED, '""', m[2])
        if any(bare.count(a) != bare.count(b) for a, b in [('(', ')'), ('[', ']'), ('{', '}'), ('<', '>')]):
            raise Hold('multiline or unbalanced named type')
        result[m[1]] = m[2]
    return result


def _type_closure(roots, old_types, new_types) -> dict[str, str]:
    closure = {}
    pending = list(roots)
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        if name not in old_types or name not in new_types:
            raise Hold('reachable named type definition absent')
        if old_types[name] != new_types[name]:
            raise Hold('reachable old/fresh named type contents differ')
        closure[name] = old_types[name]
        pending.extend(re.findall(LOCAL, re.sub(QUOTED, '', closure[name])))
        if len(closure) > 256:
            raise Hold('named type closure exceeds bounded graph limit')
    return closure


def _pure_bitcontainer(root: str, types: Mapping[str, str]) -> None:
    """Validate only fixed value types, not LLVM pointers or allocation flags."""
    active = set()
    complete = set()
    def named(name):
        if name in active:
            raise Hold('recursive by-value allocation type')
        if name in complete:
            return
        if name not in types or len(active) >= 64:
            raise Hold('missing or excessively deep allocation type')
        active.add(name)
        text = types[name]
        pos = parse(text, 0)
        if text[pos:].strip():
            raise Hold('non-value syntax in named allocation type')
        active.remove(name)
        complete.add(name)
    def skip(text, pos):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        return pos
    def parse(text, pos):
        pos = skip(text, pos)
        scalar = re.match(r'(?:i[1-9][0-9]*|half|bfloat|float|double|fp128|x86_fp80|ppc_fp128)(?![-\w.$])', text[pos:])
        if scalar:
            return pos + len(scalar[0])
        reference = re.match(LOCAL, text[pos:])
        if reference:
            named(reference[0])
            return pos + len(reference[0])
        array = re.match(r'\[\s*([1-9][0-9]*)\s+x\s+', text[pos:])
        if array:
            if int(array[1]) > 1048576:
                raise Hold('allocation array exceeds bounded container limit')
            end = skip(text, parse(text, pos + len(array[0])))
            if end >= len(text) or text[end] != ']':
                raise Hold('malformed fixed allocation array')
            return end + 1
        packed = text.startswith('<{', pos)
        if packed or text.startswith('{', pos):
            end = skip(text, pos + (2 if packed else 1))
            if end < len(text) and text[end] == '}':
                raise Hold('empty allocation container is outside the profile')
            while True:
                end = skip(text, parse(text, end))
                if end < len(text) and text[end] == ',':
                    end += 1
                    continue
                close = '}>' if packed else '}'
                if not text.startswith(close, end):
                    raise Hold('malformed allocation struct')
                return end + len(close)
        raise Hold('allocation type is not a pure fixed-size bitcontainer')
    named(root)


def _named_entry_types(body: str) -> set[str]:
    prefix = ENTRY_PREFIX.match(body)
    if not prefix:
        raise Hold('unrecognized function entry')
    return set(re.findall(r'= alloca (%[-A-Za-z$._0-9]+), align \d+', prefix[1]))


def extract_functions(module: str) -> dict[int, str]:
    result = {}
    for m in FUNCTION.finditer(module):
        head = int(m[1], 16)
        if head in result:
            raise Hold('duplicate function definition')
        result[head] = m[0]
    return result


def _definitions(body: str) -> dict[str, tuple[int, str]]:
    result = {}
    for m in re.finditer(rf'^  ({LOCAL}) = ([^\n]+)$', body, re.M):
        if m[1] in result:
            raise Hold('duplicate SSA definition')
        result[m[1]] = (m.start(), m[2])
    return result


def _register(definitions, name: str) -> int:
    try:
        rhs = definitions[name][1]
    except KeyError as error:
        raise Hold('missing vector register definition') from error
    m = re.fullmatch(r'getelementptr inbounds %struct.State, ptr %[-\w.$]+, '
                     r'i32 0, i32 0, i32 1, i32 0, i32 (\d+), i32 0, i32 0, i32 0', rhs)
    if not m or not 0 <= int(m[1]) < 32:
        raise Hold('destination/source is not an architectural vector register')
    return int(m[1])


def _source_register(body: str, definitions, value: str, before: int) -> int:
    def definition(name, pattern):
        if name not in definitions or definitions[name][0] >= before:
            raise Hold('source value is not snapshotted before FCSEL')
        match = re.fullmatch(pattern, definitions[name][1])
        if not match:
            raise Hold('unrecognized vector-to-numeric source dataflow')
        return match
    m = definition(value, rf'trunc i128 ({LOCAL}) to i64')
    m = definition(m[1], rf'load i128, ptr ({LOCAL}), align 16')
    m = definition(m[1], rf'bitcast ptr ({LOCAL}) to ptr')
    temporary = m[1]
    m = definition(temporary, r'alloca (\[4 x i32\]|\[2 x i64\]), align (4|8)')
    shape, alignment = m[1], m[2]
    stores = list(re.finditer(rf'^  store {re.escape(shape)} ({LOCAL}), ptr '
                             rf'{re.escape(temporary)}, align {alignment}$', body[:before], re.M))
    if len(stores) != 1:
        raise Hold('source temporary does not have exactly one vector snapshot store')
    loaded = stores[0][1]
    m = definition(loaded, rf'load {re.escape(shape)}, ptr ({LOCAL}), align {alignment}')
    return _register(definitions, m[1])


def _check_site(body: str, match, site: Mapping[str, Any], definitions) -> dict[str, Any]:
    width = int(match['width'])
    supplied_width = site.get('native_width', site.get('width'))
    if supplied_width != width:
        raise Hold('site width differs from the exact old load')
    if site.get('function_sha256', _sha(body)) != _sha(body):
        raise Hold('site does not bind the selected old body hash')
    for name in [match['pointer'], match['loaded']]:
        occurrences = re.findall(re.escape(name) + r'(?![-A-Za-z$._0-9])', body)
        if len(occurrences) != 2:
            raise Hold('old pointer/load result has additional uses')
    destination = match['destination']
    rd = _register(definitions, destination)
    if site.get('rd') != rd:
        raise Hold('site destination register differs')
    source = match['source']
    if source not in definitions or definitions[source][0] >= match.start():
        raise Hold('selected numeric source is missing or not prior to pointer conversion')
    rhs = definitions[source][1]
    selection = re.fullmatch(rf'select i1 ({LOCAL}), i64 ({LOCAL}), i64 ({LOCAL})', rhs)
    # LLVM may invert the predicate and swap select arms (e.g. MI becomes
    # N==0). Original operands are identified by their snapshot order, while
    # the complete-body comparison below preserves the predicate/arm wiring.
    values = [selection[2], selection[3]] if selection else [source]
    if selection:
        if any(value not in definitions for value in values):
            raise Hold('select arm definition absent')
        values.sort(key=lambda value: definitions[value][0])
    registers = [_source_register(body, definitions, v, match.start()) for v in values]
    if registers != site.get('source_vector_registers'):
        raise Hold('site source registers differ from the scalar value dataflow')
    # Architectural destination upper bits must already be explicitly cleared.
    tail = body[match.end():]
    if width == 32:
        zero = re.match(rf'\n  ({LOCAL}) = getelementptr inbounds \[4 x i32\], ptr '
                        rf'{re.escape(destination)}, i64 0, i64 1\n'
                        rf'  store <2 x i32> zeroinitializer, ptr \1, align 1\n'
                        rf'  ({LOCAL}) = getelementptr inbounds \[4 x i32\], ptr '
                        rf'{re.escape(destination)}, i64 0, i64 3\n'
                        rf'  store i32 0, ptr \2, align 1', tail)
    else:
        zero = re.match(rf'\n  ({LOCAL}) = getelementptr inbounds \[2 x i64\], ptr '
                        rf'{re.escape(destination)}, i64 0, i64 1\n'
                        rf'  store i64 0, ptr \1, align 1', tail)
    if not zero:
        raise Hold('missing unchanged architectural upper-vector clear')
    candidates = site.get('original_FCSEL_candidates_in_head_FDE',
                          site.get('original_opcode_candidates', []))
    if not candidates:
        raise Hold('site lacks original-opcode attribution')
    for candidate in candidates:
        try:
            word = int(candidate['word'], 16)
            bits = (word >> 22) & 3
            expected_regs = [candidate['rn'], candidate['rm']] if selection else [candidate['rn']]
            if (word & 0xff200c00 != 0x1e200c00 or bits not in (0, 1)
                or candidate['width'] != width or (32 if bits == 0 else 64) != width
                or candidate['rd'] != rd or (word & 31) != rd
                or ((word >> 5) & 31) != candidate['rn'] or ((word >> 16) & 31) != candidate['rm']
                or ((word >> 12) & 15) != candidate['cond'] or expected_regs != registers
                or (not selection and candidate['cond'] not in (14, 15))):
                raise Hold('original opcode/register attribution differs')
        except (KeyError, TypeError, ValueError) as error:
            raise Hold('malformed original-opcode attribution') from error
    return dict(offset=match.start(), width=width, destination=rd,
                source_registers=registers, old_pointer=match['pointer'],
                old_load=match['loaded'], carrier=source,
                original_candidates=[dict(x) for x in candidates],
                attribution=site.get('attribution', 'original-head-FDE'))


def _repair_old(body: str, sites: Sequence[Mapping[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    if not sites:
        raise Hold('no attributed FCSEL sites requested')
    definitions = _definitions(body)
    substitutions = []
    proofs = []
    offsets = set()
    for site in sites:
        offset = site.get('IR_offset', site.get('offset'))
        if not isinstance(offset, int) or isinstance(offset, bool) or offset in offsets:
            raise Hold('missing, noninteger or duplicate selected-body site offset')
        match = PAIR.match(body, offset)
        if not match:
            raise Hold('site offset does not identify the exact pointer/load/store idiom')
        offsets.add(offset)
        proof = _check_site(body, match, site, definitions)
        prefix = (f"  {match['loaded']} = trunc i64 {match['source']} to i32\n"
                  if match['width'] == '32' else '')
        stored = match['loaded'] if match['width'] == '32' else match['source']
        replacement = prefix + f"  store i{match['width']} {stored}, ptr {match['destination']}, align 1"
        substitutions.append((match.start(), match.end(), replacement))
        proofs.append(proof)
    for start, end, replacement in sorted(substitutions, reverse=True):
        body = body[:start] + replacement + body[end:]
    return body, proofs


def _alpha(body: str, permitted_named_allocas=frozenset()) -> tuple[str, dict[str, str]]:
    header = body.splitlines()[0]
    m = re.fullmatch(r'define[^\n]*@sub_[0-9a-f]+\((.*)\)[^\n]*\{', header)
    if not m:
        raise Hold('unrecognized translated function header')
    arguments = re.findall(LOCAL, m[1])
    if len(arguments) != 3 or len(set(arguments)) != 3:
        raise Hold('unrecognized translated three-argument ABI')
    definitions = [(x.start(), x[1]) for x in re.finditer(rf'^  ({LOCAL}) = ', body, re.M)]
    labels = [(x.start(), '%' + x[1]) for x in re.finditer(r'^([-A-Za-z$._0-9]+):', body, re.M)]
    # LLVM can permute indistinguishable static entry temporaries when assigning
    # their names. Give those names their first-use order, then sort declarations
    # ONLY within consecutive runs having the exact same allocation RHS. This
    # preserves their complete def/use bijection, type, alignment and count; it
    # permits no other instruction motion or variable-sized allocation change.
    prefix = ENTRY_PREFIX.match(body)
    if not _named_entry_types(body) <= set(permitted_named_allocas):
        raise Hold('named entry allocation requires a verified pure old/fresh type closure')
    entry = list(re.finditer(rf'^  ({LOCAL}) = (alloca [^\n]+)$', prefix[1], re.M))
    # Pointer cells are part of the static entry run, so they must not hide
    # later value temporaries. Their definitions nevertheless remain anchored
    # in the ordinary definition-order map and are never declaration-sorted.
    eligible = [x for x in entry if not x[2].startswith('alloca ptr,')]
    entry_names = {x[1] for x in eligible}
    tail = body[prefix.end():]
    def first_use(name):
        match = re.search(re.escape(name) + r'(?![-A-Za-z$._0-9])', tail)
        return match.start() if match else len(tail)
    entry_order = sorted((x[1] for x in eligible), key=first_use)
    names = arguments + entry_order + [name for _, name in sorted(definitions + labels)
                                       if name not in entry_names]
    if len(set(names)) != len(names):
        raise Hold('duplicate local value/label')
    # LLVM's unnamed initial block consumes %0 without printing a label.
    if re.search(r'%0(?![-A-Za-z$._0-9])', body) and '%0' not in names:
        names.insert(3, '%0')
    mapping = {name: f'%__fcsel_local_{i}' for i, name in enumerate(names)}
    renamed = _outside(body, LOCAL, lambda token: mapping.get(token, token))
    def label(match):
        value = mapping.get('%' + match[1])
        if value is None:
            raise Hold('unmapped basic block label')
        return value[1:] + ':'
    renamed = re.sub(r'^([-A-Za-z$._0-9]+):', label, renamed, flags=re.M)
    renamed = re.sub(r'^([-A-Za-z$._0-9]+):[ \t]+; preds =', r'\1: ; preds =', renamed, flags=re.M)
    if entry:
        lines = renamed.splitlines(keepends=True)
        start = 1
        while start <= len(entry):
            rhs = lines[start].split(' = ', 1)[1]
            if rhs.startswith('alloca ptr,'):
                start += 1
                continue
            end = start + 1
            while end <= len(entry) and lines[end].split(' = ', 1)[1] == rhs:
                end += 1
            lines[start:end] = sorted(lines[start:end])
            start = end
        renamed = ''.join(lines)
    return renamed, mapping


def _attribute_contents(body: str, attributes: Mapping[str, str]) -> str:
    def replace(token):
        key = token[1:]
        if key not in attributes:
            raise Hold('referenced attribute group absent')
        return '#ATTR<' + attributes[key] + '>'
    return _outside(body, r'#\d+', replace)


def _metadata_refs(text: str) -> tuple[str, list[str]]:
    refs = []
    def replace(token):
        refs.append(token[1:])
        return '!NODE'
    return _outside(text, r'!\d+', replace), refs


def _metadata_mapping(old: str, new: str, old_nodes, new_nodes) -> dict[str, str]:
    old_shape, old_roots = _metadata_refs(old)
    new_shape, new_roots = _metadata_refs(new)
    if old_shape != new_shape or len(old_roots) != len(new_roots):
        raise Hold('non-FCSEL instruction/CFG/type/attribute text differs after local renaming')
    new_to_old = {}
    old_to_new = {}
    todo = list(zip(old_roots, new_roots))
    while todo:
        old_id, new_id = todo.pop()
        if new_id in new_to_old:
            if new_to_old[new_id] != old_id:
                raise Hold('metadata sharing/identity differs')
            continue
        if old_id in old_to_new and old_to_new[old_id] != new_id:
            raise Hold('metadata identity is not bijective')
        if old_id not in old_nodes or new_id not in new_nodes:
            raise Hold('reachable metadata definition absent')
        old_node, new_node = old_nodes[old_id], new_nodes[new_id]
        # Mapping local-value-bearing debug metadata needs a different owned
        # rewrite; do not silently attach an old local name to the fresh body.
        if re.search(LOCAL, re.sub(QUOTED, '', old_node + new_node)):
            raise Hold('value/type-bearing metadata is outside this bounded splice')
        a, ar = _metadata_refs(old_node)
        b, br = _metadata_refs(new_node)
        if a != b or len(ar) != len(br):
            raise Hold('reachable metadata node contents or distinctness differ')
        new_to_old[new_id] = old_id
        old_to_new[old_id] = new_id
        todo.extend(zip(ar, br))
    return new_to_old


def _verify_body(old_body: str, new_body: str, *, sites,
                 old_attributes, new_attributes, old_metadata=None,
                 new_metadata=None, old_types=None, new_types=None,
                 identity=False) -> VerificationResult:
    """Return a fresh body mapped into the exact old module, or a HOLD result.

    ``sites`` uses the inventory's IR_offset/native_width/rd/source registers/
    original_FCSEL_candidates_in_head_FDE fields. Attributes and numeric metadata
    dictionaries are id->printed contents, as returned by the parse helpers.
    This validates a supplied proposal; it never constructs a fallback candidate.
    """
    try:
        old_name = re.match(r'^define[^\n]*@(sub_[0-9a-f]+)\(', old_body)
        new_name = re.match(r'^define[^\n]*@(sub_[0-9a-f]+)\(', new_body)
        if not old_name or not new_name or old_name[1] != new_name[1]:
            raise Hold('function identity differs')
        old_attributes = {str(k): v for k, v in old_attributes.items()}
        new_attributes = {str(k): v for k, v in new_attributes.items()}
        old_metadata = {str(k): v for k, v in (old_metadata or {}).items()}
        new_metadata = {str(k): v for k, v in (new_metadata or {}).items()}
        named_allocas = _named_entry_types(old_body) | _named_entry_types(new_body)
        old_types = old_types or {}
        new_types = new_types or {}
        allocation_types = _type_closure(named_allocas, old_types, new_types)
        for root in named_allocas:
            _pure_bitcontainer(root, allocation_types)
        used_type_closure = {}
        if old_types or new_types or identity:
            # This includes the whole State graph and any non-State type used by
            # the body; only allocation roots require the stricter value grammar.
            locals_old = set(_definitions(old_body))
            roots = set(re.findall(LOCAL, old_body)) & (set(old_types) | set(new_types))
            roots -= locals_old
            used_type_closure = _type_closure(roots, old_types, new_types)
            if identity and not used_type_closure:
                raise Hold('context helper identity requires explicit named type closure')
        repaired, site_proofs = (old_body, []) if identity else _repair_old(old_body, sites)
        expected, old_local_map = _alpha(repaired, named_allocas)
        proposed, new_local_map = _alpha(new_body, named_allocas)
        expected = _attribute_contents(expected, old_attributes)
        proposed = _attribute_contents(proposed, new_attributes)
        metadata_map = _metadata_mapping(expected, proposed, old_metadata, new_metadata)
        old_by_content = {}
        for key, value in old_attributes.items():
            old_by_content.setdefault(value, key)
        attribute_map = {}
        def map_attribute(token):
            key = token[1:]
            if key not in new_attributes or new_attributes[key] not in old_by_content:
                raise Hold('fresh attribute has no byte-identical old group')
            attribute_map[key] = old_by_content[new_attributes[key]]
            return '#' + attribute_map[key]
        mapped = _outside(new_body, r'#\d+', map_attribute)
        mapped = _outside(mapped, r'!\d+', lambda token: '!' + metadata_map[token[1:]])
        # Validate the actual returned body after ID remapping, not only a
        # surrogate normalized comparison.
        mapped_shape = _attribute_contents(_alpha(mapped, named_allocas)[0], old_attributes)
        assert _metadata_mapping(expected, mapped_shape, old_metadata, old_metadata) == {
            value: value for value in metadata_map.values()}
        proof = dict(function=old_name[1], old_body_sha256=_sha(old_body),
                     fresh_body_sha256=_sha(new_body), mapped_body_sha256=_sha(mapped),
                     site_count=len(site_proofs), sites=site_proofs,
                     complete_non_FCSEL_body_equal=True,
                     context_helper_identity=identity,
                     SSA_and_labels_bijective=True,
                     identical_static_entry_allocas_mapped_by_bijective_first_use=True,
                     static_entry_pointer_cells_anchored=True,
                     lifetime_and_effectful_instruction_order_exact=True,
                     pure_named_allocation_types=allocation_types,
                     reachable_named_type_closure=used_type_closure,
                     old_local_count=len(old_local_map), new_local_count=len(new_local_map),
                     attributes_mapped_by_exact_contents=attribute_map,
                     reachable_metadata_bijection=metadata_map,
                     width32_rule='pointer+load32 replaced by numeric trunc64to32',
                     width64_rule='pointer+load64 replaced by unchanged numeric64 carrier')
        return VerificationResult(True, mapped, proof, None)
    except (Hold, KeyError, TypeError, ValueError, AssertionError) as error:
        return VerificationResult(False, None,
                                  dict(old_body_sha256=_sha(old_body), fresh_body_sha256=_sha(new_body)),
                                  str(error) or type(error).__name__)


def verify_body(old_body: str, new_body: str, *, sites,
                old_attributes, new_attributes, old_metadata=None,
                new_metadata=None, old_types=None, new_types=None) -> VerificationResult:
    """Strict FCSEL-only comparison; zero-site calls remain a HOLD."""
    return _verify_body(old_body, new_body, sites=sites,
                        old_attributes=old_attributes, new_attributes=new_attributes,
                        old_metadata=old_metadata, new_metadata=new_metadata,
                        old_types=old_types, new_types=new_types)


def verify_identity(old_body: str, new_body: str, *, old_attributes, new_attributes,
                    old_metadata=None, new_metadata=None,
                    old_types=None, new_types=None) -> VerificationResult:
    """Zero-repair helper check; no source-bit, call-target or CFG differences."""
    return _verify_body(old_body, new_body, sites=[], identity=True,
                        old_attributes=old_attributes, new_attributes=new_attributes,
                        old_metadata=old_metadata, new_metadata=new_metadata,
                        old_types=old_types, new_types=new_types)


def splice_verified(old_module: str, results: Mapping[int, VerificationResult]) -> tuple[str, dict]:
    """Replace only verified bodies; inverse reconstruction proves all else exact."""
    old_functions = extract_functions(old_module)
    candidate = old_module
    for head, result in results.items():
        if not result.passed or not result.mapped_body or head not in old_functions:
            raise Hold('attempt to splice an unverified or absent function')
        if result.proof['old_body_sha256'] != _sha(old_functions[head]):
            raise Hold('verification did not bind the exact module body')
        if f'@sub_{head:x}(' not in result.mapped_body.splitlines()[0]:
            raise Hold('verified function identity differs from requested head')
        if candidate.count(old_functions[head]) != 1:
            raise Hold('old function is not uniquely present')
        candidate = candidate.replace(old_functions[head], result.mapped_body)
    functions = extract_functions(candidate)
    if set(functions) != set(old_functions):
        raise Hold('function/head set changed')
    inverse = candidate
    for head, result in results.items():
        if functions[head] != result.mapped_body or inverse.count(result.mapped_body) != 1:
            raise Hold('candidate body is not uniquely present')
        inverse = inverse.replace(result.mapped_body, old_functions[head])
    if inverse != old_module:
        raise Hold('nonfunction text or an unrequested body changed')
    return candidate, dict(passed=True, old_module_sha256=_sha(old_module),
                           candidate_module_sha256=_sha(candidate),
                           definitions=len(functions), changed_heads=[hex(h) for h in sorted(results)],
                           unchanged_bodies=len(functions)-len(results),
                           inverse_module_byte_exact=True,
                           State_types_declarations_globals_attributes_metadata_untouched=True)


# Separate explicit repair mode. The fresh-comparison APIs above are unchanged.
TRANSPORT_PROOF_MODE = 'exact-attributed-fcsel-transport-v1'


def _transport_edits(old_body: str, sites) -> tuple[list[dict], list[dict]]:
    if not sites:
        raise Hold('no attributed FCSEL transport sites requested')
    definitions = _definitions(old_body)
    edits = []
    proofs = []
    offsets = set()
    for site in sites:
        offset = site.get('IR_offset', site.get('offset'))
        if type(offset) is not int or offset in offsets:
            raise Hold('missing, noninteger or duplicate transport site offset')
        match = PAIR.match(old_body, offset)
        if not match:
            raise Hold('transport site is not the exact old pointer/load/store idiom')
        offsets.add(offset)
        proofs.append(_check_site(old_body, match, site, definitions))
        start = old_body.index('\n', match.start()) + 1
        end = old_body.index('\n', start)
        before = old_body[start:end]
        expected = f"  {match['loaded']} = load i{match['width']}, ptr {match['pointer']}, align 1"
        if before != expected:
            raise Hold('transport load has an unqualified suffix or instruction form')
        if match['width'] == '32':
            after = f"  {match['loaded']} = trunc i64 {match['source']} to i32"
        else:
            after = f"  {match['loaded']} = add i64 {match['source']}, 0"
        edits.append(dict(start=start, end=end, old_line=before, new_line=after))
    edits.sort(key=lambda row: row['start'])
    if any(a['end'] > b['start'] for a, b in zip(edits, edits[1:])):
        raise Hold('overlapping transport line edits')
    return edits, proofs


def build_transport_candidate(old_body: str, *, sites) -> str:
    """Build only the attributed scalar load-line substitutions, or raise Hold.

    Keeping the now-unused inttoptr definition leaves every existing SSA value,
    label, metadata identity and numbering intact. It performs no memory access.
    The i64 add has neither overflow flags nor State/FP side effects.
    """
    edits, _ = _transport_edits(old_body, sites)
    candidate = old_body
    for row in reversed(edits):
        candidate = candidate[:row['start']] + row['new_line'] + candidate[row['end']:]
    return candidate


def verify_transport_body(old_body: str, candidate_body: str, *, sites) -> VerificationResult:
    """Verify the distinct exact-line mode; never claim whole-fresh-body equality.

    The caller must additionally require the independently qualified original
    condition/predicate binding. Module insertion uses splice_verified, retaining
    the exact old State/types/globals/attributes/metadata and every other body.
    """
    try:
        function = re.match(r'^define[^\n]*@(sub_[0-9a-f]+)\(', old_body)
        if not function:
            raise Hold('transport input is not a selected translated function body')
        edits, site_proofs = _transport_edits(old_body, sites)
        expected = old_body
        for row in reversed(edits):
            expected = expected[:row['start']] + row['new_line'] + expected[row['end']:]
        if candidate_body != expected:
            raise Hold('candidate differs from the exact attributed transport load-line rewrite')
        shift = 0
        mapped_edits = []
        for row in edits:
            start = row['start'] + shift
            end = start + len(row['new_line'])
            if candidate_body[start:end] != row['new_line']:
                raise Hold('transport line edit location differs')
            mapped_edits.append(dict(row, candidate_start=start, candidate_end=end))
            shift += len(row['new_line']) - len(row['old_line'])
        inverse = candidate_body
        for row in reversed(mapped_edits):
            inverse = inverse[:row['candidate_start']] + row['old_line'] + inverse[row['candidate_end']:]
        if inverse != old_body:
            raise Hold('inverse transport line edits do not recover the exact original body')
        proof = dict(proof_mode=TRANSPORT_PROOF_MODE, function=function[1],
                     old_body_sha256=_sha(old_body), mapped_body_sha256=_sha(candidate_body),
                     site_count=len(site_proofs), sites=site_proofs,
                     exact_transport_line_edits=True, inverse_body_byte_exact=True,
                     complete_non_FCSEL_body_equal=True,
                     fresh_body_equality_claimed=False, context_helper_identity=False,
                     original_inttoptr_definitions_retained=True,
                     SSA_names_labels_attributes_metadata_and_other_bytes_unchanged=True,
                     condition_predicate_and_select_arms_unchanged=True,
                     destination_store_and_upper_clear_unchanged=True,
                     separate_original_condition_qualification_required=True,
                     line_edits=mapped_edits)
        return VerificationResult(True, candidate_body, proof, None)
    except (Hold, KeyError, TypeError, ValueError, AssertionError) as error:
        return VerificationResult(False, None,
                                  dict(proof_mode=TRANSPORT_PROOF_MODE,
                                       old_body_sha256=_sha(old_body),
                                       candidate_body_sha256=_sha(candidate_body)),
                                  str(error) or type(error).__name__)
