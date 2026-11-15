# Native channel-count fixtures

Generated locally using installed FFmpeg, no downloads or CI dependency. Each file has 30 seconds of black 320x180 MPEG4 video at 1 fps and actual silent PCM signed16 little-endian audio at 8 kHz. Channel counts are 1,3,4,5,7,10. ffprobe verified every stream count and codec before staging; manifest.json pins SHA256/bytes.

Generation command per N:
`ffmpeg -f lavfi -i color=c=black:s=320x180:r=1:d=30 -f lavfi -i anullsrc=r=8000:cl=Nc -t 30 -c:v mpeg4 -q:v 20 -c:a pcm_s16le channels-N.mkv`

These exercise Kodi native stream metadata and UI layout. They do not certify real multichannel speakers, bitstream passthrough, a PVR backend, or physical hardware.
