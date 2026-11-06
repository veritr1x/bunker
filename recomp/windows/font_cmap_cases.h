#pragma once
#include <stdint.h>
#include <string.h>
enum { FONT_CMAP_CASES=6, FONT_CMAP_TABLE_BYTES=64 };
static void font_be16(uint8_t*p,unsigned v){p[0]=(uint8_t)(v>>8);p[1]=(uint8_t)v;}
static void font_be32(uint8_t*p,unsigned v){p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v;}
static void font_cmap_case(unsigned which,uint8_t*face,uint8_t*table){
 memset(face,0,0x400);memset(table,0,FONT_CMAP_TABLE_BYTES);
 uintptr_t base=(uintptr_t)table;uint64_t size=FONT_CMAP_TABLE_BYTES;uint16_t glyphs=44;
 memcpy(face+0x330,&base,8);memcpy(face+0x338,&size,8);memcpy(face+0x1d0,&glyphs,2);
 if(which==0){font_be16(table,1);return;}
 if(which==1)return;
 font_be16(table+2,which==5?2:1);
 font_be16(table+4,3);font_be16(table+6,1);font_be32(table+8,which==2?0:24);
 font_be16(table+24,which==3?999:4);
 if(which==5){font_be16(table+12,3);font_be16(table+14,10);font_be32(table+16,28);font_be16(table+28,6);}
}
