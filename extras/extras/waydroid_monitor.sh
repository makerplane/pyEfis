#!/bin/bash

pid=0
weston_pid=0
# Stop waydroid on exit if running
trap "exit" INT TERM
trap "kill 0" EXIT

while :
do
  if [ -S ${XDG_RUNTIME_DIR}/snap.pyefis/pyefis-waydroid-1 ]; then
    if (( pid == 0 )); then
      cmd=$(ps x|grep weston|grep -v grep|head -n 1)
      regex='([0-9]+) .* --width=([0-9]+) --height=([0-9]+) '
      if [[ "$cmd" =~ $regex ]]; then
        weston_pid=${BASH_REMATCH[1]}
        width=${BASH_REMATCH[2]}
        height=${BASH_REMATCH[3]}
        # Set waydroid resolution to match weston to prevent crash
        waydroid prop set persist.waydroid.width ${width} 
        waydroid prop set persist.waydroid.width ${height}
        echo "Set ${width}x${height}"
      fi
      # Wait a couple seconds to ensure weston is ready
      sleep 2
      export WAYLAND_DISPLAY=snap.pyefis/pyefis-waydroid-1
      waydroid show-full-ui &
      pid=$!
    else
      cmd=$(ps x|grep weston|grep -v grep|head -n 1)
      regex='([0-9]+) .*'
      if [[ "$cmd" =~ $regex ]]; then
          new_weston_pid=${BASH_REMATCH[1]}
          if [ $new_weston_pid -ne $weston_pid ]; then
            echo "Killing waydroid pid for weston restart: ${pid}"
            kill ${pid}
            pid=0
            weston_pid=$new_weston_pid
          fi
      fi
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
