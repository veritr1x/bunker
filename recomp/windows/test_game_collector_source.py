"""Immutable static gates for the optional game collector profile; no game run."""
import argparse,ast,hashlib,json,subprocess,tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
HERE=Path(__file__).resolve().parent
OWN=('game_bootstrap.cpp','game_bootstrap_detail.h','game_collector_delivery.h','game_unity_main_collector.h','game_collector_mask.h','game_bootstrap_build.ps1','test_game_bootstrap.py','game_collector_profile.md','test_game_collector_source.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

RUNTIME_DIAGNOSTIC_OLD='4c1609ebd11565fb45a55b4488428cbcff94851eea9bba58f4e160cc07850860'
RUNTIME_DIAGNOSTIC_NEW='56c28270e218dcb62ddecc6048dda9e9e727a876478eaa4b0f87823881c5ace1'
RUNTIME_DIAGNOSTIC_HEADER='c7f0d6c4cb446e78c2aecb2d8b7f078c4da03d949e7d7d15e05fe0b5b420248c'
RUNTIME_DIAGNOSTIC_QUALIFICATION='ca33662cafb9743a433972d84be2aaedbb0a698581115cf3b9f2ae5e66dc91cd'
RUNTIME_DIAGNOSTIC_INSERTION='016c0c45605f11fc0aa5078bd0f9472b8ca96997ca241b914b94695af0a965cb'

def verify_runtime_diagnostic_projection(body,proof):
 assert proof['passed']is True and proof['old_runtime_sha256']==RUNTIME_DIAGNOSTIC_OLD
 assert proof['new_runtime_sha256']==RUNTIME_DIAGNOSTIC_NEW and proof['runtime_header_sha256']==RUNTIME_DIAGNOSTIC_HEADER
 for field in ('exactly_one_fprintf_insertion','old_file_recovered_byte_exact','success_and_collector_paths_source_exact'):assert proof[field]is True,field
 insertion=proof['insertion'].encode('utf-8')
 assert hashlib.sha256(insertion).hexdigest()==RUNTIME_DIAGNOSTIC_INSERTION
 assert body.count(insertion)==1 and hashlib.sha256(body).hexdigest()==RUNTIME_DIAGNOSTIC_NEW
 assert hashlib.sha256(body.replace(insertion,b'',1)).hexdigest()==RUNTIME_DIAGNOSTIC_OLD

def qualified_runtime_source(path,legacy_digest,prerequisites=None,qualification_path=None):
 assert legacy_digest==RUNTIME_DIAGNOSTIC_OLD
 path=Path(path);qualification_path=Path(qualification_path)if qualification_path is not None else HERE.parent/'work/runtime-unresolved-diagnostic1/qualification4/acceptance.json'
 assert sha(qualification_path)==RUNTIME_DIAGNOSTIC_QUALIFICATION
 record=json.loads(qualification_path.read_text());assert record['passed']is True
 assert record['old_runtime_sha256']==RUNTIME_DIAGNOSTIC_OLD and record['new_runtime_sha256']==RUNTIME_DIAGNOSTIC_NEW
 assert record['runtime_header_sha256']==RUNTIME_DIAGNOSTIC_HEADER and sha(path.with_name('runtime.h'))==RUNTIME_DIAGNOSTIC_HEADER
 assert set(record['platforms'])=={'linux','windows'}
 for observed in record['platforms'].values():
  assert observed['legacy_negative_cases']==5 and set(observed['diagnostics'])=={'unresolved-zero','unresolved-nonzero'}
 proof_path=Path(record['inverse_proof_path']);assert sha(proof_path)==record['inverse_proof_sha256']
 proof=json.loads(proof_path.read_text());verify_runtime_diagnostic_projection(path.read_bytes(),proof)
 assert sha(proof['old_runtime_path'])==RUNTIME_DIAGNOSTIC_OLD
 if prerequisites is not None:
  prerequisites[str(qualification_path)]=RUNTIME_DIAGNOSTIC_QUALIFICATION
  prerequisites[str(proof_path)]=record['inverse_proof_sha256']
  prerequisites[proof['old_runtime_path']]=RUNTIME_DIAGNOSTIC_OLD
 return RUNTIME_DIAGNOSTIC_NEW
PUBLIC_AFFINITY_BASE_CORE={'windows/thread_affinity.h':'a7ee15512cefd1cf5cb64279cd3a56b5cffebc76f9ba684d69ebcd033bae1ef7','windows/thread_affinity.cpp':'59f38f6ad52bb0d18a296213d7642bdc08ad3db9c18b4f89b9dd4990aa00ea24'}
PUBLIC_AFFINITY_CORE={'windows/thread_affinity.h':'e9a35ad8bebd8dd8259ddea2313a4d97d057f19b9acb0b2fe12d9b4b63c89684','windows/thread_affinity.cpp':'29953aa90178eee58e9fc84d7cda68019916004d6f6f15c879a907492cdee9e5'}
PUBLIC_AFFINITY_QUALIFICATION='d53e2045cba776791bf684e17674cc8020dfd9eb03e4b3b0d190932a163deb26'
PUBLIC_AFFINITY_PROOF='ef640e0dab997275342e67a86b8ed05e81b64c318656fe1d0b4d49e6079e57bf'
PUBLIC_AFFINITY_QUALIFICATION_PATH=str(HERE.parent/'work/affinity-public-qualification2/acceptance.json')

def verify_public_affinity_projection(name,body,proof):
 assert name in PUBLIC_AFFINITY_BASE_CORE and proof['passed']is True
 assert proof['base_core_sources']==PUBLIC_AFFINITY_BASE_CORE and proof['core_sources']==PUBLIC_AFFINITY_CORE
 assert proof['public_affinity_additions_only']is True and proof['legacy_raw_setter_bodies_byte_exact']is True
 assert proof['public_apis']==['Get','Set'] and proof['old_file_recovered_byte_exact']is True
 assert proof['kernel_mask_profile_bytes']==8 and proof['public_mask_bytes']==128
 assert proof['base_commit']=='51046016c712835c3f6fdebec6a14e7be59639fc'
 assert hashlib.sha256(body).hexdigest()==PUBLIC_AFFINITY_CORE[name]
 records=sorted(proof['insertions'][name],key=lambda item:item['new_offset']);assert records
 blocks=[]
 for item in records:
  value=item['bytes_hex'];assert isinstance(value,str)and value
  added=bytes.fromhex(value);assert added.hex()==value and added
  assert type(item['old_offset'])is type(item['new_offset'])is int
  blocks.append(added)
 old_size=len(body)-sum(map(len,blocks));delta=0;previous_end=0
 for item,added in zip(records,blocks):
  old_offset,new_offset=item['old_offset'],item['new_offset']
  assert 0<=old_offset<=old_size and new_offset>=previous_end and new_offset==old_offset+delta
  assert body[new_offset:new_offset+len(added)]==added
  delta+=len(added);previous_end=new_offset+len(added)
 projected=body
 for item,added in reversed(list(zip(records,blocks))):
  offset=item['new_offset'];assert projected[offset:offset+len(added)]==added
  projected=projected[:offset]+projected[offset+len(added):]
 assert hashlib.sha256(projected).hexdigest()==PUBLIC_AFFINITY_BASE_CORE[name]

def qualified_public_affinity_source(path,name,legacy_digest,prerequisites=None,qualification_path=None):
 assert name in PUBLIC_AFFINITY_BASE_CORE and legacy_digest==PUBLIC_AFFINITY_BASE_CORE[name]
 path=Path(path);qualification_path=Path(qualification_path)if qualification_path is not None else Path(PUBLIC_AFFINITY_QUALIFICATION_PATH)
 assert sha(qualification_path)==PUBLIC_AFFINITY_QUALIFICATION
 record=json.loads(qualification_path.read_text());assert record['passed']is True
 assert record['commit']=='51046016c712835c3f6fdebec6a14e7be59639fc'
 assert record['core_sources']==PUBLIC_AFFINITY_CORE and record['source_proof_sha256']==PUBLIC_AFFINITY_PROOF
 proof_path=Path(record['source_proof_path']);assert sha(proof_path)==PUBLIC_AFFINITY_PROOF
 proof=json.loads(proof_path.read_text());verify_public_affinity_projection(name,path.read_bytes(),proof)
 if prerequisites is not None:
  prerequisites[str(qualification_path)]=PUBLIC_AFFINITY_QUALIFICATION
  prerequisites[str(proof_path)]=PUBLIC_AFFINITY_PROOF
 return PUBLIC_AFFINITY_CORE[name]

JNI_OBJECT_BIND_BASE={'windows/jni_host.h':'366f9292fc4d037b8f5da42a1dd241381485f1741d5b6ee64b2c2e6475a2c3a9','windows/jni_host.cpp':'376343cc6a78e64019b5ef43a4211ccc47a26f9d5a3ae826af6b6a6bf156e4ee'}
JNI_OBJECT_BIND_CORE={'windows/jni_host.h':'606a188ec507bf8c49acbb611ac4f8d769dde3b01dc3b77a3109471930d86f30','windows/jni_host.cpp':'0fad8c9cdc4fb66b4074a4d3ef248ee7ff8d4855e237f0a1adc4b16d4796e8a6'}
JNI_PRIORITY_CORE={'windows/jni_host.h':'1bce9fb6a449dfd5ec2eff8df16b4b813d3febfd99e165ea5aee618027c47de4','windows/jni_host.cpp':'782f5af9f336155a0689b129128cfdcc7a60b10b4487fe9e8801b2dc6077daea'}
JNI_OBJECT_BIND_QUALIFICATION='5751e2f3ec2d12e8ce0bf962e0ce8000072a9400a0f03f341f810f1068fa4a93'
JNI_OBJECT_BIND_PROOF='604b7c4202a57bb6d892b287d23f3c406086ec54faa88e7a5627c28366c8dbb5'
JNI_OBJECT_BIND_PEER='585d5cb428186d5f276a10fbb3144426ca555011c06b2c3050c2c2866f62468c'
JNI_LONG_QUALIFICATION='71094a77a4f5eb3432736e63762209aabffd8fbe7433fcf7fbe4ce13e15e39ae'
JNI_OBJECT_BIND_QUALIFICATION_PATH=str(HERE.parent/'work/unity-launch-url-qualification3/acceptance.json')
JNI_OBJECT_BIND_INSERTION_SHA={'windows/jni_host.h':'9767197d448e86555d5882a2e569f5b648047d73115d6594204ed19666d6d966','windows/jni_host.cpp':'07998ddae07ae96cd48fdefa4fd608fdc1e57b658d8151a26c6aea7293c01c5e'}

def verify_jni_object_binding_projection(name,body,proof):
 assert name in JNI_OBJECT_BIND_BASE and proof['passed']is True and proof['base_commit']=='14aa64f0a0f2e67e7066aca1f5a9531086f31c59'
 assert proof['existing_all_JNI_core_bodies_byte_exact']is True and set(proof['core_source_additions'])==set(JNI_OBJECT_BIND_CORE)
 assert all(proof['owned_sources'][key]==value for key,value in JNI_OBJECT_BIND_CORE.items())
 row=proof['core_source_additions'][name]
 assert row['old_sha256']==JNI_OBJECT_BIND_BASE[name]and row['new_sha256']==JNI_OBJECT_BIND_CORE[name]and row['entire_old_file_recovered_byte_exact']is True
 assert hashlib.sha256(body).hexdigest()==JNI_OBJECT_BIND_CORE[name]
 records=row['insertions'];assert isinstance(records,list)and len(records)==1
 item=records[0];assert type(item['old_offset'])is type(item['new_offset'])is int
 value=item['bytes_hex'];assert isinstance(value,str)and value
 added=bytes.fromhex(value);assert added and added.hex()==value and added.count(b'\n')==2
 assert hashlib.sha256(added).hexdigest()==JNI_OBJECT_BIND_INSERTION_SHA[name]
 old_offset,new_offset=item['old_offset'],item['new_offset'];assert old_offset==new_offset and 0<=old_offset<=len(body)-len(added)
 assert body[new_offset:new_offset+len(added)]==added
 projected=body[:new_offset]+body[new_offset+len(added):]
 assert hashlib.sha256(projected).hexdigest()==JNI_OBJECT_BIND_BASE[name]
 return projected

def project_qualified_jni_long_source(name,body):
 # The earlier, separately qualified instance-long extension is retained, not
 # rerun or waived. Its exact inverse connects current base to priority history.
 assert name in JNI_OBJECT_BIND_BASE and hashlib.sha256(body).hexdigest()==JNI_OBJECT_BIND_BASE[name]
 if name=='windows/jni_host.h':
  changes=[(b'  // Instance jlong callbacks return the exact signed 64-bit value in X0.\n  // The existing borrowed arguments/owned callback frame rules apply.\n  void DefineLongMethod(const std::string &owner,const std::string &name,const std::string &signature,\n                        std::function<int64_t(addr_t,const MethodArguments&)> handler);\n',b'')]
 else:
  changes=[(b'void Host::DefineLongMethod(const std::string &owner,const std::string &name,const std::string &signature,std::function<int64_t(addr_t,const MethodArguments&)> handler){\n  if(!handler)throw std::invalid_argument("missing long handler");\n  DefineHandler(owner,name,signature,\'J\',[handler=std::move(handler)](addr_t object,const MethodArguments &args){return static_cast<addr_t>(handler(object,args));});\n}\n',b''),(b'||(result==\'J\'&&returns!="J")',b''),(b":kind=='J'?result",b''),(b"    case 52: case 53: case 54: {s.gpr.x0.qword=CallObject(lock,a,b,false,{},'J',&s,slot-18);return;}\n",b'')]
 for before,after in changes:
  assert body.count(before)==1;body=body.replace(before,after,1)
 assert hashlib.sha256(body).hexdigest()==JNI_PRIORITY_CORE[name]
 return body

def qualified_jni_object_source(path,name,legacy_digest,prerequisites=None,qualification_path=None):
 assert name in JNI_OBJECT_BIND_BASE and legacy_digest in(JNI_OBJECT_BIND_BASE[name],JNI_PRIORITY_CORE[name])
 path=Path(path);assert path.name==Path(name).name
 qualification_path=Path(qualification_path)if qualification_path is not None else Path(JNI_OBJECT_BIND_QUALIFICATION_PATH)
 assert sha(qualification_path)==JNI_OBJECT_BIND_QUALIFICATION
 record=json.loads(qualification_path.read_text());assert record['passed']is True and record['commit']=='14aa64f0a0f2e67e7066aca1f5a9531086f31c59'
 assert all(record['owned_sources'][key]==value for key,value in JNI_OBJECT_BIND_CORE.items())
 assert record['new_BindObjectMethod_strict_declaration_negative_controls']is record['existing_JNI_core_and_callback_constructor_frames_rechecked']is record['actual_NDK_JNI_direct_V_A_and_field_get_set']is True
 assert set(record['platforms'])=={'linux','windows'}
 for observed in record['platforms'].values():
  tests=observed['tests'];assert set(tests)=={'unity_launch_url','context_intent','java_init','jni_host','jni_callback_frame','jni_constructor_frame'}
  assert all(test['exit_code']==0 and type(test['exit_code'])is int for test in tests.values())
  assert tests['unity_launch_url']['checks']==176 and 'JNI host: 36 checks'in tests['jni_host']['stdout']and 'JNI callback frames: 464 checks'in tests['jni_callback_frame']['stdout']and 'JNI constructor frames: 362 checks'in tests['jni_constructor_frame']['stdout']
 proof_path=Path(record['source_proof']['path']);assert record['source_proof']['sha256']==JNI_OBJECT_BIND_PROOF and sha(proof_path)==JNI_OBJECT_BIND_PROOF
 proof=json.loads(proof_path.read_text());projected=verify_jni_object_binding_projection(name,path.read_bytes(),proof)
 peer_path=HERE.parent/'work/unity-launch-url-binder-peer1/peer.json';assert sha(peer_path)==JNI_OBJECT_BIND_PEER
 peer=json.loads(peer_path.read_text());assert peer['passed']is peer['source_review_only']is True
 for key in JNI_OBJECT_BIND_CORE:
  row=peer['files'][Path(key).name];assert row['old_sha256']==JNI_OBJECT_BIND_BASE[key]and row['new_sha256']==JNI_OBJECT_BIND_CORE[key]and row['whole_file_inverse_byte_exact']is True and row['added_lines']==2
 assert peer['forwarding']['result_kind']=='L'and peer['forwarding']['is_static']is peer['forwarding']['platform_native']is False and peer['forwarding']['bind_existing']is True
 if legacy_digest==JNI_PRIORITY_CORE[name]:
  long_path=HERE.parent/'work/jni-long-method-qualification1/acceptance.json';assert sha(long_path)==JNI_LONG_QUALIFICATION
  long_record=json.loads(long_path.read_text());assert long_record['passed']is True and all(long_record['owned_source_hashes'][Path(key).name]==value for key,value in JNI_OBJECT_BIND_BASE.items())
  assert set(long_record['platforms'])=={'linux','windows'}
  for observed in long_record['platforms'].values():assert observed['tests']['jni_long_method']['record_count']==54 and '626 checks'in observed['tests']['jni_long_method']['final_line']and '11125 checks'in observed['tests']['jni_numeric']['final_line']
  assert hashlib.sha256(project_qualified_jni_long_source(name,projected)).hexdigest()==legacy_digest
  if prerequisites is not None:prerequisites[str(long_path)]=JNI_LONG_QUALIFICATION
 if prerequisites is not None:
  prerequisites[str(qualification_path)]=JNI_OBJECT_BIND_QUALIFICATION;prerequisites[str(proof_path)]=JNI_OBJECT_BIND_PROOF;prerequisites[str(peer_path)]=JNI_OBJECT_BIND_PEER
 return JNI_OBJECT_BIND_CORE[name]


SIGNAL_SUBSET_BASE={'windows/signal_host.h':'b7cbcfe4ee63c53eaef932b42e9d4f6bdaa8376e50af1c89d72b7c31fb944174','windows/signal_host.cpp':'888e8b10aea824f1bd23e2d9e376db7e38a3b41f3ecf42fb3ccf372b1f6a31da'}
SIGNAL_SUBSET_CORE={'windows/signal_host.h':'12bc3d308e6ea6f86ac4dbe75f1c711a1f82a374458d2c6741d07f099fa07c58','windows/signal_host.cpp':'309a8bd7aff3c4203dd901b3e68d8bf22b1783a3e20e0ef8579d71fdfe97afa6'}
SIGNAL_SUBSET_QUALIFICATION='af404bb61a36d7e91b91aad11b6ec177b243a9f8180f02b30745c667c090274d'
SIGNAL_SUBSET_QUALIFICATION_PATH=str(HERE.parent/'work/signal-admitted-subset-qualification1/acceptance.json')
SIGNAL_SUBSET_PROOF='c748f2f660587ab63f1837c15911fa3e9565abc713c2b56b11673e486ec2c436'
SIGNAL_SUBSET_INSERTION_SHA={'windows/signal_host.h':'501216f3b40530bc9168785c79f7c0b2930f40fff6828fccb8003ead5e97d73e','windows/signal_host.cpp':'95d1632695b94e85a088c632e00f180236776464208feaff88e3dd25468a9f53'}

def verify_signal_subset_projection(name,body,proof):
 assert name in SIGNAL_SUBSET_BASE and proof['passed']is True and proof['base_commit']=='bfa4e8e650408d740e861b10e4c2bebaf26d0aa0'
 assert proof['all_existing_function_bodies_and_layout_byte_exact']is proof['new_dispatch_function_copies_existing_ownership_callback_mask_restore_and_notify_semantics']is proof['admitted_vs_selected_atomic_before_consume']is True
 assert set(proof['files'])==set(SIGNAL_SUBSET_CORE)
 row=proof['files'][name]
 assert row['old_sha256']==SIGNAL_SUBSET_BASE[name]and row['new_sha256']==SIGNAL_SUBSET_CORE[name]and row['whole_file_inverse_byte_exact']is True
 assert hashlib.sha256(body).hexdigest()==SIGNAL_SUBSET_CORE[name]
 records=row['insertions'];assert isinstance(records,list)and len(records)==1
 item=records[0];assert type(item['old_offset'])is type(item['new_offset'])is int
 value=item['bytes_hex'];assert isinstance(value,str)and value
 added=bytes.fromhex(value);assert added.hex()==value and hashlib.sha256(added).hexdigest()==SIGNAL_SUBSET_INSERTION_SHA[name]
 assert item['lines']==added.count(b'\n')=={'windows/signal_host.h':5,'windows/signal_host.cpp':20}[name]
 at=item['new_offset'];assert at==item['old_offset']and 0<=at<=len(body)-len(added)and body[at:at+len(added)]==added
 projected=body[:at]+body[at+len(added):]
 assert hashlib.sha256(projected).hexdigest()==SIGNAL_SUBSET_BASE[name]
 return projected

def qualified_signal_subset_source(path,name,legacy_digest,prerequisites=None,qualification_path=None):
 assert name in SIGNAL_SUBSET_BASE and legacy_digest==SIGNAL_SUBSET_BASE[name]
 path=Path(path);assert path.name==Path(name).name
 qualification_path=Path(qualification_path)if qualification_path is not None else Path(SIGNAL_SUBSET_QUALIFICATION_PATH)
 assert sha(qualification_path)==SIGNAL_SUBSET_QUALIFICATION
 record=json.loads(qualification_path.read_text());assert record['passed']is True and record['commit']=='bfa4e8e650408d740e861b10e4c2bebaf26d0aa0'
 assert all(record['owned_sources'][key]==value for key,value in SIGNAL_SUBSET_CORE.items())
 for field in ('actual_queue_mask_siginfo_and_real_boundary_callbacks','atomic_all_eligible_unknown_rejection_before_subset_selection','admitted_unselected_24_retained','invalid_selected_subset_returns22_before_mutation','foreign_retired_default_and_missing_boundary_controls','restored_mask_callback_edits_throw_cleanup_and_NeedsPoll_verified','existing_allowed_and_admitted_API_regressions','all_old_core_function_bodies_and_layout_byte_exact','no_NDK_lift_or_original_game_execution'):assert record[field]is True,field
 assert set(record['platforms'])=={'linux','windows'}
 for observed in record['platforms'].values():assert type(observed['exit_code'])is int and observed['exit_code']==0 and observed['checks']==256 and 'SIGNAL-ADMITTED-SUBSET-PASS checks=256'in observed['stdout']
 proof_path=Path(record['source_proof']['path']);assert record['source_proof']['sha256']==SIGNAL_SUBSET_PROOF and sha(proof_path)==SIGNAL_SUBSET_PROOF
 proof=json.loads(proof_path.read_text());verify_signal_subset_projection(name,path.read_bytes(),proof)
 if prerequisites is not None:prerequisites[str(qualification_path)]=SIGNAL_SUBSET_QUALIFICATION;prerequisites[str(proof_path)]=SIGNAL_SUBSET_PROOF
 return SIGNAL_SUBSET_CORE[name]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--build-support',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);support=a.build_support.resolve();root=HERE.parent.parent
 def wp(path):return subprocess.check_output(['wslpath','-m',str(Path(path).resolve())],text=True).strip()
 owned={n:sha(HERE/n)for n in OWN};prerequisites={}
 priority_path=HERE.parent/'work/thread-priority-held1.json';priority=json.loads(priority_path.read_text());prerequisites[str(priority_path)]=sha(priority_path)
 focused=Path(priority['acceptance_path']);assert priority['passed']and sha(focused)==priority['acceptance_sha256'];qualified=json.loads(focused.read_text());assert qualified['passed'];prerequisites[str(focused)]=sha(focused)
 peer_path=HERE.parent/'work/priority-source-peer3/peer.json';assert sha(peer_path)=='0191336d24dd436573335a9d45fba278b4c4945df9893044d5da9a61eb31dd47';peer=json.loads(peer_path.read_text());assert peer['passed']and peer['source_files']==priority['core_sources'];prerequisites[str(peer_path)]=sha(peer_path)
 assert peer['old_jni_header_exact_after_only_reviewed_additions']and peer['old_jni_cpp_exact_after_only_reviewed_additions']
 assert peer['security_exception_catalog_delta_exact']and peer['security_exception_superclass']=='java/lang/RuntimeException'
 lease_path=Path(next(k for k in peer['evidence']if k.endswith('priority-source-peer1/peer.json')));assert sha(lease_path)==peer['evidence'][str(lease_path)];lease=json.loads(lease_path.read_text());assert lease['passed']and lease['pthread_old_cpp_body_exact_after_only_additions']and lease['pthread_old_header_exact_after_only_additions'];prerequisites[str(lease_path)]=sha(lease_path)
 for name,digest in priority['core_sources'].items():
  path=HERE.parent/name
  expected=qualified_signal_subset_source(path,name,digest,prerequisites)if name in SIGNAL_SUBSET_CORE else qualified_jni_object_source(path,name,digest,prerequisites)if name in JNI_OBJECT_BIND_CORE else digest
  assert sha(path)==expected,name;prerequisites[str(path)]=sha(path)
 for name,digest in priority['fixture_sources'].items():
  path=HERE/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 base_archive=Path(priority['base_archive_path']);assert sha(base_archive)==priority['base_archive_sha256']==peer['base_archive_sha256'];prerequisites[str(base_archive)]=sha(base_archive)
 with tarfile.open(base_archive)as archive:
  old_pthreads={n:hashlib.sha256(archive.extractfile('recomp/windows/'+n).read()).hexdigest()for n in('pthread_host.h','pthread_host.cpp')}
 timed_path=HERE.parent/'work/signal-futex-timed-held2.json';timed=json.loads(timed_path.read_text());assert timed['passed'];prerequisites[str(timed_path)]=sha(timed_path)
 timed_acceptance=Path(timed['acceptance_path']);assert sha(timed_acceptance)==timed['acceptance_sha256'];timed_qualified=json.loads(timed_acceptance.read_text());assert timed_qualified['passed']and timed_qualified['core_sources']==timed['core_sources']and timed_qualified['fixture_sources']==timed['fixture_sources'];prerequisites[str(timed_acceptance)]=sha(timed_acceptance)
 assert set(timed['core_sources'])=={'windows/signal_futex.h','windows/signal_futex.cpp'}and set(timed['fixture_sources'])=={'futex_timed_ref.c','futex_timed_test.cpp','test_futex_timed.py'}
 timed_peer_path=Path(timed['source_peer_path']);assert sha(timed_peer_path)==timed['source_peer_sha256'];timed_review=json.loads(timed_peer_path.read_text());assert timed_review['passed']and timed_review['source_files']==timed['core_sources']and all(timed_review['exact_old_function_bodies'].values());prerequisites[str(timed_peer_path)]=sha(timed_peer_path)
 timed_archive=Path(timed['base_archive_path']);assert sha(timed_archive)==timed['base_archive_sha256'];prerequisites[str(timed_archive)]=sha(timed_archive)
 with tarfile.open(timed_archive)as archive:
  timed_base_hashes={n:hashlib.sha256(archive.extractfile('recomp/'+n).read()).hexdigest()for n in timed['core_sources']}
 for name,digest in timed['core_sources'].items():
  path=HERE.parent/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 for name,digest in timed['fixture_sources'].items():
  path=HERE/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 assert len(timed_qualified['canonical_records'])==timed_qualified['arm64_records']==38
 for platform in ('linux','windows'):
  observed=timed_qualified['platforms'][platform];assert observed['timed_records']==timed_qualified['canonical_records']and len(observed['timed_races'])==16 and observed['untimed_checks']==2921
 affinity_path=HERE.parent/'work/thread-affinity-held1.json';affinity=json.loads(affinity_path.read_text());assert affinity['passed'];prerequisites[str(affinity_path)]=sha(affinity_path)
 affinity_acceptance=Path(affinity['acceptance_path']);assert sha(affinity_acceptance)==affinity['acceptance_sha256'];affinity_qualified=json.loads(affinity_acceptance.read_text());assert affinity_qualified['passed']and affinity_qualified['core_sources']==affinity['core_sources']and affinity_qualified['fixture_sources']==affinity['fixture_sources'];prerequisites[str(affinity_acceptance)]=sha(affinity_acceptance)
 assert set(affinity['core_sources'])=={'windows/thread_affinity.h','windows/thread_affinity.cpp'}and len(affinity['fixture_sources'])==9
 affinity_peer=Path(affinity['source_peer_path']);assert sha(affinity_peer)==affinity['source_peer_sha256'];affinity_review=json.loads(affinity_peer.read_text());assert affinity_review['passed']and affinity_review['source_files']==affinity['core_sources'];prerequisites[str(affinity_peer)]=sha(affinity_peer)
 for name,digest in affinity['core_sources'].items():
  path=HERE.parent/name;assert sha(path)==qualified_public_affinity_source(path,name,digest,prerequisites),name;prerequisites[str(path)]=sha(path)
 for name,digest in affinity['fixture_sources'].items():
  path=HERE/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 for name,digest in affinity['protected_base_sources'].items():
  path=HERE.parent/name
  if name in timed['core_sources']:assert digest==timed_base_hashes[name]and sha(path)==timed['core_sources'][name],name
  elif name=='whole/runtime.cpp':assert sha(path)==qualified_runtime_source(path,digest,prerequisites),name
  elif name in SIGNAL_SUBSET_CORE:assert sha(path)==qualified_signal_subset_source(path,name,digest,prerequisites),name
  else:assert sha(path)==digest,name
  prerequisites[str(path)]=sha(path)
 # Accepted component manifests pin the actual production inputs used here.
 for manifest,field,names in [('worker-signal-lifecycle-held4.json','seven_live_hashes',('worker_signal_lifecycle.h','worker_signal_lifecycle.cpp')),('pthread-wait-held.json','live_sources',('pthread_host.h','pthread_host.cpp')),('signal-sleep-held5.json','core_sources',('signal_host.h','signal_host.cpp','signal_sleep.h','signal_sleep.cpp'))]:
  path=HERE.parent/'work'/manifest;record=json.loads(path.read_text());prerequisites[str(path)]=sha(path)
  for name in names:
   if manifest=='pthread-wait-held.json':
    assert old_pthreads[name]==record[field][name],name
    assert sha(HERE/name)==lease['sources'][name]==priority['core_sources']['windows/'+name],name
   elif 'windows/'+name in SIGNAL_SUBSET_CORE:assert sha(HERE/name)==qualified_signal_subset_source(HERE/name,'windows/'+name,record[field][name],prerequisites),name
   else:assert sha(HERE/name)==record[field][name],name
   prerequisites[str(HERE/name)]=sha(HERE/name)
  if manifest=='signal-sleep-held5.json':
   focused=Path(record['acceptance_path']);assert record['passed']and sha(focused)==record['acceptance_sha256'];prerequisites[str(focused)]=record['acceptance_sha256'];qualified=json.loads(focused.read_text())
   assert qualified['passed']and qualified['core']==record['core_sources']and qualified['arm64_records']==16
   for platform in ('linux','windows'):
    observed=qualified['platforms'][platform];assert'USLEEP-HOST-SUCCESS records=16'in observed['stdout']and'SIGNAL-DISPATCH-ALLOWED-SUCCESS'in observed['legacy_allowed_stdout']and'159 checks; NDK'in observed['legacy_default_stdout']
 futex_path=HERE.parent/'work/signal-futex-held1.json';futex=json.loads(futex_path.read_text());prerequisites[str(futex_path)]=sha(futex_path)
 focused=Path(futex['acceptance_path']);assert futex['passed']and sha(focused)==futex['acceptance_sha256'];prerequisites[str(focused)]=futex['acceptance_sha256'];qualified=json.loads(focused.read_text())
 assert qualified['passed']and qualified['core_sources']==futex['core_sources']and len(qualified['canonical_records'])==qualified['arm64_records']==23
 for name,digest in futex['core_sources'].items():
  path=HERE.parent/name
  if name in timed['core_sources']:assert digest==timed_base_hashes[name]and sha(path)==timed['core_sources'][name],name
  elif name=='whole/runtime.cpp':assert sha(path)==qualified_runtime_source(path,digest,prerequisites),name
  elif name in SIGNAL_SUBSET_CORE:assert sha(path)==qualified_signal_subset_source(path,name,digest,prerequisites),name
  else:assert sha(path)==digest,name
  prerequisites[str(path)]=sha(path)
 assert timed['untimed_fixture_sources']==futex['fixture_sources']
 for name,digest in futex['fixture_sources'].items():
  path=HERE/name;assert sha(path)==digest,name;prerequisites[str(path)]=digest
 for platform in ('linux','windows'):
  observed=qualified['platforms'][platform];assert'FUTEX-HOST-SUCCESS records=23'in observed['stdout']and observed['canonical_records']==qualified['canonical_records']
 audit=HERE.parent/'work/game20-first-gc-profile-audit/evidence.json';assert sha(audit)=='b4cf7340df35ab38d3e31b8dec70f5164356cd941590f70bd38f4893425052ca';data=json.loads(audit.read_text());original={str(audit):sha(audit)}
 for path,digest in data['files'].items():
  if '/work/' in path:assert sha(path)==digest,path;original[path]=digest
 library=support/'native/libil2cpp.so';assert sha(library)=='ff5c66ad2fdaa957fa005f1957988b3277331abefcdedcdb0c82e59ba2e80522';original[str(library)]=sha(library)
 with library.open('rb')as f:
  elf=ELFFile(f);v=0x25aada0;segment=next(s for s in elf.iter_segments()if s['p_type']=='PT_LOAD'and s['p_vaddr']<=v<s['p_vaddr']+s['p_filesz']);assert segment.data()[v-segment['p_vaddr']:v-segment['p_vaddr']+4]==bytes.fromhex('c0035fd6')
 assert '{0x825aada0,' in (support/'game_traces.h').read_text(),'original return head absent'
 for n in ('test_game_bootstrap.py','test_game_collector_source.py'):ast.parse((HERE/n).read_text())
 cxx=Path('/mnt/c/mingw64/bin/g++.exe');flags=['-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',wp(support/'remill-include'),'-I'+wp(support),'-I'+wp(support/'zlib-include'),'-I'+wp(support/'angle-include'),'-fsyntax-only',wp(HERE/'game_bootstrap.cpp')]
 results={}
 for name,macros,success in [('default',[],True),('enabled',['-DBUNKER_GAME_COLLECTOR_DELIVERY=1','-DBUNKER_GAME_COOPERATIVE_POLLS=1'],True),('missing-cohort',['-DBUNKER_GAME_COLLECTOR_DELIVERY=1'],False)]:
  with(out/(name+'.log')).open('w')as log:result=subprocess.run([str(cxx),*macros,*flags],stdout=log,stderr=subprocess.STDOUT)
  assert(result.returncode==0)==success,(name,result.returncode)
  if not success:assert 'Original collector delivery requires the qualified cooperative cohort'in(out/(name+'.log')).read_text()
  results[name]=result.returncode
 # Real Game19 was built without this capability. Verify refusal before any
 # runner hashing/launch/storage mutation; --verify-only cannot enable it.
 build=json.loads((support/'game_build.json').read_text());assert not build.get('collector_delivery_profile')
 result=subprocess.run([__import__('sys').executable,str(HERE/'test_game_bootstrap.py'),'--build',str(support),'--profile','frame-muted-gc','--verify-only'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(out/'unavailable-runner.log').write_text(result.stdout);assert result.returncode and'Original collector profile is unavailable'in result.stdout
 script=out/'parse.ps1';script.write_text('param([string]$Source)\n$e=$null;$t=$null;[System.Management.Automation.Language.Parser]::ParseFile($Source,[ref]$t,[ref]$e)|Out-Null;if($e){$e|Out-String|Write-Output;exit 1}\n')
 with(out/'powershell-parse.log').open('w')as log:subprocess.run(['powershell.exe','-NoProfile','-File',wp(script),'-Source',wp(HERE/'game_bootstrap_build.ps1')],stdout=log,stderr=subprocess.STDOUT,check=True)
 for name,digest in owned.items():assert sha(HERE/name)==digest,name
 for path,digest in{**prerequisites,**original}.items():assert sha(path)==digest,path
 receipt={'passed':True,'scope':'static/source/CLI-capability gates only; no native game or guest code executed','owned_sources':owned,'component_inputs':prerequisites,'original_audit_inputs':original,'compiler':str(cxx),'compiler_sha256':sha(cxx),'syntax_exit_codes':results,'unavailable_runner_exit_code':result.returncode,'build_support':str(support),'evidence':{f.name:sha(f)for f in out.iterdir()if f.is_file()}};(out/'acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('GAME-COLLECTOR-STATIC-PASS '+str(out/'acceptance.json'))
if __name__=='__main__':main()
