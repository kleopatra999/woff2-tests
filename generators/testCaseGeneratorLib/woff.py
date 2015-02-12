"""
WOFF data packers.
"""

import struct
from copy import deepcopy
from fontTools.misc import sstruct
from utilities import padData, calcHeadCheckSumAdjustment

# ------------------
# struct Description
# ------------------

woffHeaderFormat = """
    > # big endian
    signature:      4s
    flavor:         4s
    length:         L
    numTables:      H
    reserved:       H
    totalSfntSize:  L
    totalCompressedSize: L
    majorVersion:   H
    minorVersion:   H
    metaOffset:     L
    metaLength:     L
    metaOrigLength: L
    privOffset:     L
    privLength:     L
"""
woffHeaderSize = sstruct.calcsize(woffHeaderFormat)

woffTransformedGlyfHeaderFormat = """
    > # big endian
    version:               L
    numGlyphs:             H
    indexFormat:           H
    nContourStreamSize:    L
    nPointsStreamSize:     L
    flagStreamSize:        L
    glyphStreamSize:       L
    compositeStreamSize:   L
    bboxStreamSize:        L
    instructionStreamSize: L
"""

woffTransformedGlyfHeader = dict(
    version=0,
    numGlyphs=0,
    indexFormat=0,
    nContourStreamSize=0,
    nPointsStreamSize=0,
    flagStreamSize=0,
    glyphStreamSize=0,
    compositeStreamSize=0,
    bboxStreamSize=0,
    instructionStreamSize=0,
)

# ------------
# Data Packing
# ------------

knownTableTags = (
    "cmap", "head", "hhea", "hmtx", "maxp", "name", "OS/2", "post", "cvt ",
    "fpgm", "glyf", "loca", "prep", "CFF ", "VORG", "EBDT", "EBLC", "gasp",
    "hdmx", "kern", "LTSH", "PCLT", "VDMX", "vhea", "vmtx", "BASE", "GDEF",
    "GPOS", "GSUB", "EBSC", "JSTF", "MATH", "CBDT", "CBLC", "COLR", "CPAL",
    "SVG ", "sbix", "acnt", "avar", "bdat", "bloc", "bsln", "cvar", "fdsc",
    "feat", "fmtx", "fvar", "gvar", "hsty", "just", "lcar", "mort", "morx",
    "opbd", "prop", "trak", "Zapf", "Silf", "Glat", "Gloc", "Feat", "Sill",
)

unknownTableTagFlag = 63

transformedTables = ("glyf", "loca")

def transformTable(font, tag):
    origData = font.getTableData(tag)
    transformedData = origData
    if tag in transformedTables:
        if tag == "glyf":
            transformedData = tramsformGlyf(font)
        elif tag == "loca":
            transformedData = ""
        else:
            assert False, "Unknown transformed table tag: %s" % tag

    return (origData, transformedData)

def pack255UInt16(n):
    ret = ""
    if n < 253:
        ret += struct.pack(">B", n)
    elif n < 506:
        ret += struct.pack(">BB", 255, n - 253)
    elif n < 762:
        ret += struct.pack(">BB", 254, n - 506)
    else:
        ret += struct.pack(">H", n)

    return ret

def packTriplet(x, y, onCurve):
    absX = abs(x)
    absY = abs(y)
    onCurveBit = 0
    xSignBit = 0
    ySignBit = 0
    if not onCurve:
        onCurveBit = 128
    if x > 0:
        xSignBit = 1
    if y > 0:
        ySignBit = 1
    xySignBits = xSignBit + 2 * ySignBit

    fmt = ">B"
    flags = ""
    glyphs = ""
    if x == 0 and absY < 1280:
        flags += struct.pack(fmt, onCurveBit + ((absY & 0xf00) >> 7) + ySignBit)
        glyphs += struct.pack(fmt, absY & 0xff)
    elif y == 0 and absX < 1280:
        flags += struct.pack(fmt, onCurveBit + 10 + ((absX & 0xf00) >> 7) + xSignBit)
        glyphs += struct.pack(fmt, absX & 0xff)
    elif absX < 65 and absY < 65:
        flags += struct.pack(fmt, onCurveBit + 20 + ((absX - 1) & 0x30) + (((absY - 1) & 0x30) >> 2) + xySignBits)
        glyphs += struct.pack(fmt, (((absX - 1) & 0xf) << 4) | ((absY - 1) & 0xf))
    elif absX < 769 and absY < 769:
        flags += struct.pack(fmt, onCurveBit + 84 + 12 * (((absX - 1) & 0x300) >> 8) + (((absY - 1) & 0x300) >> 6) + xySignBits)
        glyphs += struct.pack(fmt, (absX - 1) & 0xff)
        glyphs += struct.pack(fmt, (absY - 1) & 0xff)
    elif absX < 4096 and absY < 4096:
        flags += struct.pack(fmt, onCurveBit + 120 + xySignBits)
        glyphs += struct.pack(fmt, absX >> 4)
        glyphs += struct.pack(fmt, ((absX & 0xf) << 4) | (absY >> 8))
        glyphs += struct.pack(fmt, absY & 0xff)
    else:
        flags += struct.pack(fmt, onCurveBit + 124 + xySignBits)
        glyphs += struct.pack(fmt, absX >> 8)
        glyphs += struct.pack(fmt, absX & 0xff)
        glyphs += struct.pack(fmt, absY >> 8)
        glyphs += struct.pack(fmt, absY & 0xff)

    return (flags, glyphs)

def tramsformGlyf(font):
    glyf = font["glyf"]
    head = font["head"]

    nContourStream = ""
    nPointsStream = ""
    flagStream = ""
    glyphStream = ""
    compositeStream = ""
    bboxStream = ""
    instructionStream = ""
    bboxBitmap = []
    bboxBitmapStream = ""

    for i in range(4 * ((len(glyf.keys()) + 31) / 32)):
        bboxBitmap.append(0)

    for glyphName in glyf.glyphOrder:
        glyph = glyf[glyphName]
        glyphId = glyf.getGlyphID(glyphName)
        if glyph.isComposite():
            assert False # XXX support composite glyphs
        else:
            # nContourStream
            nContourStream += struct.pack(">h", glyph.numberOfContours)

            # nPointsStream
            lastPointIndex = 0
            for i in range(glyph.numberOfContours):
                nPointsStream += pack255UInt16(glyph.endPtsOfContours[i] - lastPointIndex + (i == 0))
                lastPointIndex = glyph.endPtsOfContours[i]

            # flagStream & glyphStream
            lastX = 0
            lastY = 0
            lastPointIndex = 0
            for i in range(glyph.numberOfContours):
                for j in range(lastPointIndex, glyph.endPtsOfContours[i] + 1):
                    x, y = glyph.coordinates[j]
                    onCurve = glyph.flags[j] & 0x01
                    dx = x - lastX
                    dy = y - lastY
                    lastX = x
                    lastY = y
                    flags, data = packTriplet(dx, dy, onCurve)
                    flagStream += flags
                    glyphStream += data
                lastPointIndex = glyph.endPtsOfContours[i] + 1

            # instructionLength
            if glyph.numberOfContours and len(glyph.program.bytecode):
                assert False # XXX support writing instructions

            # XXX the spec is not clear here, but the reference implementation
            # seems to write the instructionLength only if there are any
            # contours.
            if glyph.numberOfContours:
                glyphStream += pack255UInt16(0)

            # instructionStream

        # bboxBitmap
        # XXX we just tell the decoder to calculate the bounding boxes for now
        #bboxBitmap[glyphId >> 3] |= 0x80 >> (glyphId & 7)

        # bboxStream
        #bboxStream += struct.pack(">hhhh", glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)

    bboxBitmapStream = "".join([struct.pack(">B", v) for v in bboxBitmap])

    header = deepcopy(woffTransformedGlyfHeader)
    header["numGlyphs"] = len(glyf.keys())
    header["indexFormat"] = head.indexToLocFormat
    header["nContourStreamSize"] = len(nContourStream)
    header["nPointsStreamSize"] = len(nPointsStream)
    header["flagStreamSize"] = len(flagStream)
    header["glyphStreamSize"] = len(glyphStream)
    header["compositeStreamSize"] = len(compositeStream)
    header["bboxStreamSize"] = len(bboxStream) + len(bboxBitmapStream)
    header["instructionStreamSize"] = len(instructionStream)

    data = sstruct.pack(woffTransformedGlyfHeaderFormat, header)
    data += nContourStream + nPointsStream + flagStream + glyphStream + compositeStream + bboxBitmapStream + bboxStream + instructionStream
    return data

def base128Size(n):
    size = 1;
    while n >= 128:
        size += 1
        n = n >> 7
    return size

def packBase128(n):
    size = base128Size(n)
    ret = ""
    for i in range(size):
        b = (n >> (7 * (size - i - 1))) & 0x7f
        if i < size - 1:
            b = b | 0x80
        ret += struct.pack(">B", b)
    return ret

def packTestHeader(header):
    return sstruct.pack(woffHeaderFormat, header)

def packTestDirectory(directory):
    data = ""
    directory = [(entry["tag"], entry) for entry in directory]
    for tag, table in directory:
        if tag in knownTableTags:
            data += struct.pack(">B", knownTableTags.index(tag))
        else:
            data += struct.pack(">B", unknownTableTagFlag)
            data += struct.pack(">4s", tag)
        data += packBase128(table["origLength"])
        if tag in transformedTables:
            data += packBase128(table["transformLength"])
    return data

def packTestMetadata((origMetadata, compMetadata), havePrivateData=False):
    if havePrivateData:
        compMetadata = padData(compMetadata)
    return compMetadata

def packTestPrivateData(privateData):
    return privateData
