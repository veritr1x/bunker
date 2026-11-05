param([Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $OutputFile){throw 'Preserve the existing public ROOT oracle'}
Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
public static class BunkerPublicRootUsageOracle {
 [StructLayout(LayoutKind.Sequential)]struct Usage {public uint count;public IntPtr names;}
 [StructLayout(LayoutKind.Sequential)]struct Match {public uint type;public Usage usage;}
 [StructLayout(LayoutKind.Sequential)]struct ChainParameters {public uint size;public Match requested;}
 [DllImport("crypt32.dll",SetLastError=true)]static extern bool CertGetCertificateChain(IntPtr engine,IntPtr cert,IntPtr time,IntPtr additional,ref ChainParameters parameters,uint flags,IntPtr reserved,out IntPtr chain);
 [DllImport("crypt32.dll")]static extern void CertFreeCertificateChain(IntPtr chain);
 [DllImport("crypt32.dll",SetLastError=true)]static extern bool CertGetEnhancedKeyUsage(IntPtr cert,uint flags,IntPtr output,ref uint bytes);
 [DllImport("kernel32.dll")]static extern void SetLastError(uint error);
 public static bool ExplicitlyDistrusted(IntPtr certificate) {
  IntPtr oid=Marshal.StringToHGlobalAnsi("1.3.6.1.5.5.7.3.1"),names=Marshal.AllocHGlobal(IntPtr.Size),chain=IntPtr.Zero;
  try{
   Marshal.WriteIntPtr(names,oid);ChainParameters parameters=new ChainParameters();parameters.size=(uint)Marshal.SizeOf(typeof(ChainParameters));parameters.requested.usage.count=1;parameters.requested.usage.names=names;
   if(!CertGetCertificateChain(IntPtr.Zero,certificate,IntPtr.Zero,IntPtr.Zero,ref parameters,0x2104,IntPtr.Zero,out chain))throw new Win32Exception(Marshal.GetLastWin32Error());
   if(chain==IntPtr.Zero)throw new InvalidOperationException("Cache-only chain query returned no context");
   // CERT_CHAIN_CONTEXT begins DWORD cbSize; CERT_TRUST_STATUS (two DWORDs).
   return (unchecked((uint)Marshal.ReadInt32(chain,4))&0x04000000)!=0;
  }finally{if(chain!=IntPtr.Zero)CertFreeCertificateChain(chain);Marshal.FreeHGlobal(names);Marshal.FreeHGlobal(oid);}
 }
 public static bool ServerAuthentication(IntPtr certificate) {
  uint size=0;SetLastError(0);
  if(!CertGetEnhancedKeyUsage(certificate,0,IntPtr.Zero,ref size))throw new Win32Exception(Marshal.GetLastWin32Error());
  IntPtr data=Marshal.AllocHGlobal(checked((int)size));
  try{
   SetLastError(0);
   if(!CertGetEnhancedKeyUsage(certificate,0,data,ref size))throw new Win32Exception(Marshal.GetLastWin32Error());
   int error=Marshal.GetLastWin32Error();uint count=unchecked((uint)Marshal.ReadInt32(data));
   if(count==0){if(unchecked((uint)error)==0x80092004)return true;if(error==0)return false;throw new Win32Exception(error);}
   IntPtr names=Marshal.ReadIntPtr(data,IntPtr.Size==8?8:4);
   for(uint i=0;i<count;++i){string oid=Marshal.PtrToStringAnsi(Marshal.ReadIntPtr(names,checked((int)i*IntPtr.Size)));if(oid=="1.3.6.1.5.5.7.3.1"||oid=="2.5.29.37.0")return true;}
   return false;
  }finally{Marshal.FreeHGlobal(data);}
 }
}
'@
$taskDenied=[System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$taskDenyCounts=[ordered]@{}
foreach($taskLocation in @('CurrentUser','LocalMachine')){
 $taskStore=[System.Security.Cryptography.X509Certificates.X509Store]::new('Disallowed',[System.Security.Cryptography.X509Certificates.StoreLocation]::$taskLocation)
 try{
  try{$taskStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly -bor [System.Security.Cryptography.X509Certificates.OpenFlags]::OpenExistingOnly)}catch [System.Security.Cryptography.CryptographicException]{if($_.Exception.HResult -eq -2147024894){$taskDenyCounts[$taskLocation]=0;continue};throw}
  $taskPublic=$taskStore.Certificates;$taskDenyCounts[$taskLocation]=$taskPublic.Count
  foreach($taskCertificate in $taskPublic){try{[void]$taskDenied.Add([System.Convert]::ToBase64String($taskCertificate.RawData))}finally{$taskCertificate.Dispose()}}
 }finally{$taskStore.Close()}
}
$taskCertificates=[System.Collections.Generic.Dictionary[string,byte[]]]::new([System.StringComparer]::Ordinal)
$taskExcludedDenied=0;$taskExcludedUsage=0;$taskExcludedDistrust=0;$taskDuplicates=0
$taskRootStore=[System.Security.Cryptography.X509Certificates.X509Store]::new('Root',[System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)
try{
 $taskRootStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly -bor [System.Security.Cryptography.X509Certificates.OpenFlags]::OpenExistingOnly)
 $taskRoots=$taskRootStore.Certificates;$taskEnumerated=$taskRoots.Count
 foreach($taskCertificate in $taskRoots){
  try{
   # Only public RawData and public certificate EKU/context metadata are read.
   # Cache-only explicit-distrust eligibility only; no peer validation or writes.
   $taskBytes=$taskCertificate.RawData;$taskKey=[System.Convert]::ToBase64String($taskBytes)
   if($taskDenied.Contains($taskKey)){$taskExcludedDenied++;continue}
   if(-not [BunkerPublicRootUsageOracle]::ServerAuthentication($taskCertificate.Handle)){$taskExcludedUsage++;continue}
   if([BunkerPublicRootUsageOracle]::ExplicitlyDistrusted($taskCertificate.Handle)){$taskExcludedDistrust++;continue}
   if($taskCertificates.ContainsKey($taskKey)){$taskDuplicates++;continue}
   $taskCertificates.Add($taskKey,$taskBytes)
  }finally{$taskCertificate.Dispose()}
 }
}finally{$taskRootStore.Close()}
$taskStream=[System.IO.FileStream]::new($OutputFile,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::Read)
$taskWriter=[System.IO.BinaryWriter]::new($taskStream)
try{
 $taskWriter.Write([uint32]0x31525354);$taskWriter.Write([uint32]$taskCertificates.Count)
 foreach($taskKey in @($taskCertificates.Keys|Sort-Object)){$taskBytes=$taskCertificates[$taskKey];$taskWriter.Write([uint32]$taskBytes.Length);$taskWriter.Write($taskBytes)}
}finally{$taskWriter.Dispose();$taskStream.Dispose()}
[ordered]@{passed=$true;scope='Read-only independent .NET logical CurrentUser ROOT minus CU+LM Disallowed DER, effective non-server EKU, cache-only explicit distrust; public data only.';enumerated_roots=$taskEnumerated;disallowed_stores=$taskDenyCounts;disallowed_unique_DER=$taskDenied.Count;excluded_disallowed=$taskExcludedDenied;excluded_usage=$taskExcludedUsage;excluded_explicit_distrust=$taskExcludedDistrust;duplicates=$taskDuplicates;accepted_public_DER_certificates=$taskCertificates.Count;output_sha256=([System.BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([System.IO.File]::ReadAllBytes($OutputFile))).Replace('-','').ToLowerInvariant());chain_flags=0x2104;chain_error_bit=0x04000000;chain_verification_claim=$false;network_requests=0;store_writes=0}|ConvertTo-Json -Compress
