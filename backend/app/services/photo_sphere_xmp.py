"""Write Google Photo Sphere compatible XMP metadata to COMPLETE 2:1 JPEGs.

Do not call this for partial panoramas: metadata does not create scene coverage.
The lightweight implementation inserts a standard APP1 XMP segment after the SOI.
"""
from pathlib import Path

XMP_HEADER = b'http://ns.adobe.com/xap/1.0/\x00'


def add_photo_sphere_xmp(filename, width, height):
    """Attach equirectangular GPano metadata; reject non-2:1 or invalid JPEGs."""
    width, height = int(width), int(height)
    if width < 2 or height < 1 or width != 2 * height:
        raise ValueError('Complete Photo Sphere exports must be exactly 2:1')
    path = Path(filename)
    data = path.read_bytes()
    if not data.startswith(b'\xff\xd8'):
        raise ValueError('Photo Sphere metadata can only be added to a JPEG')
    rdf = (
        '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:GPano="http://ns.google.com/photos/1.0/panorama/" '
        'GPano:UsePanoramaViewer="True" '
        'GPano:ProjectionType="equirectangular" '
        f'GPano:CroppedAreaImageWidthPixels="{width}" '
        f'GPano:CroppedAreaImageHeightPixels="{height}" '
        f'GPano:FullPanoWidthPixels="{width}" '
        f'GPano:FullPanoHeightPixels="{height}" '
        'GPano:CroppedAreaLeftPixels="0" '
        'GPano:CroppedAreaTopPixels="0" '
        'GPano:StitchingSoftware="Panorama360"/>'
        '</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )
    payload = XMP_HEADER + rdf.encode('utf-8')
    segment_length = len(payload) + 2
    if segment_length > 65535:
        raise ValueError('XMP metadata too large for JPEG segment')
    segment = b'\xff\xe1' + segment_length.to_bytes(2, 'big') + payload
    path.write_bytes(data[:2] + segment + data[2:])
    return path
