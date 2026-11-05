#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define HTTP_Z64 "0000000000000000000000000000000000000000000000000000000000000000"
#define HTTP_Z512 HTTP_Z64 HTTP_Z64 HTTP_Z64 HTTP_Z64 HTTP_Z64 HTTP_Z64 HTTP_Z64 HTTP_Z64
#define HTTP_N64 "9999999999999999999999999999999999999999999999999999999999999999"
#define HTTP_N512 HTTP_N64 HTTP_N64 HTTP_N64 HTTP_N64 HTTP_N64 HTTP_N64 HTTP_N64 HTTP_N64
static const char*const http_scan_formats[]={" HTTP/%d.%d %d"," HTTP/2 %d"," HTTP %3d"," RTSP/%d.%d %3d"};
struct HttpScanCase{const char*name;const char*input;unsigned implementation_observation;unsigned format;};
static const struct HttpScanCase http_scan_cases[]={
 {"empty","",0,0},{"space"," ",0,0},{"all-ascii-space","\t\r\n\v\f ",0,0},
 {"bad-first","X",0,0},{"h-only","H",0,0},{"ht-only","HT",0,0},{"htt-only","HTT",0,0},{"http-only","HTTP",0,0},{"slash-only","HTTP/",0,0},
 {"lowercase","http/1.1 200",0,0},{"leading-other","xHTTP/1.1 200",0,0},{"missing-slash","HTTP1.1 200",0,0},{"bad-literal","HTXP/1.1 200",0,0},
 {"major-only","HTTP/1",0,0},{"major-dot","HTTP/1.",0,0},{"minor-only","HTTP/1.1",0,0},{"minor-space","HTTP/1.1 ",0,0},{"minor-bad","HTTP/1.x 200",0,0},
 {"ordinary","HTTP/1.1 200",0,0},{"status-tail","HTTP/1.1 200 OK\r\n",0,0},{"major-two","HTTP/2.0 404 trailing",0,0},{"leading-spaces"," \tHTTP/1.1 204",0,0},
 {"all-field-spaces","\v\fHTTP/ \t1.\r\n1 \v\f200",0,0},{"space-before-dot","HTTP/1 .1 200",0,0},{"missing-dot","HTTP/1,1 200",0,0},
 {"zero-width-format-space","HTTP/1.1+200",0,0},{"negative-status-no-space","HTTP/1.1-200",0,0},{"status-newline","HTTP/1.1\r\n200",0,0},
 {"all-plus","HTTP/+1.+1 +200",0,0},{"all-minus","HTTP/-1.-2 -3",0,0},{"negative-zero","HTTP/-0.+0 -0",0,0},
 {"major-sign-only","HTTP/+",0,0},{"major-negative-sign-only","HTTP/-",0,0},{"double-sign","HTTP/++1.1 200",0,0},{"major-sign-space","HTTP/+ 1.1 200",0,0},
 {"minor-sign-only","HTTP/1.+",0,0},{"status-sign-only","HTTP/1.1 -",0,0},{"status-bad","HTTP/1.1 bad",0,0},
 {"decimal-leading-zero","HTTP/0008.0009 0200",0,0},{"hex-major","HTTP/0x1.1 200",0,0},{"hex-status","HTTP/1.1 0x200",0,0},{"major-trailing-letter","HTTP/1e2.1 200",0,0},
 {"int-max","HTTP/2147483647.2147483647 2147483647",0,0},{"int-min","HTTP/-2147483648.-2147483648 -2147483648",0,0},
 {"major-wrap32","HTTP/2147483648.1 200",1,0},{"minor-wrap32","HTTP/1.-2147483649 200",1,0},{"status-wrap32","HTTP/1.1 4294967295",1,0},
 {"signed64-max","HTTP/9223372036854775807.1 200",1,0},{"signed64-min","HTTP/-9223372036854775808.1 200",1,0},
 {"positive-overflow64","HTTP/9223372036854775808.1 200",1,0},{"negative-overflow64","HTTP/-9223372036854775809.1 200",1,0},
 {"later-overflows64","HTTP/1.9223372036854775808 -9223372036854775809",1,0},
 {"overflow-then-mismatch","HTTP/9223372036854775808x.1 200",1,0},{"overflow-partial","HTTP/1.9223372036854775808",1,0},
 {"512-zero-major","HTTP/" HTTP_Z512 ".1 200",1,0},{"513-digit-major","HTTP/" HTTP_Z512 "1.1 200",1,0},
 {"512-digit-overflow","HTTP/" HTTP_N512 ".1 200",1,0},{"513-digit-overflow","HTTP/" HTTP_N512 "9.1 200",1,0},
 {"512-zero-minor","HTTP/1." HTTP_Z512 " 200",1,0},{"513-zero-status","HTTP/1.1 " HTTP_Z512 "1",1,0},
 {"high-leading-byte","\xc3\xa9HTTP/1.1 200",0,0},{"high-numeric-byte","HTTP/\xa0" "1.1 200",0,0},
 {"nul-truncation","HTTP/1.1\0 200",0,0},{"nul-after-major","HTTP/1\0.1 200",0,0},
 {"status-only-first-digit","HTTP/1.1 2",0,0},{"trailing-whitespace","HTTP/1.1 200 \r\n",0,0},
 {"http2-empty","",0,1},{"http2-prefix","HTTP/2",0,1},{"http2-space","HTTP/2 ",0,1},{"http2-good","HTTP/2 204",0,1},{"http2-zero-space","HTTP/2+200",0,1},{"http2-trailing-zero","HTTP/20 200",0,1},{"http2-wrong-version","HTTP/1 200",0,1},{"http2-bad-number","HTTP/2 x",0,1},{"http2-sign-only","HTTP/2 -",0,1},{"http2-negative","HTTP/2 -200",0,1},{"http2-overflow","HTTP/2 9223372036854775808",1,1},
 {"http-empty","",0,2},{"http-prefix","HTTP",0,2},{"http-space","HTTP ",0,2},{"http-good","HTTP 200",0,2},{"http-zero-space","HTTP200",0,2},{"http-width4","HTTP 2000",0,2},{"http-negative-width","HTTP -200",0,2},{"http-plus-width","HTTP +123",0,2},{"http-width-limit","HTTP 99999999999999999999",0,2},{"http-sign-only","HTTP +",0,2},{"http-sign-space","HTTP + 2",0,2},{"http-leadingzero","HTTP 001x",0,2},{"http-leadingwhite","HTTP \t 200",0,2},{"http-bad-prefix","HTTX 200",0,2},
 {"rtsp-empty","",0,3},{"rtsp-prefix","RTSP/",0,3},{"rtsp-good","RTSP/1.0 200",0,3},{"rtsp-status-width","RTSP/1.0 2000",0,3},{"rtsp-negative-width","RTSP/-1.-2 -200",0,3},{"rtsp-plus-width","RTSP/+1.+2 +123",0,3},{"rtsp-status-missing","RTSP/1.0",0,3},{"rtsp-minor-missing","RTSP/1.",0,3},{"rtsp-bad-dot","RTSP/1,0 200",0,3},{"rtsp-status-sign-only","RTSP/1.0 -",0,3},{"rtsp-major-overflow","RTSP/9223372036854775808.1 200",1,3},{"rtsp-minor-overflow","RTSP/1.-9223372036854775809 200",1,3},{"rtsp-case-sensitive","rtsp/1.0 200",0,3}
};
struct HttpScanBuffers{uint64_t alignment;unsigned char slots[3][24];};
static inline void HttpScanInitialize(struct HttpScanBuffers*out){memset(out,0xa5,sizeof(*out));}
static inline void HttpScanRecord(unsigned n,unsigned form,int64_t status,int error,const struct HttpScanBuffers*out){printf("REC %u %u %u %lld %d ",n,form,http_scan_cases[n].implementation_observation,(long long)status,error);const unsigned char*bytes=(const unsigned char*)out;for(unsigned i=0;i<sizeof(*out);++i)printf("%02x",bytes[i]);putchar('\n');}
#define HTTP_SCAN_CASE_COUNT (sizeof(http_scan_cases)/sizeof(http_scan_cases[0]))
