// GLSL ES 3.0 shaders for render_scale.c: FSR 1 (EASU + RCAS) and SGSR 1.
//
// FSR 1 is ported from AMD's ffx_fsr1.h, 32-bit paths (FsrEasuF, FsrRcasF):
//   Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
//   Permission is hereby granted, free of charge, to any person obtaining a copy
//   of this software and associated documentation files (the "Software"), to deal
//   in the Software without restriction, including without limitation the rights
//   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
//   copies of the Software, and to permit persons to whom the Software is
//   furnished to do so, subject to the following conditions:
//   The above copyright notice and this permission notice shall be included in
//   all copies or substantial portions of the Software.
//   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
//   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
//   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
//   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
//   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
//   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
//   THE SOFTWARE.
// Changes: the gather taps read the same 12 texels with texelFetch (GLES 3.0
// has no textureGather), and the approximate reciprocals are exact.
//
// SGSR 1 is ported from Qualcomm's sgsr1_shader_mobile.frag (mode RGBA):
//   Copyright (c) 2025, Qualcomm Innovation Center, Inc. All rights reserved.
//   SPDX-License-Identifier: BSD-3-Clause
//   Redistribution and use in source and binary forms, with or without
//   modification, are permitted provided that the following conditions are met:
//   1. Redistributions of source code must retain the above copyright notice,
//      this list of conditions and the following disclaimer.
//   2. Redistributions in binary form must reproduce the above copyright notice,
//      this list of conditions and the following disclaimer in the documentation
//      and/or other materials provided with the distribution.
//   3. Neither the name of the copyright holder nor the names of its contributors
//      may be used to endorse or promote products derived from this software
//      without specific prior written permission.
//   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
//   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
//   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
//   ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
//   LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
//   CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
//   SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
//   INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
//   CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
//   ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
//   POSSIBILITY OF SUCH DAMAGE.
// Changes: textureGather (GLES 3.1) is four texelFetch reads in gather order.
#pragma once

// A triangle that covers the screen; uv runs 0..1 across it.
static const char kScaleVertex[] =
    "#version 300 es\n"
    "out highp vec2 uv;\n"
    "void main() {\n"
    "    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));\n"
    "    uv = p;\n"
    "    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n"
    "}\n";

// FSR 1 EASU: the input (inSize) upscaled to the output (outSize).
static const char kEasuFragment[] =
    "#version 300 es\n"
    "precision highp float;\n"
    "precision highp int;\n"
    "uniform highp sampler2D image;\n"
    "uniform vec2 inSize;\n"
    "uniform vec2 outSize;\n"
    "out vec4 color;\n"
    "vec3 tap(ivec2 p) { return texelFetch(image, clamp(p, ivec2(0), ivec2(inSize) - 1), 0).rgb; }\n"
    "void easuTap(inout vec3 aC, inout float aW, vec2 off, vec2 dir, vec2 len, float lob, float clp, vec3 c) {\n"
    "    vec2 v = vec2(off.x * dir.x + off.y * dir.y, off.x * -dir.y + off.y * dir.x) * len;\n"
    "    float d2 = min(v.x * v.x + v.y * v.y, clp);\n"
    "    float wB = 2.0 / 5.0 * d2 - 1.0;\n"
    "    float wA = lob * d2 - 1.0;\n"
    "    wB *= wB; wA *= wA;\n"
    "    wB = 25.0 / 16.0 * wB - (25.0 / 16.0 - 1.0);\n"
    "    float w = wB * wA;\n"
    "    aC += c * w; aW += w;\n"
    "}\n"
    "void easuSet(inout vec2 dir, inout float len, float w, float lA, float lB, float lC, float lD, float lE) {\n"
    "    float lenX = max(abs(lD - lC), abs(lC - lB));\n"
    "    lenX = 1.0 / max(lenX, 1e-8);\n"
    "    float dirX = lD - lB;\n"
    "    dir.x += dirX * w;\n"
    "    lenX = clamp(abs(dirX) * lenX, 0.0, 1.0); lenX *= lenX;\n"
    "    len += lenX * w;\n"
    "    float lenY = max(abs(lE - lC), abs(lC - lA));\n"
    "    lenY = 1.0 / max(lenY, 1e-8);\n"
    "    float dirY = lE - lA;\n"
    "    dir.y += dirY * w;\n"
    "    lenY = clamp(abs(dirY) * lenY, 0.0, 1.0); lenY *= lenY;\n"
    "    len += lenY * w;\n"
    "}\n"
    "float luma(vec3 c) { return c.b * 0.5 + (c.r * 0.5 + c.g); }\n"
    "void main() {\n"
    "    vec2 pp = gl_FragCoord.xy * (inSize / outSize) - 0.5;\n"
    "    vec2 fp = floor(pp);\n"
    "    pp -= fp;\n"
    "    ivec2 f0 = ivec2(fp);\n"
    // The 12 taps around f: b c / e f g h / i j k l / n o (y grows down the kernel).
    "    vec3 b = tap(f0 + ivec2(0, -1)), c = tap(f0 + ivec2(1, -1));\n"
    "    vec3 e = tap(f0 + ivec2(-1, 0)), f = tap(f0), g = tap(f0 + ivec2(1, 0)), h = tap(f0 + ivec2(2, 0));\n"
    "    vec3 i = tap(f0 + ivec2(-1, 1)), j = tap(f0 + ivec2(0, 1)), k = tap(f0 + ivec2(1, 1)), l = tap(f0 + ivec2(2, 1));\n"
    "    vec3 n = tap(f0 + ivec2(0, 2)), o = tap(f0 + ivec2(1, 2));\n"
    "    float bL = luma(b), cL = luma(c), eL = luma(e), fL = luma(f), gL = luma(g), hL = luma(h);\n"
    "    float iL = luma(i), jL = luma(j), kL = luma(k), lL = luma(l), nL = luma(n), oL = luma(o);\n"
    "    vec2 dir = vec2(0.0);\n"
    "    float len = 0.0;\n"
    "    easuSet(dir, len, (1.0 - pp.x) * (1.0 - pp.y), bL, eL, fL, gL, jL);\n"
    "    easuSet(dir, len, pp.x * (1.0 - pp.y), cL, fL, gL, hL, kL);\n"
    "    easuSet(dir, len, (1.0 - pp.x) * pp.y, fL, iL, jL, kL, nL);\n"
    "    easuSet(dir, len, pp.x * pp.y, gL, jL, kL, lL, oL);\n"
    "    vec2 dir2 = dir * dir;\n"
    "    float dirR = dir2.x + dir2.y;\n"
    "    bool zro = dirR < 1.0 / 32768.0;\n"
    "    dirR = zro ? 1.0 : inversesqrt(dirR);\n"
    "    dir.x = zro ? 1.0 : dir.x;\n"
    "    dir *= dirR;\n"
    "    len = len * 0.5; len *= len;\n"
    "    float stretch = (dir.x * dir.x + dir.y * dir.y) / max(max(abs(dir.x), abs(dir.y)), 1e-8);\n"
    "    vec2 len2 = vec2(1.0 + (stretch - 1.0) * len, 1.0 - 0.5 * len);\n"
    "    float lob = 0.5 + ((1.0 / 4.0 - 0.04) - 0.5) * len;\n"
    "    float clp = 1.0 / lob;\n"
    "    vec3 min4 = min(min(f, g), min(j, k));\n"
    "    vec3 max4 = max(max(f, g), max(j, k));\n"
    "    vec3 aC = vec3(0.0);\n"
    "    float aW = 0.0;\n"
    "    easuTap(aC, aW, vec2(0.0, -1.0) - pp, dir, len2, lob, clp, b);\n"
    "    easuTap(aC, aW, vec2(1.0, -1.0) - pp, dir, len2, lob, clp, c);\n"
    "    easuTap(aC, aW, vec2(-1.0, 1.0) - pp, dir, len2, lob, clp, i);\n"
    "    easuTap(aC, aW, vec2(0.0, 1.0) - pp, dir, len2, lob, clp, j);\n"
    "    easuTap(aC, aW, vec2(0.0, 0.0) - pp, dir, len2, lob, clp, f);\n"
    "    easuTap(aC, aW, vec2(-1.0, 0.0) - pp, dir, len2, lob, clp, e);\n"
    "    easuTap(aC, aW, vec2(1.0, 1.0) - pp, dir, len2, lob, clp, k);\n"
    "    easuTap(aC, aW, vec2(2.0, 1.0) - pp, dir, len2, lob, clp, l);\n"
    "    easuTap(aC, aW, vec2(2.0, 0.0) - pp, dir, len2, lob, clp, h);\n"
    "    easuTap(aC, aW, vec2(1.0, 0.0) - pp, dir, len2, lob, clp, g);\n"
    "    easuTap(aC, aW, vec2(1.0, 2.0) - pp, dir, len2, lob, clp, o);\n"
    "    easuTap(aC, aW, vec2(0.0, 2.0) - pp, dir, len2, lob, clp, n);\n"
    "    color = vec4(min(max4, max(min4, aC / aW)), 1.0);\n"
    "}\n";

// FSR 1 RCAS: sharpens the upscaled image (same size in and out); sharpness is exp2(-stops).
static const char kRcasFragment[] =
    "#version 300 es\n"
    "precision highp float;\n"
    "precision highp int;\n"
    "uniform highp sampler2D image;\n"
    "uniform float sharpness;\n"
    "out vec4 color;\n"
    "vec3 tap(ivec2 p) { return texelFetch(image, clamp(p, ivec2(0), textureSize(image, 0) - 1), 0).rgb; }\n"
    "float max3(float a, float b, float c) { return max(a, max(b, c)); }\n"
    "float min3(float a, float b, float c) { return min(a, min(b, c)); }\n"
    "void main() {\n"
    "    ivec2 sp = ivec2(gl_FragCoord.xy);\n"
    "    vec3 b = tap(sp + ivec2(0, -1)), d = tap(sp + ivec2(-1, 0)), e = tap(sp), f = tap(sp + ivec2(1, 0)), h = tap(sp + ivec2(0, 1));\n"
    "    vec3 mn4 = min(min(b, d), min(f, h));\n"
    "    vec3 mx4 = max(max(b, d), max(f, h));\n"
    "    vec2 peakC = vec2(1.0, -4.0);\n"
    "    vec3 hitMin = min(mn4, e) / (4.0 * mx4);\n"
    "    vec3 hitMax = (peakC.x - max(mx4, e)) / (4.0 * mn4 + peakC.y);\n"
    "    vec3 lobeRGB = max(-hitMin, hitMax);\n"
    "    float lobe = max(-(0.25 - 1.0 / 16.0), min(max3(lobeRGB.r, lobeRGB.g, lobeRGB.b), 0.0)) * sharpness;\n"
    "    float rcpL = 1.0 / (4.0 * lobe + 1.0);\n"
    "    color = vec4((lobe * b + lobe * d + lobe * h + lobe * f + e) * rcpL, 1.0);\n"
    "}\n";

// SGSR 1, mode RGBA (green as the edge channel): one pass from the input to the output.
static const char kSgsrFragment[] =
    "#version 300 es\n"
    "precision mediump float;\n"
    "precision highp int;\n"
    "uniform highp vec4 viewport;\n"  // 1/width, 1/height, width, height of the input
    "uniform mediump sampler2D image;\n"
    "in highp vec2 uv;\n"
    "out vec4 color;\n"
    "vec4 gather(highp vec2 coord) {\n"  // textureGather(image, coord, 1)
    "    ivec2 size = textureSize(image, 0);\n"
    "    ivec2 p = ivec2(floor(coord * viewport.zw - 0.5));\n"
    "    float t00 = texelFetch(image, clamp(p, ivec2(0), size - 1), 0).g;\n"
    "    float t10 = texelFetch(image, clamp(p + ivec2(1, 0), ivec2(0), size - 1), 0).g;\n"
    "    float t01 = texelFetch(image, clamp(p + ivec2(0, 1), ivec2(0), size - 1), 0).g;\n"
    "    float t11 = texelFetch(image, clamp(p + ivec2(1, 1), ivec2(0), size - 1), 0).g;\n"
    "    return vec4(t01, t11, t10, t00);\n"
    "}\n"
    "float fastLanczos2(float x) { float wA = x - 4.0; float wB = x * wA - wA; wA *= wA; return wB * wA; }\n"
    "vec2 weightY(float dx, float dy, float c, float std) {\n"
    "    float x = ((dx * dx) + (dy * dy)) * 0.55 + clamp(abs(c) * std, 0.0, 1.0);\n"
    "    float w = fastLanczos2(x);\n"
    "    return vec2(w, w * c);\n"
    "}\n"
    "void main() {\n"
    "    const float edgeThreshold = 8.0 / 255.0;\n"
    "    const float edgeSharpness = 2.0;\n"
    "    vec4 c = vec4(textureLod(image, uv, 0.0).xyz, 0.0);\n"
    "    highp vec2 imgCoord = uv * viewport.zw + vec2(-0.5, 0.5);\n"
    "    highp vec2 imgCoordPixel = floor(imgCoord);\n"
    "    highp vec2 coord = imgCoordPixel * viewport.xy;\n"
    "    vec2 pl = imgCoord - imgCoordPixel;\n"
    "    vec4 left = gather(coord);\n"
    "    float edgeVote = abs(left.z - left.y) + abs(c.y - left.y) + abs(c.y - left.z);\n"
    "    if (edgeVote > edgeThreshold) {\n"
    "        coord.x += viewport.x;\n"
    "        vec4 right = gather(coord + vec2(viewport.x, 0.0));\n"
    "        vec4 upDown;\n"
    "        upDown.xy = gather(coord + vec2(0.0, -viewport.y)).wz;\n"
    "        upDown.zw = gather(coord + vec2(0.0, viewport.y)).yx;\n"
    "        float mean = (left.y + left.z + right.x + right.w) * 0.25;\n"
    "        left -= vec4(mean); right -= vec4(mean); upDown -= vec4(mean);\n"
    "        c.w = c.y - mean;\n"
    "        float sum = abs(left.x) + abs(left.y) + abs(left.z) + abs(left.w) + abs(right.x) + abs(right.y) + abs(right.z) + abs(right.w)\n"
    "                  + abs(upDown.x) + abs(upDown.y) + abs(upDown.z) + abs(upDown.w);\n"
    "        float std = 2.181818 / sum;\n"
    "        vec2 aWY = weightY(pl.x, pl.y + 1.0, upDown.x, std);\n"
    "        aWY += weightY(pl.x - 1.0, pl.y + 1.0, upDown.y, std);\n"
    "        aWY += weightY(pl.x - 1.0, pl.y - 2.0, upDown.z, std);\n"
    "        aWY += weightY(pl.x, pl.y - 2.0, upDown.w, std);\n"
    "        aWY += weightY(pl.x + 1.0, pl.y - 1.0, left.x, std);\n"
    "        aWY += weightY(pl.x, pl.y - 1.0, left.y, std);\n"
    "        aWY += weightY(pl.x, pl.y, left.z, std);\n"
    "        aWY += weightY(pl.x + 1.0, pl.y, left.w, std);\n"
    "        aWY += weightY(pl.x - 1.0, pl.y - 1.0, right.x, std);\n"
    "        aWY += weightY(pl.x - 2.0, pl.y - 1.0, right.y, std);\n"
    "        aWY += weightY(pl.x - 2.0, pl.y, right.z, std);\n"
    "        aWY += weightY(pl.x - 1.0, pl.y, right.w, std);\n"
    "        float finalY = aWY.y / aWY.x;\n"
    "        float maxY = max(max(left.y, left.z), max(right.x, right.w));\n"
    "        float minY = min(min(left.y, left.z), min(right.x, right.w));\n"
    "        finalY = clamp(edgeSharpness * finalY, minY, maxY);\n"
    "        float deltaY = clamp(finalY - c.w, -23.0 / 255.0, 23.0 / 255.0);\n"
    "        c.xyz = clamp(c.xyz + deltaY, 0.0, 1.0);\n"
    "    }\n"
    "    color = vec4(c.xyz, 1.0);\n"
    "}\n";
