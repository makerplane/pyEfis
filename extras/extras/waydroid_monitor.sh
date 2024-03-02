#!/bin/bash

pid=0

# Stop waydroid on exit if running
trap "exit" INT TERM
trap "kill 0" EXIT

while :
do
  if [ -S ${XDG_RUNTIME_DIR}/snap.pyefis/pyefis-waydroid-1 ]; then
    if (( pid == 0 )); then
      echo "starting waydroid"
      # Wait a couple seconds to ensure weston is ready
      sleep 2
      export WAYLAND_DISPLAY=snap.pyefis/pyefis-waydroid-1
      waydroid show-full-ui &
      pid=$!
    fi
  else
    if (( pid > 0 )); then
      echo "Killing waydroid pid: ${pid}"
      kill ${pid}
      pid=0
    fi
  fi
  sleep 1
done
