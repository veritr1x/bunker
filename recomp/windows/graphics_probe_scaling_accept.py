"""Record bounded GPU acceptance for the separate native scaling variant.

This does not select the variant for Unity or alter the accepted base bundle.
"""
from pathlib import Path
import hashlib
import json
import shutil
WORK=Path(__file__).resolve().parent.parent/'work'
HERE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    root=WORK/'angle-scaling';probe=WORK/'graphics-probe-scaling';base=WORK/'angle-native/bundle'
    bundle=read(root/'bundle/provenance.json');patch=read(root/'scaling-patch.json')
    if bundle['variant_patch']['patch_sha256']!=patch['patch_sha256']:raise RuntimeError('Bundle scaling patch changed')
    for name,digest in patch['files_sha256'].items():
        if sha(root/'src'/name)!=digest:raise RuntimeError('Variant source changed since build:'+name)
    for name,digest in bundle['files_sha256'].items():
        if sha(root/'bundle'/name)!=digest:raise RuntimeError('Variant staged file changed:'+name)
    for record in read(base/'provenance.json')['files']:
        if sha(base/'bin'/Path(record['path'].replace('\\','/')).name)!=record['sha256']:raise RuntimeError('Accepted base file changed')
    reports=[]
    for directory in [probe]+[probe/'repeats'/('run'+str(n)) for n in range(1,6)]:
        report=read(directory/'result.json');trace=(directory/'stderr.log').read_text()
        if not report['success'] or report['fixed_readback_samples']!=30 or not report['surface_attrib_real_resize']:raise RuntimeError('Native fixed-buffer proof failed')
        for required in ['buffer=160x90 physical=640x360','buffer=160x90 physical=800x450','buffer=128x72 physical=800x450','mode=1 flags=4','mode=2 flags=4']:
            if required not in trace:raise RuntimeError('Native swapchain evidence missing:'+required)
        reports.append({'path':str(directory.resolve()),'result_sha256':sha(directory/'result.json'),'trace_sha256':sha(directory/'stderr.log')})
    astc=read(WORK/'graphics-probe-scaling-astc/result.json')
    if not astc['success'] or astc['astc_sample_cases']!=239 or astc['astc_verified_bytes']!=61184:raise RuntimeError('Scaling variant ASTC regression failed')
    disabled=read(WORK/'graphics-probe-scaling-feature-disabled/result.json')
    if 'EGL_ANGLE_window_fixed_size' in disabled['egl_display_extensions']:raise RuntimeError('Disabled native capability falsely advertised fixed buffers')
    caps=read(WORK/'graphics-probe-window-caps/result.json')
    if not caps['success'] or not caps['actual_hwnd_physical_resize_verified']:raise RuntimeError('Actual HWND capability evidence missing')
    archive=root/'crash-evidence';archive.mkdir(exist_ok=True)
    for name in ['libEGL.dll','libGLESv2.dll']:
        source=root/'debug-bin'/name
        if source.exists():shutil.copy2(source,archive/name)
    for source in [WORK/'angle-scaling-gdb.log',WORK/'graphics-probe-scaling-isolated-layers/stderr.log']:
        if source.exists():shutil.copy2(source,archive/('pre-mitigation-'+source.parent.name+'-'+source.name))
    crash={'observed_exit':-1073741819,'stage':'logical fixed-buffer resize with optional deferred swapchain memory allocation enabled',
           'gdb':'NVIDIA driver worker SIGSEGV; disabling implicit layers did not remove failure',
           'mitigation':'Fixed/scaled swapchains omit VK_SWAPCHAIN_CREATE_DEFERRED_MEMORY_ALLOCATION_BIT_EXT. Real maintenance1/scaling support remains enabled; fixed-width changes also notify framebuffer state.',
           'files_sha256':{p.name:sha(p) for p in archive.iterdir() if p.is_file() and p.name!='provenance.json'}}
    (archive/'provenance.json').write_text(json.dumps(crash,indent=2)+'\n')
    sources=sorted(p for p in HERE.glob('graphics_probe_scaling*') if p.is_file())
    acceptance={'accepted_scope':'Independent diagnostic native fixed-buffer variant on tested RTX4090/Vulkan driver621.01; not a general SDK/conformance claim',
      'source_pin':'890b5d8fa2988e3719e0d80421bf3e927db9cd5c','patch':patch,'actual_hwnd_capabilities':caps,
      'positive_fresh_process_runs':len(reports),'reports':reports,'per_run':{'native_presents':11,'logical_corner_center_samples':30,'logical_readback_bytes':120,'logical_sizes':[[160,90],[128,72]],'physical_sizes':[[640,360],[800,450]],'present_modes':['FIFO','MAILBOX']},
      'negative_gates':['0/negative/oversized SurfaceAttrib dimensions rejected without changing size','Oversized fixed creation rejected','SurfaceAttrib rejects a nonfixed surface','Feature-disabled variant does not advertise fixed-size support'],
      'astc_regression':{'formats':28,'samples':239,'verified_bytes':61184,'profile_sensitive_bytes':astc['astc_profile_sensitive_bytes']},
      'mitigation':crash,'base_bundle_unchanged':True,'source_files_sha256':{str(p.resolve()):sha(p) for p in sources},
      'binary_sha256':{p.name:sha(p) for p in (root/'bundle/bin').glob('*.dll')},
      'limits':['Positive extents only; exact native per-mode scaled bounds intersect image/framebuffer limits','Default guest NativeWindows/EglHost integration is a separate gate; no app DLL argument switched','No broad GL framebuffer/client/mapped-memory virtualization','Runtime redistribution/license review remains separate from diagnostic use'],
      'primary_sources':['https://docs.vulkan.org/refpages/latest/refpages/source/VkSwapchainPresentScalingCreateInfoKHR.html','https://docs.vulkan.org/refpages/latest/refpages/source/VkSurfacePresentScalingCapabilitiesKHR.html']}
    (root/'acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n')
    bundle['accepted']=True;bundle['acceptance_scope']=acceptance['accepted_scope'];bundle['acceptance_sha256']=sha(root/'acceptance.json')
    (root/'bundle/provenance.json').write_text(json.dumps(bundle,indent=2)+'\n')
    print('Independent native scaling variant accepted for the recorded bounded diagnostic scope')


if __name__=='__main__':main()
