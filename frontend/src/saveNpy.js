// saveNpy.js
// Minimal .npy writer for 2D float32 arrays (version 1.0)
export function saveNpy(array2d, filename = 'landmarks.npy') {
  // array2d: Array of Array or TypedArray rows
  const rows = array2d.length;
  const cols = rows ? array2d[0].length : 0;

  // Flatten data into Float32Array little-endian
  const flat = new Float32Array(rows * cols);
  for (let i = 0; i < rows; ++i) {
    const row = array2d[i];
    for (let j = 0; j < cols; ++j) flat[i * cols + j] = row[j];
  }

  // Build header per numpy .npy v1.0
  const MAGIC = "\x93NUMPY";
  const MAJOR = 1;
  const MINOR = 0;

  const descr = "<f4"; // little-endian float32
  const fortran_order = false;
  const headerObj = `{'descr': '${descr}', 'fortran_order': ${fortran_order}, 'shape': (${rows}, ${cols}), }`;
  // header must be padded with spaces until total header length is divisible by 16, ending with a newline
  let headerStr = headerObj;
  const encoding = 'ascii';
  // pad
  const preLen = MAGIC.length + 2 + 2 + headerStr.length; // magic + version + ushort_len + header

  // compute header length later by padding
  // We'll build header bytes after we determine header_len
  let headerBytes = new TextEncoder().encode(headerStr);
  // compute padding
  let headerLen = headerBytes.length + 1; // plus newline
  // header_len must be even? For v1.0 it's a uint16
  // pad with spaces so (magic + 2 + 2 + header_len) % 16 == 0
  const base = MAGIC.length + 2 + 2;
  let total = base + headerLen;
  let pad = (16 - (total % 16)) % 16;
  headerLen = headerLen + pad;

  // rebuild headerStr with padding and newline
  headerStr = headerStr + ' '.repeat(pad) + '\n';
  headerBytes = new TextEncoder().encode(headerStr);

  // assemble file
  const headerLenBuf = new Uint8Array(2);
  const dv = new DataView(headerLenBuf.buffer);
  dv.setUint16(0, headerBytes.length, true); // little-endian

  const magicBytes = new TextEncoder().encode(MAGIC);
  const versionBytes = new Uint8Array([MAJOR, MINOR]);

  const blobParts = [magicBytes, versionBytes, headerLenBuf, headerBytes, new Uint8Array(flat.buffer)];
  const blob = new Blob(blobParts, { type: 'application/octet-stream' });

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  a.remove(); URL.revokeObjectURL(url);
}
