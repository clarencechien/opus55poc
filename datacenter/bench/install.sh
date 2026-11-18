#!/usr/bin/env bash
# One-time setup for a bench container: Blender 4.2 LTS (headless), Mesa EGL for Workbench previews, `bench` on PATH.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x /opt/blender/blender ]; then
  mkdir -p /opt/blender
  curl -fsSL https://download.blender.org/release/Blender4.2/blender-4.2.23-linux-x64.tar.xz -o /tmp/blender.tar.xz
  tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && rm /tmp/blender.tar.xz
fi
if ! ldconfig -p | grep -q libEGL.so.1; then
  apt-get install -y -q libegl1 libegl-mesa0 libgbm1 >/dev/null 2>&1 || { apt-get update -q >/dev/null; apt-get install -y -q libegl1 libegl-mesa0 libgbm1 >/dev/null; }
fi
python3 -c "import PIL" 2>/dev/null || pip install -q pillow
printf '#!/usr/bin/env bash\nexec python3 %s/bench.py "$@"\n' "$HERE" > /usr/local/bin/bench
chmod +x /usr/local/bin/bench
echo "bench ready"
